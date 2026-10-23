"""Threat-intel transforms: hashes, CVEs and reputation services (most need an API key)."""

from __future__ import annotations

import base64

from ..entities import HASH_LENGTHS, L, registered_domain
from .base import Skip, Transform, register


@register
class HashLookup(Transform):
    name = "hash_lookup"
    title = L("To known file [CIRCL hashlookup]", "A fichero conocido [CIRCL hashlookup]")
    description = L("Is the hash a known file (NSRL and other known-good sets)?",
                    "¿El hash corresponde a un fichero conocido (NSRL y otros conjuntos)?")
    category = "threat"
    inputs = ("hash",)
    sources = ("CIRCL hashlookup",)

    async def run(self, ctx):
        algo = {32: "md5", 40: "sha1", 64: "sha256"}.get(len(ctx.value))
        if not algo:
            raise Skip(f"{HASH_LENGTHS.get(len(ctx.value), 'This hash')} is not supported by hashlookup")
        st, d = await ctx.get_json(f"https://hashlookup.circl.lu/lookup/{algo}/{ctx.value}")
        ctx.enrich({"algorithm": HASH_LENGTHS.get(len(ctx.value))})
        if st == 404:
            ctx.enrich({"known_file": False})
            ctx.log("Unknown to hashlookup")
            return
        if st != 200 or not isinstance(d, dict):
            raise Skip(f"hashlookup HTTP {st}")
        product = d.get("ProductCode") or {}
        ctx.enrich({"known_file": True, "filename": d.get("FileName"), "file_size": d.get("FileSize"),
                    "product": product.get("ProductName"), "vendor": product.get("MfgCode"),
                    "known_malicious": d.get("KnownMalicious"), "hashlookup_source": d.get("source")})


@register
class CveInfo(Transform):
    name = "cve_info"
    title = L("To CVE details [NVD]", "A detalles del CVE [NVD]")
    description = L("Description, CVSS score and publication date.", "Descripción, puntuación CVSS y fecha.")
    category = "threat"
    inputs = ("vulnerability",)
    sources = ("NIST NVD",)

    async def run(self, ctx):
        st, d = await ctx.get_json("https://services.nvd.nist.gov/rest/json/cves/2.0", params={"cveId": ctx.value})
        if st != 200 or not isinstance(d, dict):
            raise Skip(f"NVD HTTP {st}")
        vulns = d.get("vulnerabilities") or []
        if not vulns:
            return
        cve = vulns[0].get("cve") or {}
        desc = next((x.get("value") for x in cve.get("descriptions") or [] if x.get("lang") == "en"), None)
        metrics = cve.get("metrics") or {}
        score = severity = None
        for key in ("cvssMetricV40", "cvssMetricV31", "cvssMetricV30", "cvssMetricV2"):
            if metrics.get(key):
                data = metrics[key][0].get("cvssData") or {}
                score = data.get("baseScore")
                severity = data.get("baseSeverity") or metrics[key][0].get("baseSeverity")
                break
        published = (cve.get("published") or "")[:10]
        ctx.enrich({"description": desc, "cvss": score, "severity": severity, "published": published,
                    "_dates": [[f"{ctx.value} published", published]] if published else [],
                    "_links": [["NVD", f"https://nvd.nist.gov/vuln/detail/{ctx.value}"]]})


@register
class VirusTotal(Transform):
    name = "virustotal"
    title = L("To reputation [VirusTotal]", "A reputación [VirusTotal]")
    description = L("Detection stats, reputation and categories.", "Detecciones, reputación y categorías.")
    category = "threat"
    inputs = ("domain", "hostname", "ip", "url", "hash")
    keys = ("virustotal",)
    sources = ("VirusTotal",)

    async def run(self, ctx):
        key = ctx.require_key("virustotal")
        t, v = ctx.entity["type"], ctx.value
        if t in ("domain", "hostname"):
            path = f"domains/{v}"
        elif t == "ip":
            path = f"ip_addresses/{v}"
        elif t == "url":
            path = "urls/" + base64.urlsafe_b64encode(v.encode()).decode().rstrip("=")
        else:
            path = f"files/{v}"
        st, d = await ctx.get_json(f"https://www.virustotal.com/api/v3/{path}", headers={"x-apikey": key})
        if st == 404:
            ctx.log("Not in VirusTotal")
            return
        if st != 200 or not isinstance(d, dict):
            raise Skip(f"VirusTotal HTTP {st}")
        a = (d.get("data") or {}).get("attributes") or {}
        stats = a.get("last_analysis_stats") or {}
        ctx.enrich({"vt_malicious": stats.get("malicious"), "vt_suspicious": stats.get("suspicious"),
                    "vt_harmless": stats.get("harmless"), "vt_reputation": a.get("reputation"),
                    "vt_categories": sorted(set((a.get("categories") or {}).values())) or None,
                    "vt_tags": a.get("tags"), "vt_names": (a.get("names") or [])[:10] or None,
                    "_links": [["VirusTotal", f"https://www.virustotal.com/gui/search/{v}"]]})


