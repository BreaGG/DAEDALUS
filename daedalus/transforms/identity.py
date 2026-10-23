"""Identity transforms: emails, phones, people and aliases."""

from __future__ import annotations

import hashlib
import re
import unicodedata

import phonenumbers
from phonenumbers import carrier, geocoder, timezone

from ..entities import FREE_EMAIL_PROVIDERS, L
from ..webutil import resolve
from .base import Skip, Transform, register

GENERIC_LOCALPARTS = {
    "info", "contact", "contacto", "admin", "administrator", "support", "soporte", "sales", "ventas", "hello",
    "hola", "hi", "mail", "email", "office", "team", "noreply", "no-reply", "donotreply", "webmaster", "postmaster",
    "hostmaster", "abuse", "security", "privacy", "billing", "help", "jobs", "careers", "press", "marketing",
    "newsletter", "news", "service", "services", "dmarc", "dmarc-reports", "reports", "root", "test",
}
DISPOSABLE_DOMAINS = {
    "mailinator.com", "guerrillamail.com", "10minutemail.com", "tempmail.com", "temp-mail.org", "yopmail.com",
    "trashmail.com", "sharklasers.com", "getnada.com", "dispostable.com", "maildrop.cc", "throwawaymail.com",
    "fakeinbox.com", "mintemail.com", "emailondeck.com", "mohmal.com", "tempail.com", "moakt.com",
}
FREE_PROVIDER_NAMES = {"gmail.com": "Gmail", "googlemail.com": "Gmail", "outlook.com": "Outlook",
                       "hotmail.com": "Hotmail", "yahoo.com": "Yahoo", "icloud.com": "iCloud", "proton.me": "Proton",
                       "protonmail.com": "Proton", "gmx.com": "GMX", "yandex.com": "Yandex", "aol.com": "AOL"}


def _ascii(s: str) -> str:
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()


@register
class EmailToDomain(Transform):
    name = "email_to_domain"
    title = L("To domain", "A dominio")
    description = L("Domain of the address. Free webmail providers are noted but not added, so they do not "
                    "become false bridges between unrelated people.",
                    "Dominio de la dirección. Los proveedores gratuitos se anotan pero no se añaden, para que no "
                    "creen puentes falsos entre personas que no tienen relación.")
    category = "identity"
    inputs = ("email",)
    outputs = ("domain",)

    async def run(self, ctx):
        domain = ctx.value.rsplit("@", 1)[-1]
        if domain in FREE_EMAIL_PROVIDERS:
            ctx.enrich({"provider": FREE_PROVIDER_NAMES.get(domain, domain), "free_provider": True})
            ctx.log(f"{domain} is a free provider (not added)")
            return
        ctx.add("domain", domain, label="email domain", reverse=False)


@register
class EmailToAlias(Transform):
    name = "email_to_alias"
    title = L("To alias (local part)", "A alias (parte local)")
    description = L("The part before the @, when it looks like a personal handle.",
                    "La parte antes de la @, cuando parece un alias personal.")
    category = "identity"
    inputs = ("email",)
    outputs = ("username",)

    async def run(self, ctx):
        local = ctx.value.split("@", 1)[0].split("+", 1)[0]
        if len(local) < 3 or local in GENERIC_LOCALPARTS or not re.fullmatch(r"[a-z0-9._\-]+", local):
            ctx.log("Local part looks generic")
            return
        ctx.add("username", local, label="local part")


@register
class EmailValidate(Transform):
    name = "email_validate"
    title = L("Validate address [MX]", "Validar dirección [MX]")
    description = L("Does the domain accept mail? Is it a disposable provider?",
                    "¿El dominio acepta correo? ¿Es un proveedor desechable?")
    category = "identity"
    inputs = ("email",)

    async def run(self, ctx):
        domain = ctx.value.rsplit("@", 1)[-1]
        mx = await resolve(domain, "MX")
        ctx.enrich({"domain_accepts_mail": bool(mx), "mx_records": [m.split()[-1].rstrip(".") for m in mx],
                    "disposable": domain in DISPOSABLE_DOMAINS or None})


