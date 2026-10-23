"""Web transforms: websites, page scraping, archives and security.txt."""

from __future__ import annotations

import re
from collections import Counter
from urllib.parse import quote, urljoin, urlparse

from ..entities import L, registered_domain
from ..webutil import parse_page, tech_from_response
from .base import Skip, Transform, register

MAX_PAGE_BYTES = 3_000_000
# link targets too generic to say anything about the owner of a page
NOISE_DOMAINS = {
    "google.com", "googleapis.com", "gstatic.com", "googletagmanager.com", "google-analytics.com", "doubleclick.net",
    "facebook.com", "fb.com", "twitter.com", "x.com", "instagram.com", "linkedin.com", "youtube.com", "youtu.be",
    "tiktok.com", "pinterest.com", "apple.com", "microsoft.com", "cloudflare.com", "jsdelivr.net", "unpkg.com",
    "cdnjs.com", "w3.org", "schema.org", "wordpress.org", "wordpress.com", "gravatar.com", "wp.com", "github.com",
    "bootstrapcdn.com", "fontawesome.com", "fonts.com", "typekit.net", "jquery.com", "t.me", "wa.me",
    "whatsapp.com", "reddit.com", "medium.com", "amazon.com", "amazonaws.com", "akamaihd.net", "bit.ly",
    "goo.gl", "vimeo.com", "spotify.com", "creativecommons.org", "mozilla.org", "openstreetmap.org",
}


async def fetch(ctx, url: str, max_bytes: int = MAX_PAGE_BYTES, hops: int = 6):
    """GET following redirects by hand so every hop passes the SSRF guard. Returns (response, text)."""
    for _ in range(hops):
        await ctx.assert_public(url)
        req = ctx.http.build_request("GET", url)
        r = await ctx.http.send(req, stream=True, follow_redirects=False)
        try:
            if r.is_redirect and r.headers.get("location"):
                url = urljoin(str(r.url), r.headers["location"])
                continue
            chunks, size = [], 0
            async for chunk in r.aiter_bytes():
                chunks.append(chunk)
                size += len(chunk)
                if size >= max_bytes:
                    break
            body = b"".join(chunks)
        finally:
            await r.aclose()
        return r, body.decode(r.encoding or "utf-8", "replace")
    raise Skip("Too many redirects")


@register
class ToWebsite(Transform):
    name = "to_website"
    title = L("To website", "A sitio web")
    description = L("Checks whether the name serves a website over HTTPS or HTTP.",
                    "Comprueba si el nombre sirve una web por HTTPS o HTTP.")
    category = "web"
    inputs = ("domain", "hostname")
    outputs = ("url",)
    sources = ("HTTP",)

    async def run(self, ctx):
        last_error = None
        for scheme in ("https", "http"):
            try:
                r, html = await fetch(ctx, f"{scheme}://{ctx.value}/", max_bytes=400_000)
            except Skip:
                raise
            except Exception as e:  # noqa: BLE001
                last_error = e
                continue
            title = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
            final = str(r.url)
            ctx.add("url", final, {"status": r.status_code, "title": " ".join(title.group(1).split())[:200] if title else None,
                                   "server": r.headers.get("server")}, label="website")
            final_host = (urlparse(final).hostname or "").lower()
            if final_host and final_host != ctx.value and registered_domain(final_host) != registered_domain(ctx.value):
                ctx.add("domain", registered_domain(final_host), label="redirects to")
            return
        raise Skip(f"No website answered ({type(last_error).__name__ if last_error else 'no response'})")


@register
class PageScan(Transform):
    name = "web_page_scan"
    title = L("To entities on the page", "A entidades de la página")
    description = L("Downloads the page and extracts emails, phones, social profiles, tracking codes, technologies "
                    "and the domains it links to.",
                    "Descarga la página y extrae correos, teléfonos, perfiles sociales, códigos de seguimiento, "
                    "tecnologías y los dominios a los que enlaza.")
    category = "web"
    inputs = ("url",)
    outputs = ("email", "phone", "account", "tracking_code", "domain")
    sources = ("HTTP",)

    async def run(self, ctx):
        r, html = await fetch(ctx, ctx.value)
        if r.status_code >= 400:
            ctx.enrich({"status": r.status_code})
            raise Skip(f"HTTP {r.status_code}")
        page = parse_page(html, str(r.url))
        ctx.enrich({"status": r.status_code, "title": page["title"], "description": page["description"],
                    "generator": page["generator"], "technologies": tech_from_response(r.headers, html),
                    "final_url": str(r.url) if str(r.url) != ctx.value else None})
        for code in page["tracking_codes"]:
            ctx.add("tracking_code", code, {"kind": _tracking_kind(code)}, label="uses")
        for email in page["emails"][:40]:
            ctx.add("email", email, label="mentions")
        for phone in page["phones"][:10]:
            ctx.add("phone", phone, label="mentions")
        for platform, handle, url in page["socials"][:40]:
            ctx.add("account", url, {"platform": platform, "username": handle, "_links": [["Profile", url]]},
                    label="links to profile")
        own = registered_domain(urlparse(str(r.url)).hostname or "")
        counts = Counter(registered_domain(urlparse(u).hostname or "") for u in page["external_links"])
        for dom, _ in counts.most_common(30):
            if dom and dom != own and dom not in NOISE_DOMAINS and "." in dom:
                ctx.add("domain", dom, label="links to")


