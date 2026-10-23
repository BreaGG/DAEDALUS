"""The generated reference in docs/ must match the code (run `python scripts/gen_docs.py` after changing transforms)."""

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_generated_reference_is_up_to_date():
    spec = importlib.util.spec_from_file_location("gen_docs", ROOT / "scripts" / "gen_docs.py")
    gen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gen)
    for lang, path in gen.OUTPUT.items():
        assert path.read_text(encoding="utf-8") == gen.render(lang), f"{path} is stale: run python scripts/gen_docs.py"


def test_docs_links_point_to_existing_files():
    import re

    for md in [ROOT / "README.md", ROOT / "README.es.md", *ROOT.glob("docs/**/*.md")]:
        for target in re.findall(r"\]\(((?!https?://|#|mailto:)[^)#\s]+)", md.read_text(encoding="utf-8")):
            assert (md.parent / target).exists(), f"{md.relative_to(ROOT)} links to missing {target}"


def _slugs(md: Path) -> set[str]:
    """GitHub-style heading anchors of a markdown file (code blocks ignored)."""
    import re

    text = re.sub(r"```.*?```", "", md.read_text(encoding="utf-8"), flags=re.S)
    slugs = set()
    for heading in re.findall(r"^#{1,6} (.+)$", text, flags=re.M):
        slug = re.sub(r"[^\w\- ]", "", heading.strip().lower()).replace(" ", "-")
        slugs.add(slug)
    return slugs


def test_docs_anchors_exist():
    import re

    for md in [ROOT / "README.md", ROOT / "README.es.md", *ROOT.glob("docs/**/*.md")]:
        for target, anchor in re.findall(r"\]\(((?!https?://)[^)#\s]*)#([^)\s]+)\)", md.read_text(encoding="utf-8")):
            path = (md.parent / target) if target else md
            assert anchor in _slugs(path), f"{md.relative_to(ROOT)}: #{anchor} not found in {path.relative_to(ROOT)}"
