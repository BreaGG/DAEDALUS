"""Entity catalogue: types, auto-detection of raw input and value normalisation."""

from __future__ import annotations

import ipaddress
import re


def L(en: str, es: str) -> dict:
    """Bilingual label."""
    return {"en": en, "es": es}


CATEGORIES: dict[str, dict] = {
    "identity": L("Identity", "Identidad"),
    "infrastructure": L("Infrastructure", "Infraestructura"),
    "web": L("Web", "Web"),
    "location": L("Location", "Ubicación"),
    "finance": L("Crypto & finance", "Cripto y finanzas"),
    "artifact": L("Artifacts", "Artefactos"),
    "threat": L("Threat intel", "Amenazas"),
}

# type -> metadata. "icon" is a key into web/js/icons.js, "manual" means the user can create it.
ENTITY_TYPES: dict[str, dict] = {
    "person": {"label": L("Person", "Persona"), "category": "identity", "color": "#e879a6", "manual": True},
    "username": {"label": L("Alias", "Alias"), "category": "identity", "color": "#5ec8f2", "manual": True},
    "email": {"label": L("Email address", "Correo"), "category": "identity", "color": "#f2b25e", "manual": True},
    "phone": {"label": L("Phone number", "Teléfono"), "category": "identity", "color": "#7fd18b", "manual": True},
    "account": {"label": L("Online account", "Cuenta online"), "category": "identity", "color": "#4fc1b0", "manual": True},
    "organization": {"label": L("Organization", "Organización"), "category": "identity", "color": "#8b93f0", "manual": True},
    "domain": {"label": L("Domain", "Dominio"), "category": "infrastructure", "color": "#b77cf0", "manual": True},
    "hostname": {"label": L("DNS name", "Nombre DNS"), "category": "infrastructure", "color": "#9a7fe0", "manual": True},
    "ip": {"label": L("IP address", "Dirección IP"), "category": "infrastructure", "color": "#ef6f6c", "manual": True},
    "netblock": {"label": L("Netblock", "Bloque de red"), "category": "infrastructure", "color": "#d9786a", "manual": True},
    "asn": {"label": L("AS number", "Sistema autónomo"), "category": "infrastructure", "color": "#c98ae8", "manual": True},
    "url": {"label": L("URL", "URL"), "category": "web", "color": "#9fb0c3", "manual": True},
    "tracking_code": {"label": L("Tracking code", "Código de seguimiento"), "category": "web", "color": "#e0c35a", "manual": True},
    "location": {"label": L("Location", "Ubicación"), "category": "location", "color": "#a3d468", "manual": True},
    "crypto": {"label": L("Crypto wallet", "Cartera cripto"), "category": "finance", "color": "#f5c84c", "manual": True},
    "hash": {"label": L("Hash", "Hash"), "category": "artifact", "color": "#b39a86", "manual": True},
    "image": {"label": L("Image", "Imagen"), "category": "artifact", "color": "#55cbdc", "manual": False},
    "phrase": {"label": L("Phrase", "Frase"), "category": "artifact", "color": "#c7c2b8", "manual": True},
    "breach": {"label": L("Data breach", "Filtración"), "category": "threat", "color": "#f0545a", "manual": False},
    "vulnerability": {"label": L("Vulnerability", "Vulnerabilidad"), "category": "threat", "color": "#ff8a4c", "manual": True},
}

# Second-level labels that act like a TLD ("example.co.uk" is a registrable domain).
MULTI_SUFFIXES = {
    "co.uk", "org.uk", "ac.uk", "gov.uk", "me.uk", "ltd.uk", "plc.uk", "net.uk", "sch.uk",
    "com.ar", "net.ar", "org.ar", "gob.ar", "edu.ar", "com.mx", "org.mx", "gob.mx", "edu.mx", "net.mx",
    "com.br", "net.br", "org.br", "gov.br", "edu.br", "com.co", "net.co", "org.co", "gov.co", "edu.co",
    "com.pe", "org.pe", "gob.pe", "edu.pe", "com.ve", "gob.ve", "com.ec", "gob.ec", "com.uy", "gub.uy",
    "com.py", "gov.py", "com.bo", "gob.bo", "gob.cl", "com.es", "org.es", "nom.es", "gob.es", "edu.es",
    "com.au", "net.au", "org.au", "gov.au", "edu.au", "co.nz", "org.nz", "govt.nz", "co.jp", "ne.jp",
    "or.jp", "ac.jp", "go.jp", "co.kr", "or.kr", "go.kr", "com.cn", "net.cn", "org.cn", "gov.cn",
    "com.hk", "com.tw", "com.sg", "com.my", "co.in", "net.in", "org.in", "gov.in", "co.za", "org.za",
    "gov.za", "com.tr", "gov.tr", "com.pl", "com.ru", "com.ua", "co.il", "org.il", "co.id", "or.id",
    "go.id", "com.ph", "gov.ph", "com.vn", "com.sa", "com.eg", "com.ng", "co.ke", "github.io",
    "gitlab.io", "herokuapp.com", "blogspot.com", "netlify.app", "vercel.app", "pages.dev", "web.app",
    "firebaseapp.com", "azurewebsites.net", "cloudfront.net", "appspot.com",
}

