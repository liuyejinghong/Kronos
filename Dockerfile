FROM python:3.12-slim

RUN pip install uv --no-cache-dir

WORKDIR /kronos
COPY pyproject.toml uv.lock ./
RUN uv sync --no-cache

COPY kronos/ kronos/
COPY cli/ cli/
COPY configs/ configs/
COPY VERSION ./
COPY README.md README.en.md ./

CMD ["uv", "run", "kronos", "quickstart"]
