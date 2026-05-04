"""FastAPI app factory for the local Kronos Agent workbench."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from fastapi import FastAPI, Request

from kronos.web.schemas import HealthResponse


@dataclass(frozen=True)
class WebAppContext:
    """Local filesystem roots used by the Web API."""

    project_root: Path
    runtime_path: Path
    research_path: Path
    secret_store_path: Path
    material_store_path: Path


def create_app(
    *,
    project_root: str | Path | None = None,
    runtime_path: str | Path | None = None,
    research_path: str | Path | None = None,
    secret_store_path: str | Path | None = None,
    material_store_path: str | Path | None = None,
) -> FastAPI:
    """Create the local FastAPI app for the Kronos Agent workbench."""
    root = Path(project_root or ".").resolve()
    context = WebAppContext(
        project_root=root,
        runtime_path=Path(runtime_path or root / "reports" / "agent_runtime"),
        research_path=Path(research_path or root / "reports" / "research"),
        secret_store_path=Path(secret_store_path or root / ".kronos-secrets" / "agent_secrets.json"),
        material_store_path=Path(
            material_store_path or root / "reports" / "agent_materials" / "materials.jsonl"
        ),
    )

    app = FastAPI(
        title="Kronos Agent Web API",
        version="0.1.0",
        docs_url="/api/docs",
        redoc_url=None,
        openapi_url="/api/openapi.json",
    )
    app.state.kronos_context = context

    @app.get("/api/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse()

    from kronos.web.routes.agent import router as agent_router
    from kronos.web.routes.approvals import router as approvals_router
    from kronos.web.routes.candidates import router as candidates_router
    from kronos.web.routes.events import router as events_router
    from kronos.web.routes.materials import router as materials_router
    from kronos.web.routes.settings import router as settings_router

    app.include_router(agent_router)
    app.include_router(candidates_router)
    app.include_router(events_router)
    app.include_router(settings_router)
    app.include_router(materials_router)
    app.include_router(approvals_router)
    return app


def get_context(request: Request) -> WebAppContext:
    """Return the Kronos local app context from FastAPI state."""
    context = getattr(request.app.state, "kronos_context", None)
    if not isinstance(context, WebAppContext):
        raise RuntimeError("Kronos Web API context is not configured.")
    return context