@register
class Gravatar(Transform):
    name = "gravatar"
    title = L("To Gravatar profile", "A perfil de Gravatar")
    description = L("Public Gravatar profile: name, location, avatar and verified accounts.",
                    "Perfil público de Gravatar: nombre, ubicación, avatar y cuentas verificadas.")
    category = "social"
    inputs = ("email",)
    outputs = ("account", "person", "location", "url")
    sources = ("Gravatar",)

    async def run(self, ctx):
        email = ctx.value.strip().lower()
        md5 = hashlib.md5(email.encode()).hexdigest()  # noqa: S324  Gravatar's legacy key
        sha = hashlib.sha256(email.encode()).hexdigest()
        st, d = await ctx.get_json(f"https://en.gravatar.com/{md5}.json")
        entry = (d.get("entry") or [None])[0] if st == 200 and isinstance(d, dict) else None
        if entry:
            profile = {
                "url": entry.get("profileUrl"), "username": entry.get("preferredUsername"),
                "name": (entry.get("name") or {}).get("formatted") or entry.get("displayName"),
                "location": entry.get("currentLocation"), "about": entry.get("aboutMe"),
                "avatar": entry.get("thumbnailUrl"),
                "accounts": [(a.get("shortname") or a.get("domain"), a.get("url"), a.get("username"))
                             for a in entry.get("accounts") or []],
                "urls": [u.get("value") for u in entry.get("urls") or []],
            }
        else:
            st, d = await ctx.get_json(f"https://api.gravatar.com/v3/profiles/{sha}")
            if st != 200 or not isinstance(d, dict):
                ctx.log("No Gravatar profile")
                return
            profile = {
                "url": d.get("profile_url"), "username": None, "name": d.get("display_name"),
                "location": d.get("location"), "about": d.get("description"), "avatar": d.get("avatar_url"),
                "accounts": [(a.get("service_label") or a.get("service_type"), a.get("url"), None)
                             for a in d.get("verified_accounts") or [] if not a.get("is_hidden")],
                "urls": [], "job_title": d.get("job_title"), "company": d.get("company"),
            }
        if not profile.get("url"):
            return
        acc = ctx.add("account", profile["url"], {
            "platform": "Gravatar", "username": profile.get("username"), "about": profile.get("about"),
            "_image": profile.get("avatar"), "_links": [["Profile", profile["url"]]]}, label="has account")
        if profile.get("name"):
            ctx.add("person", profile["name"], label="name", parent=acc)
        if profile.get("location"):
            ctx.add("location", profile["location"], label="lives in", parent=acc)
        if profile.get("company"):
            ctx.add("organization", profile["company"], {"role": profile.get("job_title")}, label="works at", parent=acc)
        for platform, url, user in profile["accounts"]:
            if url:
                ctx.add("account", url, {"platform": platform, "username": user, "verified": "Gravatar",
                                         "_links": [["Profile", url]]}, label="verified account", parent=acc)
        for url in profile["urls"]:
            if url:
                ctx.add("url", url, label="website", parent=acc)