FREE_EMAIL_PROVIDERS = {
    "gmail.com", "googlemail.com", "outlook.com", "outlook.es", "hotmail.com", "hotmail.es", "live.com",
    "msn.com", "yahoo.com", "yahoo.es", "yahoo.com.ar", "yahoo.com.mx", "ymail.com", "icloud.com", "me.com",
    "mac.com", "aol.com", "proton.me", "protonmail.com", "pm.me", "gmx.com", "gmx.net", "gmx.es", "mail.com",
    "yandex.com", "yandex.ru", "zoho.com", "tutanota.com", "tuta.io", "mail.ru", "qq.com", "163.com",
    "126.com", "fastmail.com", "hey.com", "terra.com.br", "uol.com.br", "bol.com.br", "inbox.ru",
    "hotmail.com.ar", "live.com.mx", "outlook.com.ar", "disroot.org", "riseup.net",
}

CRYPTO_PATTERNS: dict[str, re.Pattern] = {
    "btc": re.compile(r"^(?:bc1[ac-hj-np-z02-9]{25,62}|[13][a-km-zA-HJ-NP-Z1-9]{25,34})$"),
    "eth": re.compile(r"^0x[a-fA-F0-9]{40}$"),
    "ltc": re.compile(r"^(?:ltc1[ac-hj-np-z02-9]{25,62}|[LM][a-km-zA-HJ-NP-Z1-9]{26,33})$"),
    "doge": re.compile(r"^D[5-9A-HJ-NP-U][1-9A-HJ-NP-Za-km-z]{32}$"),
    "trx": re.compile(r"^T[1-9A-HJ-NP-Za-km-z]{33}$"),
    "xmr": re.compile(r"^[48][0-9AB][1-9A-HJ-NP-Za-km-z]{93}$"),
}
CRYPTO_NAMES = {"btc": "Bitcoin", "eth": "Ethereum / EVM", "ltc": "Litecoin", "doge": "Dogecoin",
                "trx": "Tron", "xmr": "Monero"}

HASH_LENGTHS = {32: "MD5", 40: "SHA-1", 56: "SHA-224", 64: "SHA-256", 96: "SHA-384", 128: "SHA-512"}

_EMAIL = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,24}$")
_FQDN = re.compile(r"^(?=.{4,253}$)(?:[a-z0-9_](?:[a-z0-9_-]{0,61}[a-z0-9])?\.)+[a-z][a-z0-9-]{0,61}[a-z0-9]$", re.I)
_PHONE = re.compile(r"^\+?[\d\s().\-]{7,22}$")
_HEX = re.compile(r"^[a-f0-9]+$", re.I)
_ASN = re.compile(r"^AS\d{1,10}$", re.I)
_CVE = re.compile(r"^CVE-\d{4}-\d{4,7}$", re.I)
_TRACKING = re.compile(r"^(?:UA-\d{4,10}-\d{1,4}|G-[A-Z0-9]{6,12}|GTM-[A-Z0-9]{4,9}|(?:ca-)?pub-\d{10,20})$", re.I)
_LATLON = re.compile(r"^\s*(-?\d{1,2}(?:\.\d+)?)\s*,\s*(-?\d{1,3}(?:\.\d+)?)\s*$")
_USERNAME = re.compile(r"^@?[\w.\-]{1,64}$", re.UNICODE)


def crypto_chain(value: str) -> str | None:
    for chain, rx in CRYPTO_PATTERNS.items():
        if rx.match(value):
            return chain
    return None


def registered_domain(host: str) -> str:
    """Best-effort registrable domain of a hostname ("a.b.example.co.uk" -> "example.co.uk")."""
    parts = host.lower().rstrip(".").split(".")
    if len(parts) <= 2:
        return ".".join(parts)
    if ".".join(parts[-2:]) in MULTI_SUFFIXES:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


