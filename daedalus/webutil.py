"""Helpers shared by transforms: HTML scraping, social profile URLs and DNS."""

from __future__ import annotations

import asyncio
import html as htmllib
import re
from urllib.parse import parse_qs, unquote, urljoin, urlparse

import dns.exception
import dns.name
import dns.resolver
import dns.reversename

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,24}")
PHONE_RE = re.compile(r"(?<![\w+])(\+\d[\d\s().\-]{7,18}\d)(?![\d])")
TRACKING_RE = re.compile(r"\b(UA-\d{4,10}-\d{1,4}|G-[A-Z0-9]{8,12}|GTM-[A-Z0-9]{4,9}|ca-pub-\d{10,20})\b")
_IGNORED_EMAIL_SUFFIX = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".css", ".js", ".woff", ".woff2")
_IGNORED_EMAIL_DOMAINS = ("example.com", "example.org", "domain.com", "email.com", "sentry.io", "wixpress.com",
                          "sentry-next.wixpress.com", "yourdomain.com")

# (platform, regex capturing the handle, canonical URL template)
SOCIAL_PATTERNS: list[tuple[str, re.Pattern, str]] = [
    ("X", re.compile(r"^https?://(?:www\.|mobile\.)?(?:twitter|x)\.com/(?!share|intent|home|search|hashtag|i/|privacy|tos)([A-Za-z0-9_]{1,15})/?$", re.I), "https://x.com/{}"),
    ("Instagram", re.compile(r"^https?://(?:www\.)?instagram\.com/(?!p/|reel/|explore/|accounts/|stories/)([A-Za-z0-9_.]{1,30})/?$", re.I), "https://www.instagram.com/{}"),
    ("Facebook", re.compile(r"^https?://(?:www\.|m\.|[a-z]{2}-[a-z]{2}\.)?facebook\.com/(?!sharer|share|dialog|plugins|tr\b|groups/|events/|pages/|profile\.php)([A-Za-z0-9.\-]{2,50})/?$", re.I), "https://www.facebook.com/{}"),
    ("LinkedIn", re.compile(r"^https?://(?:[a-z]{2,3}\.)?linkedin\.com/(?:in|company)/([A-Za-z0-9\-_%]{2,100})/?$", re.I), "https://www.linkedin.com/in/{}"),
    ("GitHub", re.compile(r"^https?://(?:www\.)?github\.com/(?!sponsors|orgs|features|about|login|topics|marketplace|apps|site|security|pricing)([A-Za-z0-9\-]{1,39})/?$", re.I), "https://github.com/{}"),
    ("GitLab", re.compile(r"^https?://(?:www\.)?gitlab\.com/(?!explore|help|users/sign_in)([A-Za-z0-9_.\-]{2,255})/?$", re.I), "https://gitlab.com/{}"),
    ("YouTube", re.compile(r"^https?://(?:www\.)?youtube\.com/@([A-Za-z0-9_\-.]{2,100})/?$", re.I), "https://www.youtube.com/@{}"),
    ("TikTok", re.compile(r"^https?://(?:www\.)?tiktok\.com/@([A-Za-z0-9_.]{2,24})/?$", re.I), "https://www.tiktok.com/@{}"),
    ("Telegram", re.compile(r"^https?://(?:t\.me|telegram\.me)/(?!share|joinchat|s/|\+)([A-Za-z0-9_]{5,32})/?$", re.I), "https://t.me/{}"),
    ("Twitch", re.compile(r"^https?://(?:www\.)?twitch\.tv/([A-Za-z0-9_]{3,25})/?$", re.I), "https://www.twitch.tv/{}"),
    ("Reddit", re.compile(r"^https?://(?:www\.|old\.)?reddit\.com/(?:u|user)/([A-Za-z0-9_\-]{3,20})/?$", re.I), "https://www.reddit.com/user/{}"),
    ("Bluesky", re.compile(r"^https?://bsky\.app/profile/([A-Za-z0-9.\-]{3,100})/?$", re.I), "https://bsky.app/profile/{}"),
    ("Threads", re.compile(r"^https?://(?:www\.)?threads\.(?:net|com)/@([A-Za-z0-9_.]{1,30})/?$", re.I), "https://www.threads.net/@{}"),
    ("Mastodon", re.compile(r"^https?://([a-z0-9.\-]+\.[a-z]{2,})/@([A-Za-z0-9_]{1,30})/?$", re.I), ""),
    ("Medium", re.compile(r"^https?://(?:www\.)?medium\.com/@([A-Za-z0-9_.\-]{1,50})/?$", re.I), "https://medium.com/@{}"),
    ("Keybase", re.compile(r"^https?://keybase\.io/([A-Za-z0-9_]{2,16})/?$", re.I), "https://keybase.io/{}"),
    ("Pinterest", re.compile(r"^https?://(?:[a-z]{2}\.|www\.)?pinterest\.[a-z.]+/([A-Za-z0-9_]{3,30})/?$", re.I), "https://www.pinterest.com/{}"),
    ("Discord", re.compile(r"^https?://(?:www\.)?(?:discord\.gg|discord\.com/invite)/([A-Za-z0-9\-]{2,32})/?$", re.I), "https://discord.gg/{}"),
]