@register
class XposedOrNot(Transform):
    name = "xposedornot"
    title = L("To data breaches [XposedOrNot]", "A filtraciones [XposedOrNot]")
    description = L("Public breaches where the address appears (free, no key).",
                    "Filtraciones públicas en las que aparece la dirección (gratis, sin clave).")
    category = "threat"
    inputs = ("email",)
    outputs = ("breach",)
    sources = ("XposedOrNot",)

    async def run(self, ctx):
        st, d = await ctx.get_json("https://api.xposedornot.com/v1/breach-analytics", params={"email": ctx.value})
        if st == 404 or (isinstance(d, dict) and d.get("Error")):
            return
        if st == 429:
            raise Skip("XposedOrNot rate limit, try again later")
        if st != 200 or not isinstance(d, dict):
            raise Skip(f"XposedOrNot HTTP {st}")
        details = ((d.get("ExposedBreaches") or {}).get("breaches_details")) or []
        for b in details:
            name = b.get("breach")
            if not name:
                continue
            date = str(b.get("xposed_date") or "")
            ctx.add("breach", name, {
                "title": name, "domain": b.get("domain"), "date": date, "records": b.get("xposed_records"),
                "data_classes": [x.strip() for x in str(b.get("xposed_data") or "").split(";") if x.strip()],
                "industry": b.get("industry"), "password_risk": b.get("password_risk"),
                "description": b.get("details"), "_dates": [[f"Breach: {name}", date]] if date else [],
            }, label="exposed in")
        summary = (d.get("BreachesSummary") or {}).get("site")
        if summary and not details:
            for name in str(summary).split(";"):
                if name.strip():
                    ctx.add("breach", name.strip(), {"title": name.strip()}, label="exposed in")


@register
class HIBP(Transform):
    name = "hibp"
    title = L("To data breaches [Have I Been Pwned]", "A filtraciones [Have I Been Pwned]")
    description = L("Breaches from HIBP (paid API key).", "Filtraciones de HIBP (clave de pago).")
    category = "threat"
    inputs = ("email",)
    outputs = ("breach",)
    keys = ("hibp",)
    sources = ("Have I Been Pwned",)

    async def run(self, ctx):
        key = ctx.require_key("hibp")
        st, d = await ctx.get_json(f"https://haveibeenpwned.com/api/v3/breachedaccount/{ctx.value}",
                                   params={"truncateResponse": "false"},
                                   headers={"hibp-api-key": key, "user-agent": "DAEDALUS-OSINT"})
        if st == 404:
            return
        if st != 200 or not isinstance(d, list):
            raise Skip(f"HIBP HTTP {st}")
        for b in d:
            name = b.get("Name")
            date = b.get("BreachDate") or ""
            ctx.add("breach", name, {
                "title": b.get("Title") or name, "domain": b.get("Domain"), "date": date, "records": b.get("PwnCount"),
                "data_classes": b.get("DataClasses"), "verified": b.get("IsVerified"),
                "description": re.sub(r"<[^>]+>", "", b.get("Description") or ""),
                "_dates": [[f"Breach: {b.get('Title') or name}", date]] if date else [],
            }, label="exposed in")


@register
class HunterDomain(Transform):
    name = "hunter_domain"
    title = L("To emails and people [Hunter.io]", "A correos y personas [Hunter.io]")
    description = L("Addresses published for the domain, with names and positions.",
                    "Direcciones publicadas del dominio, con nombres y cargos.")
    category = "identity"
    inputs = ("domain",)
    outputs = ("email", "person", "organization")
    keys = ("hunter",)
    sources = ("Hunter.io",)

    async def run(self, ctx):
        key = ctx.require_key("hunter")
        st, d = await ctx.get_json("https://api.hunter.io/v2/domain-search",
                                   params={"domain": ctx.value, "api_key": key, "limit": min(ctx.limit, 100)})
        if st != 200 or not isinstance(d, dict):
            raise Skip(f"Hunter HTTP {st}")
        data = d.get("data") or {}
        if data.get("organization"):
            ctx.add("organization", data["organization"], label="owned by", reverse=False)
        ctx.enrich({"email_pattern": data.get("pattern")})
        for e in data.get("emails") or []:
            eid = ctx.add("email", e.get("value"), {"confidence": e.get("confidence"), "position": e.get("position"),
                                                    "department": e.get("department")}, label="email at")
            name = " ".join(x for x in (e.get("first_name"), e.get("last_name")) if x)
            if eid and name:
                ctx.add("person", name, {"position": e.get("position")}, label="uses", parent=eid, reverse=True)