# gTLDs common enough to tell "john.dev" (domain) from "john.doe" (alias); 2-letter labels count as ccTLDs.
COMMON_TLDS = set("""
com net org info biz io dev app ai co me tv xyz online site tech store shop blog cloud live news pro club top win
vip one art design agency email gov edu mil int mobi name page link click space website fun world life today
network systems solutions services digital media studio games global group company center zone host press social
community academy africa asia bank bar beer bet bio black blue book build business cafe camera capital care cash
casa cat city codes coffee consulting cool credit dating deals delivery dental energy events exchange expert
express family farm fashion finance fit fitness foundation free fund gallery garden gift gold golf guide guru
health help holdings house institute insure international investments jobs kitchen land law legal lgbt life
limited live loan love ltd luxury management market marketing mba moda money movie museum music ninja onl
partners photo photography photos pics pink pizza plus poker porn press productions properties pub radio realty
recipes red rent repair report rest restaurant review reviews rocks run sale salon school science security sex
shoes show singles ski soccer software solar sport style sucks supply support surf tax taxi team tel tickets
tips tools tours town toys trade training travel university vegas ventures video villas vision vote voyage
watch wiki wine work works wtf xxx yoga zip eus cat gal bzh moe lol porn adult
""".split())


def looks_like_domain(value: str) -> bool:
    if not _FQDN.match(value) or value.replace(".", "").isdigit():
        return False
    tld = value.lower().rstrip(".").rsplit(".", 1)[-1]
    return (len(tld) == 2 and tld.isalpha()) or tld in COMMON_TLDS


def detect_type(value: str) -> str:
    """Guess the entity type of a raw string typed by the user."""
    v = (value or "").strip()
    if not v:
        return "phrase"
    if re.match(r"^https?://", v, re.I):
        return "url"
    if _EMAIL.match(v):
        return "email"
    try:
        ipaddress.ip_address(v)
        return "ip"
    except ValueError:
        pass
    if "/" in v:
        try:
            ipaddress.ip_network(v, strict=False)
            return "netblock"
        except ValueError:
            pass
    if _ASN.match(v):
        return "asn"
    if _CVE.match(v):
        return "vulnerability"
    if _TRACKING.match(v):
        return "tracking_code"
    if _LATLON.match(v):
        return "location"
    if crypto_chain(v):
        return "crypto"
    if _HEX.match(v) and len(v) in HASH_LENGTHS:
        return "hash"
    digits = re.sub(r"\D", "", v)
    if _PHONE.match(v) and 7 <= len(digits) <= 15 and (v.startswith("+") or not re.search(r"[a-z]", v, re.I)):
        return "phone"
    if looks_like_domain(v):
        return "domain" if registered_domain(v) == v.lower().rstrip(".") else "hostname"
    if " " in v:
        # "John Smith" -> person; longer free text -> phrase
        words = v.split()
        if 2 <= len(words) <= 5 and all(w[:1].isalpha() and w[:1].isupper() for w in words):
            return "person"
        return "phrase"
    if _USERNAME.match(v):
        return "username"
    return "phrase"


def normalize(etype: str, value: str) -> str:
    v = " ".join(str(value or "").split()) if etype in ("person", "phrase", "organization", "location") \
        else str(value or "").strip()
    if etype in ("email", "domain", "hostname", "hash", "username"):
        v = v.lower()
    if etype in ("domain", "hostname"):
        v = v.rstrip(".")
        if v.startswith("*."):
            v = v[2:]
    elif etype == "username":
        v = v.lstrip("@")
    elif etype == "ip":
        try:
            v = str(ipaddress.ip_address(v))
        except ValueError:
            pass
    elif etype == "netblock":
        try:
            v = str(ipaddress.ip_network(v, strict=False))
        except ValueError:
            pass
    elif etype == "phone":
        v = re.sub(r"[^\d+]", "", v)
    elif etype == "asn":
        v = "AS" + re.sub(r"\D", "", v)
    elif etype in ("vulnerability", "tracking_code"):
        v = v.upper()
    elif etype == "url":
        v = v.split("#")[0]
        if re.match(r"^https?://[^/]+$", v, re.I):
            v += "/"
    elif etype == "account":
        v = v.split("#")[0].rstrip("/")
    return v


def entity_id(etype: str, value: str) -> str:
    """Stable id; case-insensitive for free-text types so "Acme" and "ACME" collapse."""
    key = value.lower() if etype in ("person", "organization", "location", "phrase", "account", "url") else value
    return f"{etype}:{key}"


def display_label(etype: str, value: str, props: dict) -> str:
    if etype == "account":
        platform, user = props.get("platform"), props.get("username")
        if platform:
            return f"{platform} · {user}" if user else platform
    if etype == "asn" and props.get("name"):
        return f"{value} · {props['name']}"
    if etype == "image" and props.get("filename"):
        return props["filename"]
    if etype == "breach" and props.get("title"):
        return props["title"]
    if etype == "hash" and len(value) > 20:
        return f"{value[:10]}…{value[-6:]}"
    if etype == "crypto" and len(value) > 22:
        return f"{value[:10]}…{value[-6:]}"
    return value


def latlon(value: str) -> tuple[float, float] | None:
    m = _LATLON.match(value or "")
    if not m:
        return None
    lat, lon = float(m.group(1)), float(m.group(2))
    if -90 <= lat <= 90 and -180 <= lon <= 180:
        return lat, lon
    return None
