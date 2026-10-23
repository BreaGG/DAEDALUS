"""Command line entry point: `python -m daedalus` or `daedalus`."""

from __future__ import annotations

import argparse
import os
import socket
import sys
import threading
import webbrowser
from pathlib import Path

BANNER = r"""
   ___  ___   ____ ___   ___   __   __  ______
  / _ \/ _ | / __// _ \ / _ | / /  / / / / __/
 / // / __ |/ _/ / // // __ |/ /__/ /_/ /\ \
/____/_/ |_/___//____//_/ |_/____/\____/___/
   every labyrinth has a way out
"""

RAILWAY_VARS = ("RAILWAY_ENVIRONMENT_NAME", "RAILWAY_ENVIRONMENT", "RAILWAY_PROJECT_ID", "RAILWAY_SERVICE_ID")


def _in_use(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1" if host in ("0.0.0.0", "") else host, port)) == 0


def default_port() -> int:
    """DAEDALUS_PORT, else PORT (set by Railway, Render, Fly…), else 8787."""
    return int(os.environ.get("DAEDALUS_PORT") or os.environ.get("PORT") or 8787)


def on_railway() -> bool:
    return any(os.environ.get(v) for v in RAILWAY_VARS)


def hosting_problems() -> list[str]:
    """Fatal misconfigurations when running on Railway (a public URL with no login would be an open OSINT proxy)."""
    if not on_railway():
        return []
    problems = []
    if not os.environ.get("DAEDALUS_PASSWORD") and os.environ.get("DAEDALUS_ALLOW_PUBLIC") != "1":
        problems.append("DAEDALUS_PASSWORD is not set. Add it in the service's Variables tab (a long random string); "
                        "set DAEDALUS_ALLOW_PUBLIC=1 only if you really want the app open to anyone.")
    return problems


def drop_privileges(data_dir: Path, user: str) -> bool:
    """Started as root (Railway mounts volumes as root): hand the data dir to `user` and switch to it."""
    if os.name != "posix" or os.geteuid() != 0 or not user:
        return False
    import pwd

    try:
        pw = pwd.getpwnam(user)
    except KeyError:
        print(f"  WARNING: user {user!r} does not exist, staying root")
        return False
    try:
        data_dir.mkdir(parents=True, exist_ok=True)
        for root, dirs, files in os.walk(data_dir):
            for name in [root, *(os.path.join(root, x) for x in dirs + files)]:
                os.chown(name, pw.pw_uid, pw.pw_gid)
    except OSError as e:
        print(f"  WARNING: cannot hand {data_dir} to {user} ({e}), staying root")
        return False
    os.setgroups([])
    os.setgid(pw.pw_gid)
    os.setuid(pw.pw_uid)
    os.environ["HOME"] = pw.pw_dir
    return True


def main(argv: list[str] | None = None) -> None:
    from .config import default_data_dir

    parser = argparse.ArgumentParser(prog="daedalus", description="DAEDALUS - open-source link analysis & OSINT")
    parser.add_argument("--host", default=os.environ.get("DAEDALUS_HOST", "127.0.0.1"),
                        help="interface to bind (default 127.0.0.1)")
    parser.add_argument("--port", type=int, default=default_port())
    parser.add_argument("--data-dir", default=None, help="where cases and settings are stored")
    parser.add_argument("--no-browser", action="store_true", help="do not open the browser")
    args = parser.parse_args(argv)
    data_dir = Path(args.data_dir).expanduser() if args.data_dir else default_data_dir()

    problems = hosting_problems()
    if problems:
        for p in problems:
            print(f"  ERROR: {p}", file=sys.stderr)
        sys.exit(1)
    if on_railway() and not os.environ.get("RAILWAY_VOLUME_MOUNT_PATH") and not os.environ.get("DAEDALUS_DATA_DIR"):
        print("  WARNING: no Railway volume attached: cases and settings will be lost on every redeploy. "
              "Attach a volume to this service (any mount path).")

    drop_privileges(data_dir, os.environ.get("DAEDALUS_RUN_AS", ""))

    url = f"http://{'127.0.0.1' if args.host in ('0.0.0.0', '') else args.host}:{args.port}"
    if _in_use(args.host, args.port):
        print(f"\n  DAEDALUS is already running at {url}\n")
        if not args.no_browser:
            webbrowser.open(url)
        return

    import uvicorn

    from .api import create_app

    if args.host not in ("127.0.0.1", "localhost", "::1") and not os.environ.get("DAEDALUS_PASSWORD"):
        print("  WARNING: listening on a public interface without DAEDALUS_PASSWORD set. "
              "Anyone who can reach this port can use the tool.")
    app = create_app(data_dir)
    print(BANNER)
    print(f"  Running at {url}  ·  data in {data_dir}  (Ctrl+C to stop)\n")
    if not args.no_browser:
        threading.Timer(1.5, lambda: webbrowser.open(url)).start()
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