@register
class PhoneInfo(Transform):
    name = "phone_info"
    title = L("To carrier, region and line type", "A operador, región y tipo de línea")
    description = L("Offline analysis with libphonenumber: validity, country, carrier, line type and time zone.",
                    "Análisis sin conexión con libphonenumber: validez, país, operador, tipo de línea y zona horaria.")
    category = "identity"
    inputs = ("phone",)
    outputs = ("location",)
    sources = ("libphonenumber",)

    TYPES = {0: "fixed line", 1: "mobile", 2: "fixed line or mobile", 3: "toll free", 4: "premium rate",
             5: "shared cost", 6: "VoIP", 7: "personal number", 8: "pager", 9: "UAN", 10: "voicemail"}

    async def run(self, ctx):
        region = (ctx.settings.get("default_region") or "").upper() or None
        try:
            num = phonenumbers.parse(ctx.value, None if ctx.value.startswith("+") else region)
        except phonenumbers.NumberParseException as e:
            raise Skip(f"Cannot parse number ({e}); set a default country in settings") from e
        e164 = phonenumbers.format_number(num, phonenumbers.PhoneNumberFormat.E164)
        country = geocoder.country_name_for_number(num, "en")
        place = geocoder.description_for_number(num, "en")
        digits = e164.lstrip("+")
        ctx.enrich({
            "valid": phonenumbers.is_valid_number(num),
            "e164": e164,
            "international": phonenumbers.format_number(num, phonenumbers.PhoneNumberFormat.INTERNATIONAL),
            "country": country,
            "region_code": phonenumbers.region_code_for_number(num),
            "line_type": self.TYPES.get(phonenumbers.number_type(num), "unknown"),
            "carrier": carrier.name_for_number(num, "en") or None,
            "timezones": list(timezone.time_zones_for_number(num)),
            "_links": [["WhatsApp", f"https://wa.me/{digits}"], ["Telegram", f"https://t.me/+{digits}"],
                       ["Search", f"https://duckduckgo.com/?q=%22{digits}%22"]],
        })
        where = place if place and place != country else None
        label = ", ".join(x for x in (where, country) if x)
        if label:
            ctx.add("location", label, {"precision": "phone numbering plan"}, label="registered in")


def name_permutations(full: str) -> list[str]:
    parts = [re.sub(r"[^a-z]", "", _ascii(p).lower()) for p in full.split()]
    parts = [p for p in parts if p]
    if len(parts) < 2:
        return []
    first, last = parts[0], parts[-1]
    combos = [f"{first}{last}", f"{first}.{last}", f"{first}_{last}", f"{first[0]}{last}", f"{first[0]}.{last}",
              f"{first}{last[0]}", f"{last}{first}", f"{last}.{first}", f"{last}{first[0]}", f"{first}-{last}"]
    if len(parts) > 2:
        middle = parts[1]
        combos += [f"{first}{middle[0]}{last}", f"{first}{middle}", f"{first}.{middle}.{last}"]
    return list(dict.fromkeys(c for c in combos if len(c) >= 4))


@register
class PersonToAliases(Transform):
    name = "person_to_aliases"
    title = L("To likely aliases (permutations)", "A alias probables (permutaciones)")
    description = L("Typical handles built from the name (jdoe, john.doe...). They are guesses: verify them "
                    "with the account sweep.",
                    "Alias típicos construidos con el nombre (jperez, juan.perez...). Son suposiciones: "
                    "verifícalos con el barrido de cuentas.")
    category = "identity"
    inputs = ("person",)
    outputs = ("username",)
    default = False

    async def run(self, ctx):
        for alias in name_permutations(ctx.value):
            if ctx.add("username", alias, {"guessed": True}, label="possible alias") is None:
                break


@register
class AccountToAlias(Transform):
    name = "account_to_alias"
    title = L("To alias", "A alias")
    description = L("Handle used on the account.", "Alias usado en la cuenta.")
    category = "social"
    inputs = ("account",)
    outputs = ("username",)

    async def run(self, ctx):
        user = (ctx.props.get("username") or "").strip().lstrip("@")
        if user and "@" not in user and re.fullmatch(r"[\w.\-]{2,64}", user):
            ctx.add("username", user, label="has account", reverse=True)
