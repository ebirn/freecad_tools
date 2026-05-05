#!/usr/bin/env bash
set -euo pipefail

TOOL_DIR=$(dirname "$0")
export VIRTUAL_ENV=${TOOL_DIR}/.venv
source ${VIRTUAL_ENV}/bin/activate

if [[ ! -x "${VIRTUAL_ENV}/bin/python" ]]; then
  uv sync --frozen --extra dev
fi

export FREECAD_GUI_BINARY=${FREECAD_GUI_BINARY:-/opt/freecad/usr/bin/freecad}

if [[ -d /config/.XDG ]]; then
  export XDG_RUNTIME_DIR=/config/.XDG
  export WAYLAND_DISPLAY=wayland-0
  export DISPLAY=:0
  export QT_QPA_PLATFORM=xcb
fi

exec "${VIRTUAL_ENV}/bin/python" "${TOOL_DIR}/tools/export.py" "$@"
