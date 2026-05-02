#!/usr/bin/env bash
set -euo pipefail

cd $(dirname "$0")

if [[ ! -x .venv/bin/python ]]; then
  uv sync --frozen --extra dev
fi

export FREECAD_GUI_BINARY=${FREECAD_GUI_BINARY:-/opt/freecad/usr/bin/freecadcmd}

exec .venv/bin/python tools/export.py "$@"
