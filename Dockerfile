FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl git build-essential nodejs npm \
    && rm -rf /var/lib/apt/lists/*
RUN pip install uv --no-cache-dir

WORKDIR /kronos
COPY pyproject.toml uv.lock ./
RUN uv sync --dev --no-cache

COPY kronos/ kronos/
COPY cli/ cli/
COPY configs/ configs/
COPY tests/ tests/
COPY VERSION ./
COPY README.md README.en.md ./

COPY web/package.json web/package-lock.json web/
RUN cd web && npm install
COPY web/ web/

EXPOSE 3000 8000

CMD ["uv", "run", "kronos", "quickstart"]
