"""Infrastructure transforms: RDAP/WHOIS, IP geolocation, Shodan InternetDB and routing data."""

from __future__ import annotations

import asyncio
import re

from ..entities import L
from .base import Skip, Transform, register

_REDACTED = re.compile(r"redact|privacy|private|protected|withheld|not disclosed|gdpr|statutory masking|"
                       r"contact form|whoisguard|please query", re.I)
ROLE_LABELS = {"registrant": "registrant", "administrative": "admin contact", "technical": "tech contact",
               "abuse": "abuse contact", "billing": "billing contact", "registrar": "registrar"}


def _clean(v) -> str | None:
    if not isinstance(v, str):
        return None
    v = " ".join(v.split())
    return None if not v or _REDACTED.search(v) else v


def _vcard(entity: dict) -> dict:
    out: dict = {}
    arr = entity.get("vcardArray")
    if not (isinstance(arr, list) and len(arr) == 2 and isinstance(arr[1], list)):
        return out
    for item in arr[1]:
        if not isinstance(item, list) or len(item) < 4:
            continue
        key, params, _, val = item[0], item[1] if isinstance(item[1], dict) else {}, item[2], item[3]
        if key in ("fn", "org", "email", "tel"):
            v = _clean(val if isinstance(val, str) else "")
            if v:
                out.setdefault(key, v.removeprefix("tel:").removeprefix("mailto:"))
        elif key == "adr":
            label = params.get("label")
            if isinstance(val, list):
                label = label or ", ".join(x for x in val if isinstance(x, str) and x)
            label = _clean(label or "")
            if label:
                out["adr"] = label
    return out


def _walk_entities(entities: list, depth: int = 0):
    for e in entities or []:
        if not isinstance(e, dict):
            continue
        yield e
        if depth < 2:
            yield from _walk_entities(e.get("entities") or [], depth + 1)


def _events(data: dict) -> dict:
    out = {}
    for ev in data.get("events") or []:
        action, date = ev.get("eventAction"), (ev.get("eventDate") or "")[:10]
        if action and date:
            out[action] = date
    return out


async def whois_query(server: str, query: str, timeout: float = 15) -> str:
    reader, writer = await asyncio.wait_for(asyncio.open_connection(server, 43), timeout)
    try:
        writer.write((query + "\r\n").encode())
        await writer.drain()
        data = await asyncio.wait_for(reader.read(200_000), timeout)
    finally:
        writer.close()
    return data.decode("utf-8", "replace")


WHOIS_FIELDS = {
    "registrar": ("registrar", "sponsoring registrar", "registrar name"),
    "created": ("creation date", "created", "registered", "registration time", "created on"),
    "expires": ("registry expiry date", "expiration date", "expiry date", "paid-till", "expires", "expires on"),
    "updated": ("updated date", "last updated", "changed", "last modified"),
    "registrant_org": ("registrant organization", "registrant organisation", "org", "registrant"),
    "registrant_name": ("registrant name",),
    "registrant_email": ("registrant email",),
    "registrant_country": ("registrant country",),
    "name_server": ("name server", "nserver", "nameserver"),
}


def parse_whois(text: str) -> dict:
    out: dict = {}
    for line in text.splitlines():
        if ":" not in line or line.lstrip().startswith(("%", "#", ">>>")):
            continue
        k, _, v = line.partition(":")
        k, v = k.strip().lower(), v.strip()
        if not v:
            continue
        for field, names in WHOIS_FIELDS.items():
            if k in names:
                if field == "name_server":
                    out.setdefault(field, []).append(v.split()[0].lower().rstrip("."))
                else:
                    out.setdefault(field, v)
    return out


