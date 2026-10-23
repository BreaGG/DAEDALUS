"""Alias transforms: account sweep across sites and rich public profiles."""

from __future__ import annotations

import asyncio
import json
import random
import re
import string
import time
from datetime import datetime, timezone

import httpx

from ..config import RESOURCES_DIR
from ..entities import L
from ..webutil import html_to_text
from .base import Skip, Transform, register

SHERLOCK_URL = "https://raw.githubusercontent.com/sherlock-project/sherlock/master/sherlock_project/resources/data.json"
WAF_MARKERS = ("cf-browser-verification", "challenge-platform", "Just a moment...", "captcha-delivery",
               "Attention Required! | Cloudflare", "px-captcha", "/_Incapsula_Resource")


def _as_list(x) -> list:
    if x is None:
        return []
    return x if isinstance(x, list) else [x]


def _date(value) -> str | None:
    if value in (None, ""):
        return None
    try:
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(value / (1000 if value > 1e11 else 1), tz=timezone.utc).strftime("%Y-%m-%d")
        return str(value)[:10] if re.match(r"\d{4}-\d{2}-\d{2}", str(value)) else None
    except (OverflowError, OSError, ValueError):
        return None


def builtin_sites() -> dict:
    return json.loads((RESOURCES_DIR / "sites.json").read_text(encoding="utf-8"))


_sherlock_cache: tuple[float, dict] | None = None


