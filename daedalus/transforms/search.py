"""Search-engine transforms and dork links."""

from __future__ import annotations

import re
from urllib.parse import quote_plus, urlparse

from ..entities import L
from ..webutil import ddg_unwrap, html_to_text
from .base import Skip, Transform, register

SEARCHABLE = ("person", "username", "email", "phone", "phrase", "organization", "tracking_code", "crypto", "hash",
              "domain")


def _host(url: str) -> str:
    return (urlparse(url).hostname or "").lower()


def query_for(entity: dict) -> str:
    v = entity["value"]
    if entity["type"] == "domain":
        return f'"{v}" -site:{v}'
    if entity["type"] == "phone":
        return f'"{v}" OR "{v.lstrip("+")}"'
    return f'"{v}"'


async def _serper(ctx, q: str, n: int) -> list[dict]:
    r = await ctx.http.post("https://google.serper.dev/search", json={"q": q, "num": min(n, 100)},
                            headers={"X-API-KEY": ctx.key("serper")})
    if r.status_code != 200:
        raise Skip(f"Serper HTTP {r.status_code}")
    return [{"url": x.get("link"), "title": x.get("title"), "snippet": x.get("snippet")}
            for x in r.json().get("organic") or []]


async def _brave(ctx, q: str, n: int) -> list[dict]:
    st, d = await ctx.get_json("https://api.search.brave.com/res/v1/web/search", params={"q": q, "count": min(n, 20)},
                               headers={"X-Subscription-Token": ctx.key("brave"), "Accept": "application/json"})
    if st != 200 or not isinstance(d, dict):
        raise Skip(f"Brave HTTP {st}")
    return [{"url": x.get("url"), "title": x.get("title"), "snippet": html_to_text(x.get("description") or "")}
            for x in (d.get("web") or {}).get("results") or []]


def parse_ddg(html: str) -> list[dict]:
    """Results of DuckDuckGo's HTML endpoint (ads and internal links dropped)."""
    out, seen = [], set()
    for chunk in re.split(r'(?=<a[^>]*class="result__a")', html)[1:]:
        tag = re.match(r'<a[^>]*>', chunk)
        href = re.search(r'href="([^"]+)"', tag.group(0)) if tag else None
        title = re.match(r'<a[^>]*>(.*?)</a>', chunk, re.S)
        if not href:
            continue
        url = ddg_unwrap(href.group(1))
        if not url.startswith("http") or _host(url).endswith("duckduckgo.com") or url in seen:
            continue
        seen.add(url)
        snippet = re.search(r'class="result__snippet"[^>]*>(.*?)</a>', chunk, re.S)
        out.append({"url": url, "title": html_to_text(title.group(1)) if title else None,
                    "snippet": html_to_text(snippet.group(1)) if snippet else None})
    return out


async def _ddg(ctx, q: str, n: int) -> list[dict]:
    r = await ctx.http.post("https://html.duckduckgo.com/html/", data={"q": q, "kl": "wt-wt"},
                            headers={"Referer": "https://html.duckduckgo.com/"})
    if r.status_code != 200:
        raise Skip(f"DuckDuckGo HTTP {r.status_code}")
    if "anomaly" in r.text.lower() and "result__a" not in r.text:
        raise Skip("DuckDuckGo asked for a captcha; add a Serper or Brave key for reliable search")
    return parse_ddg(r.text)[:n]


@register
class WebSearch(Transform):
    name = "web_search"
    title = L("To web mentions [search engine]", "A menciones web [buscador]")
    description = L("Pages that mention the value. Uses Serper (Google) or Brave when a key is set, otherwise "
                    "DuckDuckGo.",
                    "Páginas que mencionan el valor. Usa Serper (Google) o Brave si hay clave; si no, DuckDuckGo.")
    category = "search"
    inputs = SEARCHABLE
    outputs = ("url",)
    optional_keys = ("serper", "brave")
    sources = ("Serper", "Brave", "DuckDuckGo")

    async def run(self, ctx):
        q = query_for(ctx.entity)
        n = min(ctx.limit, 30)
        if ctx.key("serper"):
            results, engine = await _serper(ctx, q, n), "Google (Serper)"
        elif ctx.key("brave"):
            results, engine = await _brave(ctx, q, n), "Brave"
        else:
            results, engine = await _ddg(ctx, q, n), "DuckDuckGo"
        for r in results[:n]:
            if r.get("url"):
                ctx.add("url", r["url"], {"title": r.get("title"), "snippet": r.get("snippet"), "search_engine": engine,
                                          "query": q}, label="mentioned at", reverse=False)
        ctx.log(f"{min(len(results), n)} result(s) from {engine}")


