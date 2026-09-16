#!/bin/sh
# Team-lead start script (Unix). Prefer start-ledger.bat on Windows.
set -e
HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
if [ -f "$HERE/pyproject.toml" ]; then
  ROOT=$HERE
elif [ -f "$HERE/../pyproject.toml" ]; then
  ROOT=$(CDPATH= cd -- "$HERE/.." && pwd)
else
  echo "Could not find pyproject.toml next to this script or in the parent folder." >&2
  exit 1
fi
cd "$ROOT"
VENV_PY="$ROOT/.venv/bin/python"
PREPARE="$ROOT/prepare_instance.py"
[ -f "$PREPARE" ] || PREPARE="$ROOT/pack/prepare_instance.py"

if [ ! -x "$VENV_PY" ]; then
  python3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)"
  python3 -m venv .venv
  "$VENV_PY" -m pip install --upgrade pip
  "$VENV_PY" -m pip install "setuptools>=68" wheel
  "$VENV_PY" -m pip install --no-build-isolation -e .
fi

"$VENV_PY" "$PREPARE"
"$VENV_PY" tasks.py db-init
exec "$VENV_PY" tasks.py run
