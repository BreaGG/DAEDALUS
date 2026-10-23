"""Transform base class and registry.

A transform takes one entity and discovers related entities (Maltego terminology).
Subclass `Transform`, decorate it with `@register` and implement `run(ctx)`; the
context gives you an HTTP client, settings/API keys and `ctx.add(...)` to emit results.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..entities import L

if TYPE_CHECKING:
    from ..engine import Context

TRANSFORM_CATEGORIES: dict[str, dict] = {
    "dns": L("DNS", "DNS"),
    "infrastructure": L("Infrastructure", "Infraestructura"),
    "web": L("Web", "Web"),
    "identity": L("Identity", "Identidad"),
    "social": L("Social & accounts", "Redes y cuentas"),
    "search": L("Search engines", "Buscadores"),
    "location": L("Location", "Ubicación"),
    "crypto": L("Blockchain", "Blockchain"),
    "threat": L("Threat intel", "Amenazas"),
    "utility": L("Utilities", "Utilidades"),
}


class Skip(Exception):
    """The transform cannot run (missing API key, input does not apply...)."""


class Transform:
    name: str = ""
    title: dict = L("", "")
    description: dict = L("", "")
    category: str = "utility"
    inputs: tuple[str, ...] = ()
    outputs: tuple[str, ...] = ()
    # required API keys (transform is skipped without them) and keys that only improve results
    keys: tuple[str, ...] = ()
    optional_keys: tuple[str, ...] = ()
    sources: tuple[str, ...] = ()
    timeout: float = 45
    # included in "run all transforms" and in the generic auto-expand machine
    default: bool = True

    def applies(self, entity: dict) -> bool:
        return entity["type"] in self.inputs

    async def run(self, ctx: "Context") -> None:
        raise NotImplementedError

    def meta(self) -> dict:
        return {
            "name": self.name,
            "title": self.title,
            "description": self.description,
            "category": self.category,
            "inputs": list(self.inputs),
            "outputs": list(self.outputs),
            "keys": list(self.keys),
            "optional_keys": list(self.optional_keys),
            "sources": list(self.sources),
            "default": self.default,
        }


REGISTRY: dict[str, Transform] = {}


def register(cls):
    inst = cls()
    if not inst.name:
        raise ValueError(f"{cls.__name__} has no name")
    if inst.name in REGISTRY:
        raise ValueError(f"duplicate transform name {inst.name}")
    REGISTRY[inst.name] = inst
    return cls