@register
class RdapDomain(Transform):
    name = "rdap_domain"
    title = L("To registration data [RDAP/WHOIS]", "A datos de registro [RDAP/WHOIS]")
    description = L("Registrar, dates, contacts and name servers. Falls back to WHOIS when the TLD has no RDAP.",
                    "Registrador, fechas, contactos y servidores de nombres. Usa WHOIS si el TLD no tiene RDAP.")
    category = "infrastructure"
    inputs = ("domain",)
    outputs = ("organization", "email", "phone", "person", "hostname", "location")
    sources = ("RDAP", "WHOIS")

    async def run(self, ctx):
        st, data = await ctx.get_json(f"https://rdap.org/domain/{ctx.value}")
        if st == 200 and isinstance(data, dict):
            await self._from_rdap(ctx, data)
        else:
            await self._from_whois(ctx)

    async def _from_rdap(self, ctx, data: dict) -> None:
        ev = _events(data)
        props = {
            "registered": ev.get("registration"),
            "expires": ev.get("expiration"),
            "last_changed": ev.get("last changed"),
            "status": data.get("status"),
            "_dates": [[label, ev[k]] for k, label in (("registration", "Domain registered"),
                                                        ("expiration", "Domain expires"),
                                                        ("last changed", "Registration changed")) if ev.get(k)],
            "_links": [["RDAP", (data.get("links") or [{}])[0].get("href") or f"https://rdap.org/domain/{ctx.value}"]],
        }
        for e in _walk_entities(data.get("entities") or []):
            roles = e.get("roles") or []
            card = _vcard(e)
            for role in roles:
                label = ROLE_LABELS.get(role, role)
                if role == "abuse":  # the registrar's abuse desk says nothing about the owner
                    continue
                if role == "registrar":
                    name = card.get("fn") or card.get("org")
                    if name:
                        props["registrar"] = name
                        ctx.add("organization", name, {"role": "registrar"}, label="registrar")
                    continue
                org = card.get("org") or (card.get("fn") if role == "registrant" else None)
                if org:
                    ctx.add("organization", org, label=label)
                if card.get("fn") and card.get("fn") != org:
                    ctx.add("person", card["fn"], label=label)
                if card.get("email"):
                    ctx.add("email", card["email"], {"role": label}, label=label)
                if card.get("tel"):
                    ctx.add("phone", card["tel"], label=label)
                if card.get("adr") and role == "registrant":
                    ctx.add("location", card["adr"], label="registrant address")
        for ns in data.get("nameservers") or []:
            name = (ns.get("ldhName") or "").lower().rstrip(".")
            if name:
                ctx.add("hostname", name, {"role": "name server"}, label="NS")
        ctx.enrich(props)

    async def _from_whois(self, ctx) -> None:
        tld = ctx.value.rsplit(".", 1)[-1]
        try:
            iana = await whois_query("whois.iana.org", tld)
            m = re.search(r"^(?:refer|whois):\s*(\S+)", iana, re.M | re.I)
            if not m:
                raise Skip(f"No RDAP or WHOIS server known for .{tld}")
            text = await whois_query(m.group(1), ctx.value)
        except (OSError, asyncio.TimeoutError) as e:
            raise Skip(f"No RDAP for .{tld} and WHOIS unreachable ({type(e).__name__})") from e
        w = parse_whois(text)
        if not w:
            ctx.log("WHOIS answered without parseable fields")
            ctx.enrich({"whois_raw": text[:4000]})
            return
        if w.get("registrar"):
            ctx.add("organization", w["registrar"], {"role": "registrar"}, label="registrar")
        org = _clean(w.get("registrant_org"))
        if org:
            ctx.add("organization", org, label="registrant")
        if _clean(w.get("registrant_name")):
            ctx.add("person", w["registrant_name"], label="registrant")
        if _clean(w.get("registrant_email")) and "@" in w["registrant_email"]:
            ctx.add("email", w["registrant_email"], label="registrant")
        for ns in w.get("name_server") or []:
            ctx.add("hostname", ns, {"role": "name server"}, label="NS")
        dates = [[lbl, w[k][:10]] for k, lbl in (("created", "Domain registered"), ("expires", "Domain expires"))
                 if w.get(k) and re.match(r"\d{4}-\d{2}-\d{2}", w[k])]
        ctx.enrich({"registrar": w.get("registrar"), "registered": w.get("created"), "expires": w.get("expires"),
                    "registrant_country": w.get("registrant_country"), "_dates": dates, "whois_raw": text[:4000]})


