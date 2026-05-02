FROM python:3.13-slim AS slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /workspace

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --extra dev

COPY . .

ENTRYPOINT ["uv", "run", "python", "tools/export.py"]


FROM lscr.io/linuxserver/freecad:latest AS freecad

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1


COPY . /freecad_tools
WORKDIR /freecad_tools

RUN python3 -m pip install --no-cache-dir uv

RUN uv sync --frozen --extra dev

# restore original
WORKDIR /
