"""Paths, persisted settings and the catalogue of optional API keys."""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
WEB_DIR = PACKAGE_DIR / "web"
RESOURCES_DIR = PACKAGE_DIR / "resources"


def default_data_dir() -> Path:
    """Where cases and settings live, first match wins:

    DAEDALUS_DATA_DIR, the volume Railway attached (RAILWAY_VOLUME_MOUNT_PATH), the image default
    (DAEDALUS_DEFAULT_DATA_DIR, /data in the Docker image), ./data next to a source checkout, ~/.daedalus.
    """
    for var in ("DAEDALUS_DATA_DIR", "RAILWAY_VOLUME_MOUNT_PATH", "DAEDALUS_DEFAULT_DATA_DIR"):
        if os.environ.get(var):
            return Path(os.environ[var]).expanduser()
    checkout = PACKAGE_DIR.parent
    if (checkout / "pyproject.toml").exists():
        return checkout / "data"
    return Path.home() / ".daedalus"


# key -> (label, where to get it)
API_KEYS: dict[str, tuple[str, str]] = {
    "shodan": ("Shodan", "https://account.shodan.io/"),
    "virustotal": ("VirusTotal", "https://www.virustotal.com/gui/my-apikey"),
    "hunter": ("Hunter.io", "https://hunter.io/api-keys"),
    "hibp": ("Have I Been Pwned", "https://haveibeenpwned.com/API/Key"),
    "abuseipdb": ("AbuseIPDB", "https://www.abuseipdb.com/account/api"),
    "urlscan": ("URLScan.io", "https://urlscan.io/user/profile/"),
    "github": ("GitHub token (60 -> 5000 req/h)", "https://github.com/settings/tokens"),
    "serper": ("Serper.dev (Google search)", "https://serper.dev/api-key"),
    "brave": ("Brave Search API", "https://api-dashboard.search.brave.com/app/keys"),
}

# interface languages; the first one is the default
LANGUAGES: dict[str, str] = {"en": "English", "es": "Español"}

DEFAULT_SETTINGS: dict = {
    "api_keys": {},
    "lang": next(iter(LANGUAGES)),
    # results a single transform may add (Maltego's "slider")
    "result_limit": 50,
    # per-request timeout for the username sweep
    "username_timeout": 12,
    # also load the Sherlock project's site list (400+ sites) for the username sweep
    "sherlock_db": False,
    "include_nsfw": False,
    # entities a machine may expand before it stops
    "machine_max_entities": 60,
    # refuse to fetch private / loopback addresses from web transforms (SSRF guard)
    "block_private_targets": True,
    "default_region": "",
}


class Settings:
    def __init__(self, path: Path):
        self.path = path
        self._lock = threading.Lock()
        self.data = json.loads(json.dumps(DEFAULT_SETTINGS))
        if path.exists():
            try:
                self.data.update(json.loads(path.read_text(encoding="utf-8")))
            except (OSError, ValueError):
                pass

    def get(self, name: str, default=None):
        return self.data.get(name, default)

    def key(self, name: str) -> str | None:
        return (self.data.get("api_keys") or {}).get(name) or None

    def update(self, changes: dict) -> None:
        changes = dict(changes)
        with self._lock:
            keys = dict(self.data.get("api_keys") or {})
            for k, v in (changes.pop("api_keys", None) or {}).items():
                if k not in API_KEYS or v is None:
                    continue
                v = str(v).strip()
                if v:
                    keys[k] = v
                else:
                    keys.pop(k, None)
            self.data["api_keys"] = keys
            for k, v in changes.items():
                if k in DEFAULT_SETTINGS and k != "api_keys":
                    default = DEFAULT_SETTINGS[k]
                    if k == "lang" and v not in LANGUAGES:
                        continue
                    if isinstance(default, bool):
                        v = bool(v)
                    elif isinstance(default, int):
                        try:
                            v = int(v)
                        except (TypeError, ValueError):
                            continue
                    self.data[k] = v
            self.path.parent.mkdir(parents=True, exist_ok=True)
            # only what differs from the defaults, so a future default change still reaches this install
            saved = {k: v for k, v in self.data.items() if k == "api_keys" or v != DEFAULT_SETTINGS.get(k)}
            self.path.write_text(json.dumps(saved, indent=2, ensure_ascii=False), encoding="utf-8")

    def public(self) -> dict:
        """Settings safe to send to the browser: keys are masked."""
        keys = self.data.get("api_keys") or {}
        out = {k: v for k, v in self.data.items() if k != "api_keys"}
        out["api_keys"] = {}
        for k, (label, url) in API_KEYS.items():
            val = keys.get(k) or ""
            masked = f"{val[:3]}…{val[-3:]}" if len(val) > 8 else ("•••" if val else "")
            out["api_keys"][k] = {"label": label, "url": url, "set": bool(val), "masked": masked}
        return out