def _tracking_kind(code: str) -> str:
    c = code.upper()
    if c.startswith("UA-"):
        return "Google Analytics (Universal)"
    if c.startswith("G-"):
        return "Google Analytics 4"
    if c.startswith("GTM-"):
        return "Google Tag Manager"
    return "Google AdSense"


@register
class UrlToHost(Transform):
    name = "url_to_host"
    title = L("To DNS name / domain", "A nombre DNS / dominio")
    description = L("Host part of a URL.", "Host de una URL.")
    category = "web"
    inputs = ("url",)
    outputs = ("domain", "hostname", "ip")

    async def run(self, ctx):
        host = (urlparse(ctx.value).hostname or "").lower()
        if not host:
            return
        if re.fullmatch(r"[\d.]+|[0-9a-f:]+", host):
            ctx.add("ip", host, label="hosted at", reverse=True)
        elif registered_domain(host) == host:
            ctx.add("domain", host, label="hosted at", reverse=True)
        else:
            ctx.add("hostname", host, label="hosted at", reverse=True)


@register
class Wayback(Transform):
    name = "wayback"
    title = L("To archive history [Wayback Machine]", "A historial archivado [Wayback Machine]")
    description = L("First and last capture in the Internet Archive.", "Primera y última captura en Internet Archive.")
    category = "web"
    inputs = ("domain", "hostname", "url")
    sources = ("Internet Archive",)

    async def run(self, ctx):
        target = ctx.value
        cdx = "https://web.archive.org/cdx/search/cdx"
        base = {"url": target, "output": "json", "fl": "timestamp,original,statuscode"}
        st, first = await ctx.get_json(cdx, params={**base, "limit": "1"})
        if st != 200:
            raise Skip(f"Wayback HTTP {st}")
        if not first or len(first) < 2:
            return
        _, last = await ctx.get_json(cdx, params={**base, "limit": "-1", "fastLatest": "true"})
        f = first[1][0]
        lst = last[-1][0] if isinstance(last, list) and len(last) >= 2 else f

        def iso(ts: str) -> str:
            return f"{ts[:4]}-{ts[4:6]}-{ts[6:8]}"

        ctx.enrich({"first_archived": iso(f), "last_archived": iso(lst),
                    "_dates": [["First archived", iso(f)], ["Last archived", iso(lst)]],
                    "_links": [["Wayback Machine", f"https://web.archive.org/web/*/{quote(target, safe=':/')}*"]]})


INTERESTING_EXT = re.compile(r"\.(pdf|docx?|xlsx?|pptx?|csv|sql|bak|zip|tar|gz|7z|rar|env|json|xml|log|conf|txt|key|pem)$", re.I)


@register
class WaybackUrls(Transform):
    name = "wayback_urls"
    title = L("To archived files [Wayback Machine]", "A ficheros archivados [Wayback Machine]")
    description = L("Archived URLs of the domain that look like documents, backups or config files.",
                    "URLs archivadas del dominio que parecen documentos, copias de seguridad o configuraciones.")
    category = "web"
    inputs = ("domain",)
    outputs = ("url",)
    sources = ("Internet Archive",)
    default = False
    timeout = 90

    async def run(self, ctx):
        st, rows = await ctx.get_json("https://web.archive.org/cdx/search/cdx", params={
            "url": f"{ctx.value}/*", "output": "json", "fl": "timestamp,original,mimetype", "collapse": "urlkey",
            "limit": "5000", "filter": "statuscode:200"}, timeout=80)
        if st != 200 or not isinstance(rows, list):
            raise Skip(f"Wayback HTTP {st}")
        for ts, original, mime in rows[1:]:
            path = urlparse(original).path
            if INTERESTING_EXT.search(path):
                date = f"{ts[:4]}-{ts[4:6]}-{ts[6:8]}"
                if ctx.add("url", original, {"mimetype": mime, "archived": date,
                                             "_links": [["Archived copy", f"https://web.archive.org/web/{ts}/{original}"]],
                                             "_dates": [["Archived", date]]}, label="archived file") is None:
                    break


@register
class SecurityTxt(Transform):
    name = "security_txt"
    title = L("To security contacts [security.txt]", "A contactos de seguridad [security.txt]")
    description = L("Contacts published in /.well-known/security.txt.", "Contactos publicados en /.well-known/security.txt.")
    category = "web"
    inputs = ("domain",)
    outputs = ("email", "url")
    sources = ("HTTP",)

    async def run(self, ctx):
        for path in ("/.well-known/security.txt", "/security.txt"):
            try:
                r, body = await fetch(ctx, f"https://{ctx.value}{path}", max_bytes=100_000)
            except Skip:
                raise
            except Exception:  # noqa: BLE001
                continue
            if r.status_code != 200 or "contact:" not in body.lower():
                continue
            props = {}
            for line in body.splitlines():
                k, _, v = line.partition(":")
                k, v = k.strip().lower(), v.strip()
                if k == "contact":
                    if v.lower().startswith("mailto:"):
                        ctx.add("email", v[7:], {"role": "security contact"}, label="security contact")
                    elif v.lower().startswith("http"):
                        ctx.add("url", v, label="security contact")
                elif k in ("policy", "expires", "preferred-languages", "hiring", "acknowledgments"):
                    props[k.replace("-", "_")] = v
            ctx.enrich(props)
            return
