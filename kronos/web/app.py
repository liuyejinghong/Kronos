# ruff: noqa: RUF001, RUF002 -- Chinese user-facing security messages use fullwidth punctuation.
"""FastAPI app factory for the local Kronos Agent workbench."""

from __future__ import annotations

import os
import secrets
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Final
from urllib.parse import urlparse

from fastapi import FastAPI, Request
from pydantic import BaseModel, ConfigDict
from starlette.datastructures import Headers
from starlette.responses import JSONResponse

from kronos.agent.secrets import resolve_secret_store_path
from kronos.web.schemas import HealthResponse

if TYPE_CHECKING:
    from starlette.types import ASGIApp, Receive, Scope, Send

#: Header carrying the per-process local session token on write requests.
LOCAL_TOKEN_HEADER: Final[str] = "X-Kronos-Local-Token"
#: Optional env override for the local session token (e.g. launcher-provided).
KRONOS_WEB_TOKEN_ENV: Final[str] = "KRONOS_WEB_TOKEN"
#: Env kill-switch for the local write security middleware ("off" disables it;
#: intended for the pre-P19 integration tests, never for production).
KRONOS_WEB_LOCAL_SECURITY_ENV: Final[str] = "KRONOS_WEB_LOCAL_SECURITY"
#: Hosts a write request may target (DNS-rebinding guard).
_LOOPBACK_HOSTS: Final[frozenset[str]] = frozenset({"127.0.0.1", "localhost", "::1"})
#: Methods that can never mutate state; the middleware only screens the rest.
_SAFE_METHODS: Final[frozenset[str]] = frozenset({"GET", "HEAD", "OPTIONS"})
#: Paths exempt from the write screening regardless of method.
_EXEMPT_PATHS: Final[frozenset[str]] = frozenset({"/api/health"})


class LocalSessionTokenResponse(BaseModel):
    """Same-origin bootstrap payload for the local write token."""

    model_config = ConfigDict(extra="forbid")

    token: str


def _loopback_host_name(host_header: str) -> str:
    """Extract the hostname from a ``Host`` header (port and brackets off)."""
    value = host_header.strip().lower()
    if value.startswith("["):
        end = value.find("]")
        return value[1:end] if end != -1 else value[1:]
    if ":" in value:
        return value.rsplit(":", 1)[0]
    return value


def _origin_hostname(origin: str) -> str | None:
    """Return the hostname of an ``Origin`` header value, or None if foreign."""
    parsed = urlparse(origin.strip())
    if parsed.scheme not in ("http", "https"):
        return None
    return parsed.hostname


class LocalSecurityMiddleware:
    """Reject write requests that are not provably local same-origin (403).

    Spec ``security-boundary``: 服务默认仅监听 loopback；写接口必须校验本地
    会话令牌与 Origin/Host。Every non-safe-method request to a non-exempt
    path must (a) target a loopback ``Host`` (anti DNS-rebinding), (b) carry
    a loopback ``Origin`` when it carries one at all (anti cross-site write),
    and (c) carry ``X-Kronos-Local-Token`` matching the per-process token
    issued via the CORS-protected ``GET /api/session-token`` (a foreign page
    can send requests but can never read the token back).
    """

    def __init__(self, app: ASGIApp, token: str) -> None:
        self.app = app
        self.token = token

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if (
            scope["type"] != "http"
            or scope["method"] in _SAFE_METHODS
            or scope["path"] in (_EXEMPT_PATHS)
        ):
            await self.app(scope, receive, send)
            return
        headers = Headers(scope=scope)
        reason = self._reject_reason(headers)
        if reason is not None:
            response = JSONResponse(status_code=403, content={"detail": reason})
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)

    def _reject_reason(self, headers: Headers) -> str | None:
        host = _loopback_host_name(headers.get("host", ""))
        if host not in _LOOPBACK_HOSTS:
            return (
                "本地安全校验失败：Host 必须是本机回环地址"
                "（127.0.0.1 / localhost / [::1]），非回环写请求已拒绝。"
            )
        origin = headers.get("origin")
        if origin and _origin_hostname(origin) not in _LOOPBACK_HOSTS:
            return "本地安全校验失败：已拒绝非同源（跨站）写请求。"
        if headers.get(LOCAL_TOKEN_HEADER.lower()) != self.token:
            return (
                "本地安全校验失败：缺少或不匹配的本地会话令牌；"
                f"请先请求 GET /api/session-token，再以 {LOCAL_TOKEN_HEADER} 头携带。"
            )
        return None


def _local_security_enabled() -> bool:
    """Local write security is ON by default; the env var is a test opt-out."""
    return os.environ.get(KRONOS_WEB_LOCAL_SECURITY_ENV, "on").strip().lower() not in {
        "off",
        "0",
        "false",
        "no",
    }


def local_security_enabled() -> bool:
    """Public read of the local-write-security switch (route-level checks)."""
    return _local_security_enabled()


