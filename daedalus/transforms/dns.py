"""DNS transforms: resolution, mail/name servers, TXT/SPF/DMARC, PTR and subdomain discovery."""

from __future__ import annotations

import re

from ..entities import L, registered_domain
from ..webutil import DNSUnavailable, resolve, reverse_dns
from .base import Skip, Transform, register

VERIFICATION_PREFIXES = (
    "google-site-verification", "facebook-domain-verification", "apple-domain-verification", "ms=",
    "atlassian-domain-verification", "docusign", "adobe-idp-site-verification", "globalsign-domain-verification",
    "stripe-verification", "zoom-domain-verification", "openai-domain-verification", "have-i-been-pwned-verification",
    "yandex-verification", "dropbox-domain-verification", "slack-domain-verification", "hubspot-developer-verification",
)


@register
class ToIP(Transform):
    name = "dns_resolve"
    title = L("To IP address [DNS]", "A dirección IP [DNS]")
    description = L("Resolve A and AAAA records.", "Resuelve los registros A y AAAA.")
    category = "dns"
    inputs = ("domain", "hostname")
    outputs = ("ip",)
    sources = ("DNS",)

    async def run(self, ctx):
        failed = None
        for rtype in ("A", "AAAA"):
            try:
                ips = await resolve(ctx.value, rtype)
            except DNSUnavailable as e:
                failed = e
                continue
            for ip in ips:
                ctx.add("ip", ip, {"version": 4 if rtype == "A" else 6}, label=rtype)
        if failed and not ctx.found:
            raise failed


@register
class ToMX(Transform):
    name = "dns_mx"
    title = L("To mail servers [MX]", "A servidores de correo [MX]")
    description = L("MX records of the domain.", "Registros MX del dominio.")
    category = "dns"
    inputs = ("domain",)
    outputs = ("hostname",)
    sources = ("DNS",)

    async def run(self, ctx):
        records = await resolve(ctx.value, "MX")
        for rec in records:
            parts = rec.split()
            if len(parts) == 2 and parts[1] != ".":
                ctx.add("hostname", parts[1].rstrip("."), {"mx_priority": int(parts[0])}, label="MX")
        ctx.enrich({"accepts_mail": bool(records)})


@register
class ToNS(Transform):
    name = "dns_ns"
    title = L("To name servers [NS]", "A servidores de nombres [NS]")
    description = L("NS records of the domain.", "Registros NS del dominio.")
    category = "dns"
    inputs = ("domain",)
    outputs = ("hostname",)
    sources = ("DNS",)

    async def run(self, ctx):
        for ns in await resolve(ctx.value, "NS"):
            ctx.add("hostname", ns.rstrip("."), {"role": "name server"}, label="NS")


@register
class ToTXT(Transform):
    name = "dns_txt"
    title = L("To TXT / SPF / DMARC", "A TXT / SPF / DMARC")
    description = L(
        "Reads TXT records: SPF includes become domains and IPs, DMARC report addresses become emails, "
        "and third-party verification tokens are stored as properties.",
        "Lee los TXT: los include de SPF pasan a dominios e IPs, las direcciones de informes DMARC a correos "
        "y los tokens de verificación de terceros se guardan como propiedades.",
    )
    category = "dns"
    inputs = ("domain",)
    outputs = ("domain", "hostname", "ip", "netblock", "email")
    sources = ("DNS",)

    async def run(self, ctx):
        txt = await resolve(ctx.value, "TXT")
        txt = [t.replace('" "', "") for t in txt]
        props: dict = {"txt_records": txt} if txt else {}
        verifications = [t for t in txt if t.lower().startswith(VERIFICATION_PREFIXES)]
        if verifications:
            props["verification_tokens"] = verifications
        spf = next((t for t in txt if t.lower().startswith("v=spf1")), None)
        if spf:
            props["spf"] = spf
            for mech in spf.split()[1:]:
                mech = mech.lstrip("+~?-")
                key, _, val = mech.partition(":") if ":" in mech else mech.partition("=")
                key = key.lower()
                if key in ("include", "redirect") and val:
                    ctx.add("domain" if registered_domain(val) == val.lower() else "hostname", val,
                            label=f"SPF {key}")
                elif key in ("ip4", "ip6") and val:
                    ctx.add("netblock" if "/" in val else "ip", val, label=f"SPF {key}")
        try:
            dmarc_txt = await resolve(f"_dmarc.{ctx.value}", "TXT")
        except DNSUnavailable:
            dmarc_txt = []  # keep the SPF findings
        dmarc = next((t for t in dmarc_txt if t.lower().startswith("v=dmarc1")), None)
        if dmarc:
            props["dmarc"] = dmarc
            policy = re.search(r"\bp=(\w+)", dmarc)
            if policy:
                props["dmarc_policy"] = policy.group(1)
            for addr in re.findall(r"mailto:([^,;!\s]+)", dmarc):
                ctx.add("email", addr, {"role": "DMARC reports"}, label="DMARC report")
        ctx.enrich(props)