@register
class ShodanHost(Transform):
    name = "shodan_host"
    title = L("To services and banners [Shodan]", "A servicios y banners [Shodan]")
    description = L("Full Shodan host report: services, products, OS, hostnames and CVEs.",
                    "Informe completo de Shodan: servicios, productos, SO, hosts y CVEs.")
    category = "threat"
    inputs = ("ip",)
    outputs = ("hostname", "domain", "vulnerability", "organization")
    keys = ("shodan",)
    sources = ("Shodan",)

    async def run(self, ctx):
        key = ctx.require_key("shodan")
        st, d = await ctx.get_json(f"https://api.shodan.io/shodan/host/{ctx.value}", params={"key": key})
        if st == 404:
            return
        if st != 200 or not isinstance(d, dict):
            raise Skip(f"Shodan HTTP {st}")
        services = [" ".join(str(x) for x in (s.get("port"), s.get("transport"), s.get("product"), s.get("version")) if x)
                    for s in d.get("data") or []]
        ctx.enrich({"open_ports": d.get("ports"), "services": services, "os": d.get("os"), "isp": d.get("isp"),
                    "last_update": (d.get("last_update") or "")[:10] or None})
        if d.get("org"):
            ctx.add("organization", d["org"], {"role": "network owner"}, label="owned by")
        for h in d.get("hostnames") or []:
            ctx.add("hostname", h, label="hostname")
        for dom in d.get("domains") or []:
            ctx.add("domain", registered_domain(dom), label="serves")
        for cve in (d.get("vulns") or [])[:50]:
            ctx.add("vulnerability", cve, label="vulnerable to")


@register
class AbuseIPDB(Transform):
    name = "abuseipdb"
    title = L("To abuse reports [AbuseIPDB]", "A denuncias de abuso [AbuseIPDB]")
    description = L("Abuse confidence score and reports in the last 90 days.",
                    "Puntuación de abuso y denuncias de los últimos 90 días.")
    category = "threat"
    inputs = ("ip",)
    keys = ("abuseipdb",)
    sources = ("AbuseIPDB",)

    async def run(self, ctx):
        key = ctx.require_key("abuseipdb")
        st, d = await ctx.get_json("https://api.abuseipdb.com/api/v2/check",
                                   params={"ipAddress": ctx.value, "maxAgeInDays": 90},
                                   headers={"Key": key, "Accept": "application/json"})
        if st != 200 or not isinstance(d, dict):
            raise Skip(f"AbuseIPDB HTTP {st}")
        a = d.get("data") or {}
        ctx.enrich({"abuse_score": a.get("abuseConfidenceScore"), "abuse_reports": a.get("totalReports"),
                    "usage_type": a.get("usageType"), "isp": a.get("isp"), "is_tor": a.get("isTor"),
                    "last_reported": (a.get("lastReportedAt") or "")[:10] or None,
                    "_links": [["AbuseIPDB", f"https://www.abuseipdb.com/check/{ctx.value}"]]})


@register
class UrlScan(Transform):
    name = "urlscan"
    title = L("To scanned pages [urlscan.io]", "A páginas escaneadas [urlscan.io]")
    description = L("Public urlscan.io scans of the domain or IP: URLs, IPs and servers seen.",
                    "Escaneos públicos de urlscan.io del dominio o IP: URLs, IPs y servidores vistos.")
    category = "threat"
    inputs = ("domain", "hostname", "ip")
    outputs = ("url", "ip", "domain")
    optional_keys = ("urlscan",)
    sources = ("urlscan.io",)

    async def run(self, ctx):
        field = "ip" if ctx.entity["type"] == "ip" else "domain"
        headers = {"API-Key": ctx.key("urlscan")} if ctx.key("urlscan") else {}
        st, d = await ctx.get_json("https://urlscan.io/api/v1/search/",
                                   params={"q": f"{field}:{ctx.value}", "size": min(ctx.limit, 100)}, headers=headers)
        if st == 429:
            raise Skip("urlscan.io rate limit (add a key in settings)")
        if st != 200 or not isinstance(d, dict):
            raise Skip(f"urlscan HTTP {st}")
        for res in d.get("results") or []:
            page, task = res.get("page") or {}, res.get("task") or {}
            date = (task.get("time") or "")[:10]
            props = {"scanned": date, "server": page.get("server"), "country": page.get("country"),
                     "asn": page.get("asn"), "_image": res.get("screenshot"),
                     "_links": [["urlscan result", f"https://urlscan.io/result/{res.get('_id')}/"]] if res.get("_id") else [],
                     "_dates": [["urlscan scan", date]] if date else []}
            if field == "domain" and page.get("url"):
                uid = ctx.add("url", page["url"], props, label="scanned page")
                if uid and page.get("ip"):
                    ctx.add("ip", page["ip"], label="served from", parent=uid)
            elif field == "ip" and page.get("domain"):
                dom = page["domain"].lower()
                etype = "domain" if registered_domain(dom) == dom else "hostname"
                ctx.add(etype, dom, label="hosted on", reverse=True)
