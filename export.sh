#!/usr/bin/env bash
set -euo pipefail

TOOL_DIR=$(dirname "$0")

cd ${TOOL_DIR}
export VIRTUAL_ENV=${TOOL_DIR}/.venv
source ${VIRTUAL_ENV}/bin/activate

if [[ ! -x .venv/bin/python ]]; then
  uv sync --frozen --extra dev
fi

export FREECAD_GUI_BINARY=${FREECAD_GUI_BINARY:-/opt/freecad/usr/bin/freecadcmd}

exec .venv/bin/python tools/export.py "$@"