DORKS = {
    "person": [("LinkedIn", 'site:linkedin.com/in "{v}"'), ("Documents", '"{v}" filetype:pdf OR filetype:docx'),
               ("Social", '"{v}" site:facebook.com OR site:instagram.com OR site:x.com'),
               ("News", '"{v}" site:news.google.com')],
    "username": [("Pastes", '"{v}" site:pastebin.com OR site:ghostbin.com OR site:rentry.co'),
                 ("Forums", '"{v}" inurl:forum OR inurl:thread OR inurl:member'),
                 ("Code", '"{v}" site:github.com OR site:gitlab.com')],
    "email": [("Pastes", '"{v}" site:pastebin.com'), ("Documents", '"{v}" filetype:pdf OR filetype:xlsx OR filetype:csv'),
              ("Exact", '"{v}"')],
    "phone": [("Exact", '"{v}"'), ("Ads", '"{v}" site:olx.com OR site:mercadolibre.com OR site:milanuncios.com')],
    "domain": [("Subdomains", "site:*.{v} -www"), ("Files", "site:{v} filetype:pdf OR filetype:doc OR filetype:xls"),
               ("Login pages", "site:{v} inurl:login OR inurl:admin OR inurl:signin"),
               ("Exposed configs", "site:{v} ext:env OR ext:log OR ext:sql OR ext:bak OR ext:conf"),
               ("Pastes", '"{v}" site:pastebin.com')],
    "organization": [("Employees", 'site:linkedin.com/in "{v}"'), ("Documents", '"{v}" filetype:pdf')],
    "phrase": [("Exact", '"{v}"')],
}


@register
class DorkLinks(Transform):
    name = "dork_links"
    title = L("To search dorks (links)", "A dorks de búsqueda (enlaces)")
    description = L("Ready-made Google / Bing / DuckDuckGo / Yandex queries attached to the entity for manual review.",
                    "Consultas preparadas de Google / Bing / DuckDuckGo / Yandex que se adjuntan a la entidad "
                    "para revisarlas a mano.")
    category = "search"
    inputs = tuple(DORKS)
    default = False

    async def run(self, ctx):
        links = []
        for name, tpl in DORKS[ctx.entity["type"]]:
            q = quote_plus(tpl.format(v=ctx.value))
            links += [[f"Google · {name}", f"https://www.google.com/search?q={q}"],
                      [f"Bing · {name}", f"https://www.bing.com/search?q={q}"]]
        q = quote_plus(f'"{ctx.value}"')
        links += [["DuckDuckGo", f"https://duckduckgo.com/?q={q}"], ["Yandex", f"https://yandex.com/search/?text={q}"]]
        ctx.enrich({"_links": links})


@register
class Wikidata(Transform):
    name = "wikidata"
    title = L("To Wikidata entries", "A entradas de Wikidata")
    description = L("Matching items in Wikidata (public figures, companies, places).",
                    "Elementos coincidentes en Wikidata (personajes públicos, empresas, lugares).")
    category = "search"
    inputs = ("person", "organization", "location")
    outputs = ("url",)
    sources = ("Wikidata",)

    async def run(self, ctx):
        st, d = await ctx.get_json("https://www.wikidata.org/w/api.php", params={
            "action": "wbsearchentities", "search": ctx.value, "language": "en", "uselang": "en", "format": "json",
            "limit": min(ctx.limit, 10)})
        if st != 200 or not isinstance(d, dict):
            raise Skip(f"Wikidata HTTP {st}")
        for item in d.get("search") or []:
            url = item.get("concepturi") or f"https://www.wikidata.org/wiki/{item.get('id')}"
            ctx.add("url", url, {"title": item.get("label"), "description": item.get("description"),
                                 "wikidata_id": item.get("id")}, label="described at")
