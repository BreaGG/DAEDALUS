#!/usr/bin/env sh
# Creates a virtualenv on first run, installs dependencies and starts DAEDALUS.
set -e
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then
  echo "[DAEDALUS] creating virtual environment..."
  python3 -m venv .venv
fi
.venv/bin/python -m pip install --disable-pip-version-check -q -r requirements.txt
exec .venv/bin/python -m daedalus "$@"