@register
class RdapIP(Transform):
    name = "rdap_ip"
    title = L("To netblock and owner [RDAP]", "A bloque de red y titular [RDAP]")
    description = L("Network allocation, owner organisation and abuse contact.",
                    "Asignación de red, organización titular y contacto de abuso.")
    category = "infrastructure"
    inputs = ("ip",)
    outputs = ("netblock", "organization", "email")
    sources = ("RDAP",)

    async def run(self, ctx):
        st, data = await ctx.get_json(f"https://rdap.org/ip/{ctx.value}")
        if st != 200 or not isinstance(data, dict):
            raise Skip(f"RDAP HTTP {st}")
        cidrs = [f"{c.get('v4prefix') or c.get('v6prefix')}/{c.get('length')}" for c in data.get("cidr0_cidrs") or []
                 if (c.get("v4prefix") or c.get("v6prefix")) and c.get("length") is not None]
        parent = None
        for cidr in cidrs[:3]:
            parent = ctx.add("netblock", cidr, {"name": data.get("name"), "handle": data.get("handle"),
                                                "country": data.get("country")}, label="in netblock") or parent
        ev = _events(data)
        ctx.enrich({"network_name": data.get("name"), "network_range":
                    f"{data.get('startAddress')} - {data.get('endAddress')}" if data.get("startAddress") else None,
                    "country": data.get("country"), "allocated": ev.get("registration")})
        for e in _walk_entities(data.get("entities") or []):
            card, roles = _vcard(e), e.get("roles") or []
            org = card.get("org") or card.get("fn")
            if org and ("registrant" in roles or "administrative" in roles):
                ctx.add("organization", org, label="owner", parent=parent)
            if card.get("email") and "abuse" in roles:
                ctx.add("email", card["email"], {"role": "abuse"}, label="abuse contact")


@register
class IPGeo(Transform):
    name = "ip_geolocation"
    title = L("To location and ISP [GeoIP]", "A ubicación e ISP [GeoIP]")
    description = L("Approximate geolocation, ISP and autonomous system.",
                    "Geolocalización aproximada, ISP y sistema autónomo.")
    category = "infrastructure"
    inputs = ("ip",)
    outputs = ("location", "asn", "organization")
    sources = ("ipwho.is", "ip-api.com")

    async def run(self, ctx):
        st, d = await ctx.get_json(f"https://ipwho.is/{ctx.value}")
        if st == 200 and isinstance(d, dict) and d.get("success"):
            conn = d.get("connection") or {}
            geo = {"city": d.get("city"), "region": d.get("region"), "country": d.get("country"),
                   "country_code": d.get("country_code"), "lat": d.get("latitude"), "lon": d.get("longitude"),
                   "asn": conn.get("asn"), "as_name": conn.get("org"), "isp": conn.get("isp"),
                   "timezone": (d.get("timezone") or {}).get("id")}
        else:
            st, d = await ctx.get_json(f"http://ip-api.com/json/{ctx.value}",
                                       params={"fields": "status,message,country,countryCode,regionName,city,lat,lon,"
                                                         "isp,org,as,timezone"})
            if st != 200 or not isinstance(d, dict) or d.get("status") != "success":
                raise Skip("Geolocation services unavailable or private address")
            asn = re.match(r"AS(\d+)\s*(.*)", d.get("as") or "")
            geo = {"city": d.get("city"), "region": d.get("regionName"), "country": d.get("country"),
                   "country_code": d.get("countryCode"), "lat": d.get("lat"), "lon": d.get("lon"),
                   "asn": int(asn.group(1)) if asn else None, "as_name": (asn.group(2) if asn else None) or d.get("org"),
                   "isp": d.get("isp"), "timezone": d.get("timezone")}
        place = ", ".join(x for x in (geo["city"], geo["region"], geo["country"]) if x)
        if place:
            ctx.add("location", place, {"_lat": geo["lat"], "_lon": geo["lon"], "country_code": geo["country_code"],
                                        "precision": "IP geolocation (approximate)"}, label="located in")
        if geo["asn"]:
            ctx.add("asn", f"AS{geo['asn']}", {"name": geo["as_name"]}, label="AS")
        if geo["isp"]:
            ctx.add("organization", geo["isp"], {"role": "ISP"}, label="ISP")
        ctx.enrich({"country": geo["country"], "city": geo["city"], "isp": geo["isp"], "timezone": geo["timezone"]})


