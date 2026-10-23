"""Machines: scripted chains of transforms (Maltego's "machines").

Each stage runs on the entities produced by the previous stage (the seeds for
the first one); a transform only runs where its input type matches.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..entities import L
from .base import REGISTRY


@dataclass
class Machine:
    name: str
    title: dict
    description: dict
    inputs: tuple[str, ...]
    steps: list[list[str]] = field(default_factory=list)
    # True: each stage only sees what the previous one produced. False: the frontier keeps growing.
    chain: bool = True
    generic: bool = False

    def stages(self, depth: int) -> list[list[str]]:
        if self.generic:
            names = [t.name for t in REGISTRY.values() if t.default]
            return [names] * max(1, min(depth, 4))
        return self.steps

    def meta(self) -> dict:
        return {"name": self.name, "title": self.title, "description": self.description, "inputs": list(self.inputs),
                "generic": self.generic, "stages": len(self.steps) if not self.generic else None,
                "transforms": sorted({t for st in self.steps for t in st})}


MACHINES: dict[str, Machine] = {}


def machine(m: Machine) -> Machine:
    MACHINES[m.name] = m
    return m


machine(Machine(
    "domain_footprint",
    L("Domain footprint", "Huella de dominio"),
    L("DNS, registration, subdomains and website; then resolves every host and profiles each IP.",
      "DNS, registro, subdominios y web; luego resuelve cada host y perfila cada IP."),
    ("domain",),
    [
        ["dns_resolve", "dns_mx", "dns_ns", "dns_txt", "rdap_domain", "crtsh_subdomains", "to_website", "security_txt",
         "wayback"],
        ["dns_resolve", "ip_geolocation", "shodan_internetdb", "reverse_dns", "web_page_scan", "hostname_to_domain"],
        ["ip_geolocation", "shodan_internetdb", "ripestat_network"],
    ],
))

machine(Machine(
    "ip_footprint",
    L("IP footprint", "Huella de IP"),
    L("Owner, network, location, exposed services and co-hosted names of an IP address.",
      "Titular, red, ubicación, servicios expuestos y nombres alojados en una IP."),
    ("ip", "netblock"),
    [
        ["reverse_dns", "rdap_ip", "ip_geolocation", "shodan_internetdb", "reverse_ip", "ripestat_network"],
        ["hostname_to_domain", "dns_resolve", "asn_prefixes"],
    ],
))

machine(Machine(
    "identity_footprint",
    L("Identity footprint", "Huella de identidad"),
    L("From an alias, email, phone or name to accounts, profiles, breaches and new aliases, two levels deep.",
      "De un alias, correo, teléfono o nombre a cuentas, perfiles, filtraciones y nuevos alias, a dos niveles."),
    ("username", "email", "phone", "person"),
    [
        ["username_sweep", "username_profiles", "github_profile", "email_to_alias", "email_to_domain", "gravatar",
         "xposedornot", "hibp", "phone_info", "web_search"],
        ["username_sweep", "username_profiles", "github_profile", "gravatar", "xposedornot", "hibp", "email_to_alias",
         "account_to_alias", "geocode"],
        ["username_profiles", "github_profile", "gravatar", "geocode"],
    ],
))

machine(Machine(
    "web_footprint",
    L("Website footprint", "Huella de sitio web"),
    L("Scrapes a site for contacts, profiles and trackers, then follows the linked domains one step.",
      "Extrae contactos, perfiles y rastreadores de una web y sigue un paso los dominios enlazados."),
    ("url", "domain", "hostname"),
    [
        ["to_website", "web_page_scan", "url_to_host", "wayback"],
        ["web_page_scan", "account_to_alias", "rdap_domain", "dns_resolve"],
        ["username_profiles", "ip_geolocation"],
    ],
))

machine(Machine(
    "labyrinth",
    L("Labyrinth (auto-expand)", "Laberinto (expansión automática)"),
    L("Runs every default transform on the seeds and keeps walking outwards N levels. Bounded by the "
      "'machine max entities' setting.",
      "Ejecuta todos los transforms por defecto sobre las semillas y sigue avanzando N niveles. Limitado por "
      "el ajuste «máximo de entidades por máquina»."),
    (),
    generic=True,
))
