from pathlib import Path


def test_dockerfile_allows_uv_dependency_cache() -> None:
    dockerfile = Path("Dockerfile").read_text()

    assert "uv sync --frozen --no-dev --no-cache" not in dockerfile
    assert "RUN uv sync --frozen --no-dev" in dockerfile
    assert "ENV UV_NO_SYNC=1" in dockerfile
