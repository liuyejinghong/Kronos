"""Integration tests for the local Kronos Web API app."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi.testclient import TestClient

from kronos.web import create_app

if TYPE_CHECKING:
    from pathlib import Path


def test_health_endpoint(tmp_path: Path) -> None:
    app = create_app(project_root=tmp_path)
    client = TestClient(app)

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "kronos-web-api"}


def test_openapi_exposes_local_api(tmp_path: Path) -> None:
    app = create_app(project_root=tmp_path)
    client = TestClient(app)

    response = client.get("/api/openapi.json")

    assert response.status_code == 200
    assert response.json()["info"]["title"] == "Kronos Agent Web API"