@register
class InternetDB(Transform):
    name = "shodan_internetdb"
    title = L("To ports, hostnames and CVEs [InternetDB]", "A puertos, hosts y CVEs [InternetDB]")
    description = L("Shodan's free InternetDB: open ports, CPEs, tags, hostnames and known vulnerabilities.",
                    "InternetDB gratuita de Shodan: puertos abiertos, CPEs, etiquetas, hosts y vulnerabilidades.")
    category = "infrastructure"
    inputs = ("ip",)
    outputs = ("hostname", "vulnerability")
    sources = ("Shodan InternetDB",)

    async def run(self, ctx):
        st, d = await ctx.get_json(f"https://internetdb.shodan.io/{ctx.value}")
        if st == 404:
            return
        if st != 200 or not isinstance(d, dict):
            raise Skip(f"InternetDB HTTP {st}")
        ctx.enrich({"open_ports": d.get("ports"), "cpes": d.get("cpes"), "tags": d.get("tags"),
                    "_links": [["Shodan", f"https://www.shodan.io/host/{ctx.value}"]]})
        for host in d.get("hostnames") or []:
            ctx.add("hostname", host, label="hostname")
        for cve in d.get("vulns") or []:
            ctx.add("vulnerability", cve, label="vulnerable to")


def _holder_org(holder: str) -> str | None:
    """"CLOUDFLARENET - Cloudflare, Inc., US" -> "Cloudflare, Inc."."""
    name = holder.split(" - ", 1)[1] if " - " in holder else holder
    name = re.sub(r",\s*[A-Z]{2}$", "", name).strip()
    return name or None


@register
class RipeNetwork(Transform):
    name = "ripestat_network"
    title = L("To netblock and AS [RIPEstat]", "A bloque de red y AS [RIPEstat]")
    description = L("Announced prefix and origin AS of an IP, or the origin AS of a netblock.",
                    "Prefijo anunciado y AS de origen de una IP, o el AS de origen de un bloque.")
    category = "infrastructure"
    inputs = ("ip", "netblock")
    outputs = ("netblock", "asn")
    sources = ("RIPEstat",)

    async def run(self, ctx):
        base = "https://stat.ripe.net/data"
        if ctx.entity["type"] == "ip":
            st, d = await ctx.get_json(f"{base}/network-info/data.json", params={"resource": ctx.value})
            data = (d or {}).get("data") or {} if st == 200 else {}
            prefix = data.get("prefix")
            parent = ctx.add("netblock", prefix, label="in netblock") if prefix else None
            for asn in data.get("asns") or []:
                ctx.add("asn", f"AS{asn}", label="announced by", parent=parent)
            return
        st, d = await ctx.get_json(f"{base}/prefix-overview/data.json", params={"resource": ctx.value})
        data = (d or {}).get("data") or {} if st == 200 else {}
        block = data.get("block") or {}
        ctx.enrich({"block": block.get("resource"), "block_name": block.get("name"), "block_desc": block.get("desc")})
        for a in data.get("asns") or []:
            ctx.add("asn", f"AS{a.get('asn')}", {"name": a.get("holder")}, label="announced by")


@register
class AsnPrefixes(Transform):
    name = "asn_prefixes"
    title = L("To announced netblocks and owner", "A bloques anunciados y titular")
    description = L("Holder of an autonomous system and the prefixes it announces.",
                    "Titular de un sistema autónomo y los prefijos que anuncia.")
    category = "infrastructure"
    inputs = ("asn",)
    outputs = ("netblock", "organization")
    sources = ("RIPEstat",)

    async def run(self, ctx):
        base = "https://stat.ripe.net/data"
        asn = ctx.value
        st, d = await ctx.get_json(f"{base}/as-overview/data.json", params={"resource": asn})
        holder = (((d or {}).get("data") or {}).get("holder") if st == 200 else None) or ""
        if holder:
            ctx.enrich({"name": holder})
            org = _holder_org(holder)
            if org:
                ctx.add("organization", org, label="operated by")
        st, d = await ctx.get_json(f"{base}/announced-prefixes/data.json", params={"resource": asn})
        prefixes = (((d or {}).get("data") or {}).get("prefixes") or []) if st == 200 else []
        ctx.enrich({"announced_prefixes": len(prefixes)})
        for p in prefixes:
            if ctx.add("netblock", p.get("prefix"), label="announces") is None and ctx.truncated:
                break
