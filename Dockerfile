FROM python:3.12-slim

RUN pip install uv --no-cache-dir

WORKDIR /kronos

# Layer 1: dep manifests (cached unless pyproject.toml / uv.lock change)
COPY pyproject.toml uv.lock ./

# Layer 2: kronos source (needed for hatchling to build the package)
COPY kronos/ kronos/

# Layer 3: install (layer cached when pyproject.toml + uv.lock + kronos/ unchanged)
RUN uv sync --frozen --no-dev --no-cache

# Layer 4: runtime files (cheap)
COPY cli/ cli/
COPY configs/ configs/
COPY VERSION ./

CMD ["uv", "run", "--no-dev", "kronos", "quickstart"]