async def load_sites(ctx) -> dict:
    """Built-in list, plus the Sherlock project's database when enabled (cached for a day)."""
    global _sherlock_cache
    sites = builtin_sites()
    if not ctx.settings.get("sherlock_db"):
        return sites
    if _sherlock_cache and time.time() - _sherlock_cache[0] < 86400:
        extra = _sherlock_cache[1]
    else:
        cache = ctx.engine.data_dir / "sherlock.json"
        extra = {}
        try:
            r = await ctx.http.get(SHERLOCK_URL, timeout=30)
            if r.status_code == 200:
                extra = r.json()
                cache.write_text(r.text, encoding="utf-8")
        except (httpx.HTTPError, ValueError, OSError):
            pass
        if not extra and cache.exists():
            try:
                extra = json.loads(cache.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                extra = {}
        extra = {k: v for k, v in extra.items() if isinstance(v, dict) and v.get("url") and v.get("errorType")}
        _sherlock_cache = (time.time(), extra)
    lowered = {k.lower() for k in sites}
    for name, site in extra.items():
        if name.lower() not in lowered:
            sites[name] = site
    return sites


async def check_site(http: httpx.AsyncClient, site: dict, username: str, timeout: float) -> str:
    """'found' | 'missing' | 'blocked' | 'error' | 'invalid' (Sherlock-compatible site format)."""
    rx = site.get("regexCheck")
    if rx:
        try:
            if not re.search(rx, username):
                return "invalid"
        except re.error:
            pass
    url = (site.get("urlProbe") or site["url"]).replace("{}", username)
    payload = site.get("request_payload")
    if payload is not None:
        payload = json.loads(json.dumps(payload).replace("{}", username))
    types = _as_list(site.get("errorType"))
    try:
        r = await http.request((site.get("request_method") or "GET").upper(), url, json=payload,
                               headers=site.get("headers") or None, timeout=timeout,
                               follow_redirects="response_url" not in types)
    except (httpx.HTTPError, ValueError):
        return "error"
    text = r.text[:2_000_000]
    if r.status_code in (403, 429, 503) or any(m in text for m in WAF_MARKERS):
        return "blocked"
    for t in types:
        if t == "message":
            if any(m and m in text for m in _as_list(site.get("errorMsg"))):
                return "missing"
            if r.status_code >= 400:
                return "missing"
        elif t == "status_code":
            if r.status_code in _as_list(site.get("errorCode")) or not 200 <= r.status_code < 300:
                return "missing"
        elif t == "response_url":
            if not 200 <= r.status_code < 300:
                return "missing"
    return "found"


def _random_username(site: dict) -> str:
    rx = site.get("regexCheck")
    cand = "zq" + "".join(random.choices(string.ascii_lowercase, k=11))
    for _ in range(6):
        try:
            if not rx or re.search(rx, cand):
                return cand
        except re.error:
            return cand
        cand = "zq" + "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
    return cand


@register
class UsernameSweep(Transform):
    name = "username_sweep"
    title = L("To accounts [site sweep]", "A cuentas [barrido de sitios]")
    description = L(
        "Checks the alias on ~75 sites (400+ with the Sherlock database enabled in settings). Every hit is "
        "double-checked against a random alias to discard sites that answer 'yes' to everything.",
        "Comprueba el alias en ~75 sitios (400+ con la base de Sherlock activada en ajustes). Cada acierto se "
        "contrasta con un alias aleatorio para descartar sitios que responden «sí» a todo.",
    )
    category = "social"
    inputs = ("username",)
    outputs = ("account",)
    sources = ("75+ sites", "Sherlock DB (optional)")
    timeout = 180

    async def run(self, ctx):
        sites = await load_sites(ctx)
        nsfw = ctx.settings.get("include_nsfw", False)
        sites = {n: s for n, s in sites.items() if nsfw or not s.get("isNSFW")}
        user = ctx.value
        per_request = float(ctx.settings.get("username_timeout", 12))
        sem = asyncio.Semaphore(25)
        unverified: dict[str, str] = {}
        hits: list[tuple[str, str]] = []

        async def one(name, site):
            async with sem:
                res = await check_site(ctx.http, site, user, per_request)
                url = site["url"].replace("{}", user)
                if res == "found":
                    control = await check_site(ctx.http, site, _random_username(site), per_request)
                    if control != "found":
                        hits.append((name, url))
                elif res in ("blocked", "error"):
                    unverified[name] = url

        await asyncio.gather(*(one(n, s) for n, s in sites.items()))
        for name, url in sorted(hits):
            ctx.add("account", url, {"platform": name, "username": user, "category": sites[name].get("category"),
                                     "verification": "exists (checked against a random alias)",
                                     "_links": [["Profile", url]]}, label="has account")
        ctx.enrich({"sites_checked": len(sites), "accounts_found": len(hits),
                    "_unverified": [[n, u] for n, u in sorted(unverified.items())]})
        ctx.log(f"{len(hits)} account(s) on {len(sites)} sites" + (f" · {len(unverified)} could not be verified"
                                                                    if unverified else ""))


# ----------------------------------------------------------------- rich profiles
def _profile(platform, username, url, **kw) -> dict:
    return {"platform": platform, "username": username, "url": url, **kw}


async def p_gitlab(ctx, u):
    st, d = await ctx.get_json("https://gitlab.com/api/v4/users", params={"username": u})
    if st != 200 or not d:
        return None
    st, full = await ctx.get_json(f"https://gitlab.com/api/v4/users/{d[0]['id']}")
    full = full if st == 200 and isinstance(full, dict) else d[0]
    linked = [("LinkedIn", full.get("linkedin")), ("X", full.get("twitter")), ("Discord", full.get("discord"))]
    return _profile("GitLab", full.get("username"), full.get("web_url"), name=full.get("name"),
                    bio=full.get("bio"), location=full.get("location"), avatar=full.get("avatar_url"),
                    created=_date(full.get("created_at")), emails=[full.get("public_email")],
                    urls=[full.get("website_url")], organization=full.get("organization"),
                    linked=[(p, h, None) for p, h in linked if h])


async def p_keybase(ctx, u):
    st, d = await ctx.get_json("https://keybase.io/_/api/1.0/user/lookup.json",
                               params={"usernames": u, "fields": "basics,profile,proofs_summary,pictures"})
    them = (d or {}).get("them") if isinstance(d, dict) else None
    if st != 200 or not them or not them[0]:
        return None
    t = them[0]
    prof = t.get("profile") or {}
    services = {"twitter": ("X", "https://x.com/{}"), "github": ("GitHub", "https://github.com/{}"),
                "reddit": ("Reddit", "https://www.reddit.com/user/{}"),
                "hackernews": ("Hacker News", "https://news.ycombinator.com/user?id={}"),
                "facebook": ("Facebook", "https://www.facebook.com/{}")}
    linked, urls, domains = [], [], []
    for p in (t.get("proofs_summary") or {}).get("all") or []:
        kind, tag = p.get("proof_type"), p.get("nametag")
        if kind in services:
            linked.append((services[kind][0], tag, services[kind][1].format(tag)))
        elif kind == "dns":
            domains.append(tag)
        elif kind in ("generic_web_site", "https", "http"):
            urls.append(p.get("service_url") or f"https://{tag}")
    name = t["basics"]["username"]
    return _profile("Keybase", name, f"https://keybase.io/{name}", name=prof.get("full_name"), bio=prof.get("bio"),
                    location=prof.get("location"), avatar=((t.get("pictures") or {}).get("primary") or {}).get("url"),
                    linked=linked, urls=urls, domains=domains)


async def p_hackernews(ctx, u):
    st, d = await ctx.get_json(f"https://hacker-news.firebaseio.com/v0/user/{u}.json")
    if st != 200 or not isinstance(d, dict):
        return None
    return _profile("Hacker News", d["id"], f"https://news.ycombinator.com/user?id={d['id']}",
                    bio=html_to_text(d.get("about") or ""), created=_date(d.get("created")),
                    extra={"karma": d.get("karma")})


async def p_bluesky(ctx, u):
    actor = u if "." in u else f"{u}.bsky.social"
    st, d = await ctx.get_json("https://public.api.bsky.app/xrpc/app.bsky.actor.getProfile", params={"actor": actor})
    if st != 200 or not isinstance(d, dict) or not d.get("handle"):
        return None
    return _profile("Bluesky", d["handle"], f"https://bsky.app/profile/{d['handle']}", name=d.get("displayName"),
                    bio=d.get("description"), avatar=d.get("avatar"), created=_date(d.get("createdAt")),
                    extra={"followers": d.get("followersCount"), "posts": d.get("postsCount"), "did": d.get("did")})


async def p_mastodon(ctx, u):
    st, d = await ctx.get_json("https://mastodon.social/api/v1/accounts/lookup", params={"acct": u})
    if st != 200 or not isinstance(d, dict) or not d.get("url"):
        return None
    fields = {f.get("name"): html_to_text(f.get("value") or "") for f in d.get("fields") or []}
    urls = [v for v in fields.values() if v.startswith("http")]
    return _profile("Mastodon", d.get("acct"), d["url"], name=d.get("display_name"), bio=html_to_text(d.get("note") or ""),
                    avatar=d.get("avatar"), created=_date(d.get("created_at")), urls=urls,
                    extra={"followers": d.get("followers_count"), "fields": fields or None})


async def p_reddit(ctx, u):
    st, d = await ctx.get_json(f"https://www.reddit.com/user/{u}/about.json")
    data = (d or {}).get("data") if isinstance(d, dict) else None
    if st != 200 or not data or data.get("is_suspended"):
        return None
    sub = data.get("subreddit") or {}
    return _profile("Reddit", data.get("name"), f"https://www.reddit.com/user/{data.get('name')}",
                    name=sub.get("title"), bio=sub.get("public_description"),
                    avatar=(data.get("icon_img") or "").split("?")[0] or None, created=_date(data.get("created_utc")),
                    extra={"karma": (data.get("link_karma") or 0) + (data.get("comment_karma") or 0)})


async def p_chesscom(ctx, u):
    st, d = await ctx.get_json(f"https://api.chess.com/pub/player/{u.lower()}")
    if st != 200 or not isinstance(d, dict) or not d.get("username"):
        return None
    country = (d.get("country") or "").rsplit("/", 1)[-1]
    return _profile("Chess.com", d["username"], d.get("url") or f"https://www.chess.com/member/{d['username']}",
                    name=d.get("name"), location=d.get("location"), avatar=d.get("avatar"),
                    created=_date(d.get("joined")), extra={"country_code": country or None,
                                                           "last_online": _date(d.get("last_online"))})


async def p_lichess(ctx, u):
    st, d = await ctx.get_json(f"https://lichess.org/api/user/{u}")
    if st != 200 or not isinstance(d, dict) or d.get("disabled"):
        return None
    prof = d.get("profile") or {}
    name = " ".join(x for x in (prof.get("firstName"), prof.get("lastName")) if x) or prof.get("realName")
    links = [x.strip() for x in str(prof.get("links") or "").split() if x.startswith("http")]
    return _profile("Lichess", d.get("username"), d.get("url") or f"https://lichess.org/@/{u}", name=name,
                    bio=prof.get("bio"), location=prof.get("location"), created=_date(d.get("createdAt")), urls=links,
                    extra={"country_code": prof.get("country") or prof.get("flag")})


async def p_telegram(ctx, u):
    if not re.match(r"^[A-Za-z][A-Za-z0-9_]{4,31}$", u):
        return None
    r = await ctx.http.get(f"https://t.me/{u}")
    html = r.text
    if r.status_code != 200 or "tgme_page_title" not in html:
        return None
    title = re.search(r'<div class="tgme_page_title"[^>]*>\s*<span[^>]*>(.*?)</span>', html, re.S)
    desc = re.search(r'<div class="tgme_page_description[^"]*"[^>]*>(.*?)</div>', html, re.S)
    extra = re.search(r'<div class="tgme_page_extra">(.*?)</div>', html, re.S)
    photo = re.search(r'<img class="tgme_page_photo_image" src="([^"]+)"', html)
    return _profile("Telegram", u, f"https://t.me/{u}", name=html_to_text(title.group(1)) if title else None,
                    bio=html_to_text(desc.group(1)) if desc else None, avatar=photo.group(1) if photo else None,
                    extra={"info": html_to_text(extra.group(1)) if extra else None})


async def p_x(ctx, u):
    if not re.match(r"^[A-Za-z0-9_]{1,15}$", u):
        return None
    st, d = await ctx.get_json(f"https://api.fxtwitter.com/{u}")
    user = (d or {}).get("user") if isinstance(d, dict) else None
    if st != 200 or not user:
        return None
    joined = None
    try:
        joined = datetime.strptime(user.get("joined") or "", "%a %b %d %H:%M:%S %z %Y").strftime("%Y-%m-%d")
    except ValueError:
        pass
    site = user.get("website")
    site = site.get("url") if isinstance(site, dict) else site
    return _profile("X", user.get("screen_name") or u, f"https://x.com/{user.get('screen_name') or u}",
                    name=user.get("name"), bio=user.get("description"), location=user.get("location"),
                    avatar=user.get("avatar_url"), created=joined, urls=[site] if site else [],
                    extra={"followers": user.get("followers"), "tweets": user.get("tweets")})


PROFILE_FETCHERS = {"GitLab": p_gitlab, "Keybase": p_keybase, "Hacker News": p_hackernews, "Bluesky": p_bluesky,
                    "Mastodon": p_mastodon, "Reddit": p_reddit, "Chess.com": p_chesscom, "Lichess": p_lichess,
                    "Telegram": p_telegram, "X": p_x}


def add_profile(ctx, p: dict) -> str | None:
    props = {"platform": p["platform"], "username": p.get("username"), "display_name": p.get("name"),
             "bio": p.get("bio"), "location": p.get("location"), "created": p.get("created"),
             "_image": p.get("avatar"), "_links": [["Profile", p["url"]]],
             "_dates": [[f"{p['platform']} account created", p["created"]]] if p.get("created") else []}
    props.update({k: v for k, v in (p.get("extra") or {}).items() if v not in (None, "", [], {})})
    acc = ctx.add("account", p["url"], props, label="has account")
    if not acc:
        return None
    name = (p.get("name") or "").strip()
    if " " in name and len(name) <= 60 and not re.search(r"[|@#/\\]|https?:", name):
        ctx.add("person", name, label="name", parent=acc)
    if p.get("location"):
        ctx.add("location", p["location"], label="lives in", parent=acc)
    if p.get("organization"):
        ctx.add("organization", p["organization"], label="works at", parent=acc)
    for email in p.get("emails") or []:
        if email:
            ctx.add("email", email, label="public email", parent=acc)
    for url in p.get("urls") or []:
        if url:
            ctx.add("url", url if url.startswith("http") else f"https://{url}", label="website", parent=acc)
    for dom in p.get("domains") or []:
        ctx.add("domain", dom, label="proves domain", parent=acc)
    for platform, handle, url in p.get("linked") or []:
        if url:
            ctx.add("account", url, {"platform": platform, "username": handle, "_links": [["Profile", url]]},
                    label="linked account", parent=acc)
        elif handle:
            ctx.add("username", handle.lstrip("@"), {"platform_hint": platform}, label=f"{platform} handle", parent=acc)
    return acc


@register
class UsernameProfiles(Transform):
    name = "username_profiles"
    title = L("To detailed profiles", "A perfiles detallados")
    description = L("Rich public profiles (name, bio, location, links, creation date) from GitLab, Keybase, "
                    "Hacker News, Bluesky, Mastodon, Reddit, Chess.com, Lichess, Telegram and X.",
                    "Perfiles públicos completos (nombre, bio, ubicación, enlaces, fecha de alta) de GitLab, Keybase, "
                    "Hacker News, Bluesky, Mastodon, Reddit, Chess.com, Lichess, Telegram y X.")
    category = "social"
    inputs = ("username",)
    outputs = ("account", "person", "location", "url", "email", "domain")
    sources = tuple(PROFILE_FETCHERS)
    timeout = 90

    async def run(self, ctx):
        async def safe(name, fn):
            try:
                return await fn(ctx, ctx.value)
            except (httpx.HTTPError, ValueError, KeyError, TypeError, IndexError):
                return None

        results = await asyncio.gather(*(safe(n, f) for n, f in PROFILE_FETCHERS.items()))
        found = [p for p in results if p and p.get("url")]
        for p in found:
            add_profile(ctx, p)
        ctx.log(f"{len(found)} profile(s): {', '.join(p['platform'] for p in found)}" if found else "No profiles")


@register
class GitHubProfile(Transform):
    name = "github_profile"
    title = L("To GitHub profile and commit emails", "A perfil de GitHub y correos de commits")
    description = L("Profile data plus the author emails leaked in public commits.",
                    "Datos del perfil y los correos de autor que aparecen en sus commits públicos.")
    category = "social"
    inputs = ("username",)
    outputs = ("account", "person", "organization", "location", "url", "email")
    optional_keys = ("github",)
    sources = ("GitHub API",)
    timeout = 60

    async def run(self, ctx):
        headers = {"Accept": "application/vnd.github+json"}
        if ctx.key("github"):
            headers["Authorization"] = f"Bearer {ctx.key('github')}"
        st, d = await ctx.get_json(f"https://api.github.com/users/{ctx.value}", headers=headers)
        if st == 404:
            return
        if st in (403, 429):
            raise Skip("GitHub rate limit reached (add a token in settings)")
        if st != 200 or not isinstance(d, dict):
            raise Skip(f"GitHub HTTP {st}")
        login = d["login"]
        company = (d.get("company") or "").strip().lstrip("@") or None
        p = _profile("GitHub", login, d.get("html_url") or f"https://github.com/{login}", name=d.get("name"),
                     bio=d.get("bio"), location=d.get("location"), avatar=d.get("avatar_url"),
                     created=_date(d.get("created_at")), emails=[d.get("email")], organization=company,
                     urls=[d.get("blog")] if d.get("blog") else [],
                     linked=[("X", d["twitter_username"], f"https://x.com/{d['twitter_username']}")]
                     if d.get("twitter_username") else [],
                     extra={"followers": d.get("followers"), "public_repos": d.get("public_repos"),
                            "hireable": d.get("hireable"), "updated": _date(d.get("updated_at"))})
        acc = add_profile(ctx, p)
        st, events = await ctx.get_json(f"https://api.github.com/users/{login}/events/public",
                                        params={"per_page": 100}, headers=headers)
        emails: dict[str, str] = {}
        if st == 200 and isinstance(events, list):
            for ev in events:
                for c in (ev.get("payload") or {}).get("commits") or []:
                    author = c.get("author") or {}
                    email = (author.get("email") or "").lower()
                    if email and "noreply" not in email and email not in emails:
                        emails[email] = author.get("name") or ""
        for email, name in emails.items():
            eid = ctx.add("email", email, {"commit_author": name}, label="commit email", parent=acc)
            if eid and name and " " in name.strip():
                ctx.add("person", name, label="commit author", parent=eid)