@register
class ReverseDNS(Transform):
    name = "reverse_dns"
    title = L("To DNS name [PTR]", "A nombre DNS [PTR]")
    description = L("Reverse DNS lookup.", "Búsqueda DNS inversa.")
    category = "dns"
    inputs = ("ip",)
    outputs = ("hostname",)
    sources = ("DNS",)

    async def run(self, ctx):
        for host in await reverse_dns(ctx.value):
            ctx.add("hostname", host, label="PTR")


@register
class HostToDomain(Transform):
    name = "hostname_to_domain"
    title = L("To parent domain", "A dominio padre")
    description = L("Registrable domain of a DNS name.", "Dominio registrable de un nombre DNS.")
    category = "dns"
    inputs = ("hostname",)
    outputs = ("domain",)

    async def run(self, ctx):
        parent = registered_domain(ctx.value)
        if parent and parent != ctx.value:
            ctx.add("domain", parent, label="subdomain of", reverse=True)


@register
class CrtSh(Transform):
    name = "crtsh_subdomains"
    title = L("To subdomains [Certificate Transparency]", "A subdominios [Certificate Transparency]")
    description = L("Names found in TLS certificates (crt.sh, CertSpotter fallback).",
                    "Nombres encontrados en certificados TLS (crt.sh, con CertSpotter de respaldo).")
    category = "dns"
    inputs = ("domain",)
    outputs = ("hostname",)
    sources = ("crt.sh", "CertSpotter")
    timeout = 90

    async def run(self, ctx):
        domain = ctx.value
        names: dict[str, str] = {}
        try:
            st, data = await ctx.get_json("https://crt.sh/", params={"q": f"%.{domain}", "output": "json"}, timeout=60)
        except Exception:  # noqa: BLE001  crt.sh is notoriously flaky
            st, data = 0, None
        if st == 200 and isinstance(data, list):
            for row in data:
                for name in str(row.get("name_value", "")).split("\n"):
                    names.setdefault(name.strip().lower().lstrip("*."), row.get("not_before") or "")
        else:
            st, data = await ctx.get_json(
                "https://api.certspotter.com/v1/issuances",
                params={"domain": domain, "include_subdomains": "true", "expand": "dns_names"},
            )
            if st != 200 or not isinstance(data, list):
                raise Skip(f"crt.sh and CertSpotter unavailable (HTTP {st})")
            for row in data:
                for name in row.get("dns_names") or []:
                    names.setdefault(name.strip().lower().lstrip("*."), row.get("not_before") or "")
        subs = sorted(n for n in names if n.endswith("." + domain) and n != domain)
        for name in subs:
            first = names[name][:10]
            props = {"first_certificate": first, "_dates": [["First certificate", first]]} if first else {}
            if ctx.add("hostname", name, props, label="subdomain") is None:
                break
        ctx.enrich({"subdomain_count": len(subs)})


@register
class HackerTargetHosts(Transform):
    name = "hackertarget_hosts"
    title = L("To DNS names and IPs [HackerTarget]", "A nombres DNS e IPs [HackerTarget]")
    description = L("Passive host search (free tier: 50 queries/day).",
                    "Búsqueda pasiva de hosts (gratis: 50 consultas/día).")
    category = "dns"
    inputs = ("domain",)
    outputs = ("hostname", "ip")
    sources = ("HackerTarget",)
    default = False

    async def run(self, ctx):
        r = await ctx.http.get("https://api.hackertarget.com/hostsearch/", params={"q": ctx.value})
        body = r.text.strip()
        if r.status_code != 200 or "," not in body:
            raise Skip(body[:120] or f"HTTP {r.status_code}")
        for line in body.splitlines():
            host, _, ip = line.partition(",")
            host = host.strip().lower()
            if not host.endswith(ctx.value):
                continue
            hid = ctx.add("hostname", host, label="host") if host != ctx.value else ctx.entity["id"]
            if hid and ip.strip():
                ctx.add("ip", ip.strip(), label="A", parent=hid)


@register
class ReverseIP(Transform):
    name = "reverse_ip"
    title = L("To domains on the same IP", "A dominios en la misma IP")
    description = L("Reverse IP lookup (HackerTarget free tier).", "IP inversa (capa gratuita de HackerTarget).")
    category = "dns"
    inputs = ("ip",)
    outputs = ("hostname",)
    sources = ("HackerTarget",)

    async def run(self, ctx):
        r = await ctx.http.get("https://api.hackertarget.com/reverseiplookup/", params={"q": ctx.value})
        body = r.text.strip()
        if r.status_code != 200 or not body or "error" in body.lower() or "api count" in body.lower():
            raise Skip(body[:120] or f"HTTP {r.status_code}")
        if "no dns a records" in body.lower():
            return
        for host in body.splitlines():
            host = host.strip().lower()
            if host and host != ctx.value:
                etype = "domain" if registered_domain(host) == host else "hostname"
                if ctx.add(etype, host, label="hosted on", reverse=True) is None:
                    break
