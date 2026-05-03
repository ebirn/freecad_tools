FROM python:3.11-slim AS tools

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /freecad_tools

COPY --from=ghcr.io/astral-sh/uv:0.11.8 /uv /uvx /usr/local/bin/

COPY pyproject.toml uv.lock ./
# Optional: validate/lock/build your project here.
# This stage can use uv freely because it is not the FreeCAD runtime image.
RUN uv sync --frozen --no-dev

COPY . .

ENTRYPOINT ["uv", "run", "python", "tools/export.py"]


# syntax=docker/dockerfile:1.7

FROM lscr.io/linuxserver/freecad:latest AS freecad

COPY --from=tools /usr/local/bin/uv /usr/local/bin/uv
# COPY --from=tools /freecad_tools /freecad_tools


WORKDIR /freecad_tools

COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/config/.cache unset VIRTUAL_ENV && uv venv .venv --verbose --python=/opt/freecad/usr/bin/python
RUN --mount=type=cache,target=/config/.cache unset VIRTUAL_ENV && uv sync --verbose --frozen --no-dev
COPY . .

RUN chown -R abc:abc /freecad_tools

# Convenience command: run scripts with FreeCAD's runtime, not system Python.
# RUN printf '%s\n' \
#     '#!/bin/sh' \
#     'exec /opt/freecad/AppRun --console "$@"' \
#     > /usr/local/bin/freecad-python && \
#     chmod +x /usr/local/bin/freecad-python

WORKDIR /

# docker exec -it freecad /opt/freecad/AppRun --console /freecad_tools/tools/export.py