@dataclass(frozen=True)
class WebAppContext:
    """Local filesystem roots used by the Web API."""

    project_root: Path
    runtime_path: Path
    research_path: Path
    secret_store_path: Path
    material_store_path: Path
    paper_path: Path
    #: State directory for the v0.5.0 conversation runtime (conversations /
    #: tasks / budget SQLite stores); created lazily by the service.
    state_path: Path = field(default_factory=lambda: Path("state"))
    #: Local market data root (mirrors ``[data] base_path`` in configs/*.toml).
    data_path: Path = field(default_factory=lambda: Path("data"))
    #: Directory where frozen data-snapshot manifests are written.
    snapshots_path: Path = field(default_factory=lambda: Path("state") / "snapshots")
    #: Pinned freqtrade virtualenv used by the research verdict bridge.
    freqtrade_venv_path: Path = field(default_factory=lambda: Path(".tools") / "freqtrade-venv")


def create_app(
    *,
    project_root: str | Path | None = None,
    runtime_path: str | Path | None = None,
    research_path: str | Path | None = None,
    secret_store_path: str | Path | None = None,
    material_store_path: str | Path | None = None,
    paper_path: str | Path | None = None,
    state_path: str | Path | None = None,
    data_path: str | Path | None = None,
    snapshots_path: str | Path | None = None,
    freqtrade_venv_path: str | Path | None = None,
) -> FastAPI:
    """Create the local FastAPI app for the Kronos Agent workbench."""
    root = Path(project_root or ".").resolve()
    context = WebAppContext(
        project_root=root,
        runtime_path=Path(runtime_path or root / "reports" / "agent_runtime"),
        research_path=Path(research_path or root / "reports" / "research"),
        secret_store_path=Path(secret_store_path or resolve_secret_store_path()),
        material_store_path=Path(
            material_store_path or root / "reports" / "agent_materials" / "materials.jsonl"
        ),
        paper_path=Path(paper_path or root / "reports" / "paper"),
        state_path=Path(state_path or root / "state"),
        data_path=Path(data_path or root / "data"),
        snapshots_path=Path(snapshots_path or root / "state" / "snapshots"),
        freqtrade_venv_path=Path(
            freqtrade_venv_path
            or os.environ.get("KRONOS_FREQTRADE_VENV")
            or root / ".tools" / "freqtrade-venv"
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

    # Per-process local session token (security-boundary spec). The launcher
    # may pin it via KRONOS_WEB_TOKEN; otherwise it is random per process and
    # bootstrapped to the same-origin frontend through /api/session-token.
    local_token = os.environ.get(KRONOS_WEB_TOKEN_ENV) or secrets.token_urlsafe(32)
    app.state.kronos_local_token = local_token

    # P14b: real pipeline worker (ensure_data / evaluate_strategy) polling the
    # shared runtime store in-process; daemon thread stops with the process.
    from kronos.conversation.pipeline_wiring import attach_worker

    attach_worker(
        app.state,
        base_path=context.data_path,
        state_dir=context.state_path,
        snapshots_dir=context.snapshots_path,
        venv_dir=context.freqtrade_venv_path,
    )

    @app.get("/api/session-token", response_model=LocalSessionTokenResponse)
    def local_session_token() -> LocalSessionTokenResponse:
        """Issue the local write token to same-origin readers only.

        GET routes are exempt from the write screening, and the app ships no
        CORS headers, so a foreign page can hit this URL but can never read
        the response — the browser blocks the cross-origin read. Same-origin
        pages (via the Next.js proxy) cache the token and attach it as
        ``X-Kronos-Local-Token`` on write requests.
        """
        return LocalSessionTokenResponse(token=local_token)

    @app.get("/api/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse()

    if _local_security_enabled():
        app.add_middleware(LocalSecurityMiddleware, token=local_token)

    from kronos.web.routes.agent import router as agent_router
    from kronos.web.routes.approvals import router as approvals_router
    from kronos.web.routes.candidates import router as candidates_router
    from kronos.web.routes.conversation import router as conversation_router
    from kronos.web.routes.events import router as events_router
    from kronos.web.routes.materials import router as materials_router
    from kronos.web.routes.memory import router as memory_router
    from kronos.web.routes.paper import router as paper_router
    from kronos.web.routes.settings import router as settings_router

    app.include_router(agent_router)
    app.include_router(memory_router)
    app.include_router(candidates_router)
    app.include_router(events_router)
    app.include_router(settings_router)
    app.include_router(materials_router)
    app.include_router(paper_router)
    app.include_router(approvals_router)
    app.include_router(conversation_router)
    return app


def get_context(request: Request) -> WebAppContext:
    """Return the Kronos local app context from FastAPI state."""
    context = getattr(request.app.state, "kronos_context", None)
    if not isinstance(context, WebAppContext):
        raise RuntimeError("Kronos Web API context is not configured.")
    return context
