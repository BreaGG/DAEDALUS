"""Transform registry. Importing this package registers every built-in transform."""

from __future__ import annotations

import importlib.util
import logging
import sys
from pathlib import Path

from ..entities import L
from .base import REGISTRY, TRANSFORM_CATEGORIES, Skip, Transform, register
from . import dns, infra, web, identity, social, search, location, crypto, threat  # noqa: F401,E402
from .machines import MACHINES, Machine, machine  # noqa: E402

__all__ = ["REGISTRY", "TRANSFORM_CATEGORIES", "MACHINES", "L", "Machine", "Skip", "Transform", "load_plugins",
           "machine", "register"]

log = logging.getLogger("daedalus")
_loaded: set[str] = set()


def load_plugins(folder: Path) -> list[str]:
    """Import every *.py in `folder`; plugins register transforms/machines with the usual decorators.

    Returns the names of the transforms the plugins added.
    """
    added: list[str] = []
    if not folder.is_dir():
        return added
    for path in sorted(folder.glob("*.py")):
        key = str(path.resolve())
        if key in _loaded or path.name.startswith("_"):
            continue
        _loaded.add(key)
        before = set(REGISTRY)
        try:
            spec = importlib.util.spec_from_file_location(f"daedalus_plugin_{path.stem}", path)
            module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = module
            spec.loader.exec_module(module)
        except Exception:  # noqa: BLE001  a broken plugin must not take the app down
            log.exception("plugin %s failed to load", path.name)
            continue
        added += sorted(set(REGISTRY) - before)
    return added
