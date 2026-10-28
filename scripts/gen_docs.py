"""Generate the entity / transform / machine reference from the code.

    python scripts/gen_docs.py          # rewrite docs/en/transforms.md and docs/es/transforms.md
    python scripts/gen_docs.py --check  # exit 1 if they are out of date (used by the tests)
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from daedalus.config import API_KEYS  # noqa: E402
from daedalus.entities import CATEGORIES, ENTITY_TYPES  # noqa: E402
from daedalus.transforms import MACHINES, REGISTRY, TRANSFORM_CATEGORIES  # noqa: E402

OUTPUT = {"en": ROOT / "docs" / "en" / "transforms.md", "es": ROOT / "docs" / "es" / "transforms.md"}

# how the types that cannot be typed in are created
CREATED_BY = {
    "image": {"en": "uploading a photo", "es": "se crea al subir una foto"},
    "breach": {"en": "breach transforms", "es": "la crean los transforms de filtraciones"},
}

# what you can type in the quick-add bar to get each type (auto-detection)
EXAMPLES = {
    "person": "John Smith", "username": "teolabrys", "email": "daedalusintelligence@gmail.com", "phone": "+34 612 345 678",
    "account": "", "organization": "", "domain": "example.com", "hostname": "mail.example.com",
    "ip": "203.0.113.17", "netblock": "203.0.113.0/24", "asn": "AS64500", "url": "https://example.com/about",
    "tracking_code": "G-ABCD123456", "location": "40.4168, -3.7038", "crypto": "bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4",
    "hash": "d41d8cd98f00b204e9800998ecf8427e", "image": "", "phrase": "selling access to a vpn", "breach": "",
    "vulnerability": "CVE-2021-44228",
}

T = {
    "en": {
        "title": "Entity, transform and machine reference",
        "author": "Author: **Alejandro Brea**",
        "generated": "Generated from the source code by `scripts/gen_docs.py`. Do not edit by hand.",
        "toc": "[Entities](#entities) · [Transforms](#transforms) · [Machines](#machines) · [API keys](#api-keys)",
        "entities": "Entities",
        "entities_intro": "Every node in the graph is an entity of one of these types. Types with an example can be typed in "
                          "the quick-add bar and are recognised automatically; the others are created from the palette or "
                          "by transforms.",
        "ent_head": "| Type | Id | Category | Create by hand | Auto-detected from |",
        "yes": "yes", "no": "no", "palette_only": "palette / menu only", "created_by": "created by {x}",
        "transforms": "Transforms",
        "transforms_intro": "Transforms take one entity and return related entities and/or new properties. Right-click an "
                            "entity (or a selection) to run them. *Run all* runs every transform marked **default**.",
        "summary": "transforms in {n} categories, {k} of them need no API key.",
        "id": "Id", "input": "Input", "output": "Output", "props_only": "properties of the input entity",
        "sources": "Sources", "key": "API key", "none": "none", "optional": "optional", "default": "In “Run all”",
        "timeout": "Timeout",
        "machines": "Machines",
        "machines_intro": "Machines chain transforms. Stage 1 runs on the selected entities; every following stage runs only "
                          "on what the previous stage produced (a transform only runs where its input type matches). "
                          "The whole run is capped by *Settings → General → Max entities per machine*.",
        "for": "Suggested for", "any": "any entity", "stage": "Stage", "generic": "Runs every **default** transform on "
               "the seeds, then again on what they produced, for the number of levels you choose (1-4).",
        "keys": "API keys",
        "keys_intro": "All keys are optional and are set in *Settings → API keys*. They are stored in `settings.json` "
                      "inside the data folder.",
        "key_head": "| Key | Service | Used by |",
    },
    "es": {
        "title": "Referencia de entidades, transforms y máquinas",
        "author": "Autor: **Alejandro Brea**",
        "generated": "Generado a partir del código por `scripts/gen_docs.py`. No lo edites a mano.",
        "toc": "[Entidades](#entidades) · [Transforms](#transforms) · [Máquinas](#máquinas) · [Claves API](#claves-api)",
        "entities": "Entidades",
        "entities_intro": "Cada nodo del grafo es una entidad de uno de estos tipos. Los que tienen ejemplo se pueden "
                          "escribir en la barra de alta rápida y se reconocen solos; los demás se crean desde la paleta "
                          "o los generan los transforms.",
        "ent_head": "| Tipo | Id | Categoría | Se crea a mano | Se detecta a partir de |",
        "yes": "sí", "no": "no", "palette_only": "sólo desde paleta / menú", "created_by": "{x}",
        "transforms": "Transforms",
        "transforms_intro": "Un transform toma una entidad y devuelve entidades relacionadas y/o nuevas propiedades. Haz clic "
                            "derecho sobre una entidad (o una selección) para lanzarlos. *Ejecutar todos* lanza los "
                            "marcados como **por defecto**.",
        "summary": "transforms en {n} categorías; {k} no necesitan clave API.",
        "id": "Id", "input": "Entrada", "output": "Salida", "props_only": "propiedades de la entidad de entrada",
        "sources": "Fuentes", "key": "Clave API", "none": "ninguna", "optional": "opcional",
        "default": "En «Ejecutar todos»", "timeout": "Tiempo máximo",
        "machines": "Máquinas",
        "machines_intro": "Las máquinas encadenan transforms. La etapa 1 se ejecuta sobre las entidades seleccionadas; cada "
                          "etapa siguiente sólo sobre lo que produjo la anterior (un transform sólo se ejecuta si el tipo "
                          "de entrada encaja). Toda la ejecución está limitada por *Ajustes → General → Máximo de "
                          "entidades por máquina*.",
        "for": "Pensada para", "any": "cualquier entidad", "stage": "Etapa", "generic": "Ejecuta todos los transforms "
               "**por defecto** sobre las semillas y vuelve a hacerlo sobre lo que producen, durante los niveles que "
               "elijas (1-4).",
        "keys": "Claves API",
        "keys_intro": "Todas son opcionales y se configuran en *Ajustes → Claves API*. Se guardan en `settings.json`, "
                      "dentro de la carpeta de datos.",
        "key_head": "| Clave | Servicio | La usan |",
    },
}


def type_label(t: str, lang: str) -> str:
    return ENTITY_TYPES[t]["label"][lang]


def render(lang: str) -> str:
    tr = T[lang]
    out = [f"# {tr['title']}", "", tr["author"], "", f"> {tr['generated']}", "", tr["toc"], ""]

    out += [f"## {tr['entities']}", "", tr["entities_intro"], "", tr["ent_head"], "|---|---|---|---|---|"]
    for key, info in ENTITY_TYPES.items():
        manual = tr["yes"] if info["manual"] else tr["no"]
        if EXAMPLES.get(key):
            example = f"`{EXAMPLES[key]}`"
        elif key in CREATED_BY:
            example = tr["created_by"].format(x=CREATED_BY[key][lang])
        else:
            example = tr["palette_only"]
        out.append(f"| {info['label'][lang]} | `{key}` | {CATEGORIES[info['category']][lang]} | {manual} | {example} |")

    order = list(TRANSFORM_CATEGORIES)
    transforms = sorted(REGISTRY.values(), key=lambda t: (order.index(t.category), t.title[lang].lower()))
    free = sum(1 for t in transforms if not t.keys)
    used_cats = [c for c in order if any(t.category == c for t in transforms)]
    out += ["", f"## {tr['transforms']}", "", tr["transforms_intro"], "",
            f"**{len(transforms)}** {tr['summary'].format(n=len(used_cats), k=free)}", ""]
    for cat in used_cats:
        out += [f"### {TRANSFORM_CATEGORIES[cat][lang]}", ""]
        for t in (x for x in transforms if x.category == cat):
            outputs = ", ".join(type_label(o, lang) for o in t.outputs) or tr["props_only"]
            if t.keys:
                key = ", ".join(f"`{k}`" for k in t.keys)
            elif t.optional_keys:
                key = f"{tr['optional']}: " + ", ".join(f"`{k}`" for k in t.optional_keys)
            else:
                key = tr["none"]
            out += [
                f"#### {t.title[lang]}",
                "",
                t.description[lang],
                "",
                f"| {tr['id']} | {tr['input']} | {tr['output']} | {tr['sources']} | {tr['key']} | {tr['default']} | {tr['timeout']} |",
                "|---|---|---|---|---|---|---|",
                f"| `{t.name}` | {', '.join(type_label(i, lang) for i in t.inputs)} | {outputs} | "
                f"{', '.join(t.sources) or '—'} | {key} | {tr['yes'] if t.default else '—'} | {int(t.timeout)} s |",
                "",
            ]

    out += [f"## {tr['machines']}", "", tr["machines_intro"], ""]
    for m in MACHINES.values():
        inputs = ", ".join(type_label(i, lang) for i in m.inputs) or tr["any"]
        out += [f"### {m.title[lang]} (`{m.name}`)", "", m.description[lang], "", f"*{tr['for']}:* {inputs}", ""]
        if m.generic:
            out += [tr["generic"], ""]
            continue
        for i, stage in enumerate(m.steps, 1):
            names = ", ".join(REGISTRY[n].title[lang] for n in stage)
            out.append(f"{i}. **{tr['stage']} {i}:** {names}")
        out.append("")

    out += [f"## {tr['keys']}", "", tr["keys_intro"], "", tr["key_head"], "|---|---|---|"]
    for key, (label, url) in API_KEYS.items():
        users = [t.title[lang] for t in transforms if key in t.keys or key in t.optional_keys]
        out.append(f"| `{key}` | [{label}]({url}) | {'; '.join(users)} |")
    return "\n".join(out).rstrip() + "\n"


def main(argv: list[str]) -> int:
    stale = []
    for lang, path in OUTPUT.items():
        text = render(lang)
        if "--check" in argv:
            if not path.exists() or path.read_text(encoding="utf-8") != text:
                stale.append(str(path.relative_to(ROOT)))
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
            print(f"wrote {path.relative_to(ROOT)}")
    if stale:
        print("out of date, run `python scripts/gen_docs.py`: " + ", ".join(stale))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
