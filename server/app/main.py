"""FastAPI application: API under /v1 and the mobile web app at /."""

from __future__ import annotations

import threading
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from . import sim_portal
from .api.routes import router
from .core.settings import Settings, load_settings
from .db.models import make_session_factory
from .services import RequestError, purge_expired_audio
from .stt.base import NotConfigured
from .stt.providers import VoskStt, get_stt

APP_ORIGINS = ("http://localhost",)  # Android app (Capacitor, androidScheme "http")

WEB_DIR = Path(__file__).parent / "web"


def _error(status: int, code: str, message: str, details: list | None = None) -> JSONResponse:
    return JSONResponse({"error": {"code": code, "message": message, "details": details or []}}, status_code=status)


def create_app(settings: Settings | None = None, stt=None, warm_stt: bool = True) -> FastAPI:
    cfg = settings or load_settings()
    app = FastAPI(title="A.U.R.A. prototype", version="0.3.0", docs_url=None, redoc_url=None)
    app.state.settings = cfg
    app.state.sessions = make_session_factory(cfg.database_url)
    app.state.stt_instance = stt

    def resolve_stt():
        if app.state.stt_instance is None:
            app.state.stt_instance = get_stt(cfg.stt_provider)
        return app.state.stt_instance

    def stt_status() -> dict:
        try:
            inst = resolve_stt()
        except NotConfigured:
            return {"provider": cfg.stt_provider, "languages": [], "simulated": False}
        langs = inst.languages() if hasattr(inst, "languages") else ["hi", "en"]
        return {"provider": inst.name, "languages": langs, "simulated": inst.name == "mock"}

    app.state.get_stt = resolve_stt
    app.state.stt_status = stt_status

    with app.state.sessions() as db:
        purge_expired_audio(db, cfg)

    if warm_stt and stt is None:
        def warm() -> None:  # load models early so the first recording is not slow
            try:
                inst = resolve_stt()
                if isinstance(inst, VoskStt):
                    for path in inst.model_dirs.values():
                        if path.is_dir():
                            inst._load(path)
            except NotConfigured:
                pass

        threading.Thread(target=warm, daemon=True).start()

    @app.exception_handler(RequestError)
    def on_request_error(_: Request, exc: RequestError) -> JSONResponse:
        return _error(exc.status, exc.code, exc.message, exc.details)

    @app.exception_handler(RequestValidationError)
    def on_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        details = [{"path": ".".join(str(p) for p in e["loc"]), "code": e["type"], "message": e["msg"]} for e in exc.errors()]
        return _error(422, "INVALID_REQUEST", "Request is not valid", details)

    @app.middleware("http")
    async def headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["Permissions-Policy"] = "microphone=(self), geolocation=(), camera=()"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "no-store" if request.url.path.startswith("/v1") else "no-cache"
        return response

    # The Android app (mobile/, Capacitor) serves its pages from http://localhost inside the APK and calls this API
    # cross-origin. Only that origin is allowed; the login token travels in the Authorization header, not cookies.
    app.add_middleware(CORSMiddleware, allow_origins=list(APP_ORIGINS), allow_credentials=False,
                       allow_methods=["GET", "POST", "PATCH", "DELETE"],
                       allow_headers=["Authorization", "Content-Type"])
    app.include_router(router)
    app.include_router(sim_portal.router)  # SIMULATED practice forms for the autofill demo
    app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
    return app


def app_factory() -> FastAPI:
    return create_app()