def social_from_url(url: str) -> tuple[str, str, str] | None:
    """(platform, handle, canonical url) if the URL is a social profile."""
    u = url.split("?")[0].split("#")[0]
    for platform, rx, tpl in SOCIAL_PATTERNS:
        m = rx.match(u)
        if not m:
            continue
        if platform == "Mastodon":
            host, handle = m.group(1), m.group(2)
            return platform, f"{handle}@{host}", f"https://{host}/@{handle}"
        handle = unquote(m.group(1))
        return platform, handle, tpl.format(handle)
    return None


def clean_emails(text: str) -> list[str]:
    out: list[str] = []
    for e in EMAIL_RE.findall(text or ""):
        e = e.strip(".").lower()
        domain = e.rsplit("@", 1)[-1]
        if e.endswith(_IGNORED_EMAIL_SUFFIX) or domain in _IGNORED_EMAIL_DOMAINS or e in out:
            continue
        if re.match(r"^[0-9a-f]{24,}@", e):  # hashed tracking addresses
            continue
        out.append(e)
    return out


def html_to_text(html: str) -> str:
    text = re.sub(r"<script.*?</script>|<style.*?</style>|<noscript.*?</noscript>", " ", html or "", flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    return " ".join(htmllib.unescape(text).split())


def meta_tag(html: str, name: str) -> str | None:
    m = re.search(
        rf'<meta[^>]+(?:name|property)=["\']{re.escape(name)}["\'][^>]*content=["\']([^"\']*)["\']', html, re.I
    ) or re.search(rf'<meta[^>]+content=["\']([^"\']*)["\'][^>]*(?:name|property)=["\']{re.escape(name)}["\']', html, re.I)
    return htmllib.unescape(m.group(1)).strip() or None if m else None


def parse_page(html: str, base_url: str) -> dict:
    """Title, metadata, emails, phones, social profiles, outbound links and tracking codes of a page."""
    title = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
    links: list[str] = []
    for h in re.findall(r'href=["\']([^"\']+)["\']', html, re.I):
        h = htmllib.unescape(h).strip()
        if h.startswith(("mailto:", "tel:", "javascript:", "#")):
            continue
        full = urljoin(base_url, h)
        if full.startswith("http") and full not in links:
            links.append(full)
    mailtos = [htmllib.unescape(m).split("?")[0] for m in re.findall(r'mailto:([^"\'>\s]+)', html, re.I)]
    tels = [htmllib.unescape(t) for t in re.findall(r'href=["\']tel:([^"\']+)["\']', html, re.I)]
    socials: list[tuple[str, str, str]] = []
    seen_social = set()
    for ln in links:
        s = social_from_url(ln)
        if s and (s[0], s[1].lower()) not in seen_social:
            seen_social.add((s[0], s[1].lower()))
            socials.append(s)
    text = html_to_text(html)
    base_host = (urlparse(base_url).hostname or "").lower()
    phones = []
    for p in tels + PHONE_RE.findall(text):
        digits = re.sub(r"[^\d+]", "", p)
        if 8 <= len(digits.lstrip("+")) <= 15 and digits not in phones:
            phones.append(digits)
    return {
        "title": " ".join(htmllib.unescape(title.group(1)).split())[:200] if title else None,
        "description": meta_tag(html, "description") or meta_tag(html, "og:description"),
        "generator": meta_tag(html, "generator"),
        "site_name": meta_tag(html, "og:site_name"),
        "emails": clean_emails(" ".join(mailtos) + " " + text),
        "phones": phones[:20],
        "socials": socials,
        "tracking_codes": sorted(set(TRACKING_RE.findall(html))),
        "external_links": [ln for ln in links if (urlparse(ln).hostname or "").lower() not in ("", base_host)],
    }


def tech_from_response(headers, html: str) -> list[str]:
    tech = []
    for h in ("server", "x-powered-by", "x-generator", "x-aspnet-version", "x-drupal-cache", "x-shopify-stage"):
        if headers.get(h):
            tech.append(f"{h}: {headers[h]}")
    lower = (html or "").lower()
    hints = {
        "WordPress": "wp-content/", "Shopify": "cdn.shopify.com", "Wix": "static.wixstatic.com",
        "Squarespace": "squarespace", "Drupal": "drupal-settings-json", "Joomla": "/media/jui/",
        "Next.js": "__next_data__", "Nuxt": "__nuxt", "Gatsby": "___gatsby", "React": "data-reactroot",
        "Google Analytics": "google-analytics.com", "Google Tag Manager": "googletagmanager.com",
        "Cloudflare": "cdn-cgi/", "jQuery": "jquery", "Bootstrap": "bootstrap", "Hugo": "gohugo",
        "Ghost": "ghost-", "Webflow": "webflow", "HubSpot": "js.hs-scripts.com", "Matomo": "matomo",
    }
    tech += [name for name, needle in hints.items() if needle in lower]
    if "cf-ray" in headers:
        tech.append("Cloudflare")
    return list(dict.fromkeys(tech))


def ddg_unwrap(href: str) -> str:
    """DuckDuckGo HTML results wrap targets in /l/?uddg=<url>."""
    href = htmllib.unescape(href)
    if href.startswith("//"):
        href = "https:" + href
    parsed = urlparse(href)
    if parsed.hostname and parsed.hostname.endswith("duckduckgo.com") and parsed.path.startswith("/l/"):
        target = parse_qs(parsed.query).get("uddg")
        if target:
            return unquote(target[0])
    return href


# ------------------------------------------------------------------------- DNS
_resolver = dns.resolver.Resolver(configure=False)
_resolver.nameservers = ["1.1.1.1", "8.8.8.8", "9.9.9.9"]
_resolver.lifetime = 8.0
try:
    _system = dns.resolver.Resolver(configure=True)
    if _system.nameservers:
        _resolver.nameservers = list(_system.nameservers) + _resolver.nameservers
except (dns.resolver.NoResolverConfiguration, OSError):
    pass


def _resolve(name: str, rtype: str) -> list[str]:
    try:
        return [r.to_text().strip('"') for r in _resolver.resolve(name, rtype)]
    except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer, dns.resolver.NoNameservers, dns.exception.Timeout,
            dns.name.EmptyLabel, dns.name.LabelTooLong, dns.resolver.YXDOMAIN):
        return []


async def resolve(name: str, rtype: str) -> list[str]:
    return await asyncio.to_thread(_resolve, name, rtype)


async def reverse_dns(ip: str) -> list[str]:
    try:
        name = dns.reversename.from_address(ip).to_text()
    except (dns.exception.SyntaxError, ValueError):
        return []
    return [h.rstrip(".") for h in await resolve(name, "PTR")]
