"""Crea l'applicazione: API sotto /api, PWA su tutti gli altri indirizzi."""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from pydantic import ValidationError

from .api import account, admin, ai, articles, auth, editions, push, folders, images, interests, invites, opml, sources
from .config import VERSION, Settings
from .deps import AppContext
from .feeds.extract import Extractor
from .feeds.fetcher import Fetcher
from .feeds.net import make_client
from .ai.relevance import RelevanceWorker
from .feeds.scheduler import Scheduler
from .push.notifier import Notifier
from .security import same_origin_request

log = logging.getLogger("galactic_feed")

# File della PWA che il browser deve sempre ricontrollare (gli altri hanno un nome con hash).
NO_CACHE_FILES = {"index.html", "sw.js", "manifest.webmanifest", "registerSW.js"}


def _validation_message(errors: list[dict]) -> str:
    """Trasforma gli errori di validazione in una frase in italiano."""
    for err in errors:
        if err.get("type") == "value_error":
            msg = str(err.get("msg", ""))
            return msg.removeprefix("Value error, ")
    for err in errors:
        field = ".".join(str(p) for p in err.get("loc", ()) if p not in ("body", "query", "path"))
        if field:
            return f"Il campo «{field}» manca o non è valido."
    return "I dati inviati non sono validi."


def _request_origin(request: Request) -> str:
    host = request.headers.get("x-forwarded-host") or request.headers.get("host", "")
    host = host.split(",")[0].strip()
    return f"{request.url.scheme}://{host}"


class DataDirError(RuntimeError):
    pass


def check_data_dir(path: Path) -> None:
    """La cartella dei dati deve esistere ed essere scrivibile: altrimenti un messaggio chiaro."""
    try:
        path.mkdir(parents=True, exist_ok=True)
        writable = os.access(path, os.W_OK | os.X_OK)
    except OSError:
        writable = False
    if writable:
        return
    uid = os.getuid() if hasattr(os, "getuid") else "?"
    gid = os.getgid() if hasattr(os, "getgid") else "?"
    message = (
        f"La cartella dei dati {path} non è scrivibile dall'utente del server (uid {uid}). "
        f"Se nel container hai montato una cartella del computer, rendila sua con: "
        f"sudo chown -R {uid}:{gid} <cartella>. Oppure usa un volume Docker, come in docker-compose.yml."
    )
    log.error(message)
    raise DataDirError(message)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    ctx = AppContext(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        check_data_dir(settings.data_dir)
        ctx.db.init()
        ctx.load_secret()
        with ctx.db.session() as conn:
            no_users = conn.execute("SELECT 1 FROM users LIMIT 1").fetchone() is None
        ctx.refresh_setup_code(no_users)
        ctx.http = make_client(settings)
        ctx.fetcher = Fetcher(ctx)
        ctx.extractor = Extractor(ctx)
        ctx.relevance = RelevanceWorker(ctx)
        ctx.notifier = Notifier(ctx)
        ctx.notifier.start()
        ctx.hooks.edition_ready.append(ctx.notifier.edition_ready)
        ctx.scheduler = Scheduler(ctx)
        if settings.scheduler_enabled:
            ctx.scheduler.start()
        log.info("Galactic Feed %s pronto su %s (dati in %s)", VERSION, settings.public_url, settings.data_dir)
        try:
            yield
        finally:
            await ctx.scheduler.stop()
            await ctx.http.aclose()
            await ctx.notifier.close()

    app = FastAPI(
        title="Galactic Feed",
        version=VERSION,
        lifespan=lifespan,
        docs_url="/api/docs",
        redoc_url=None,
        openapi_url="/api/openapi.json",
    )
    app.state.ctx = ctx

    @app.exception_handler(RequestValidationError)
    async def _request_invalid(_: Request, exc: RequestValidationError):
        return JSONResponse(status_code=422, content={"detail": _validation_message(exc.errors())})

    @app.exception_handler(ValidationError)
    async def _model_invalid(_: Request, exc: ValidationError):
        return JSONResponse(status_code=422, content={"detail": _validation_message(exc.errors())})

    @app.middleware("http")
    async def _protect(request: Request, call_next):
        if request.url.path.startswith("/api/") and not same_origin_request(
            request.method, request.headers, settings, _request_origin(request)
        ):
            return JSONResponse(
                status_code=403,
                content={"detail": "Richiesta rifiutata: arriva da un sito diverso da Galactic Feed."},
            )
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("X-Frame-Options", "DENY")
        if request.url.path.startswith("/api/"):
            response.headers.setdefault("Cache-Control", "no-store")
        return response

    @app.get("/api/health", tags=["sistema"])
    def health():
        with ctx.db.session() as conn:
            conn.execute("SELECT 1").fetchone()
        return {"status": "ok", "version": VERSION}

    for module in (auth, invites, account, admin, folders, sources, opml, ai, articles, editions, interests, images, push):
        app.include_router(module.router)

    @app.api_route("/api/{rest:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"], include_in_schema=False)
    def api_not_found(rest: str):
        return JSONResponse(status_code=404, content={"detail": "Indirizzo dell'API inesistente."})

    _mount_frontend(app, settings.frontend_dir)
    return app


def _mount_frontend(app: FastAPI, dist: Path) -> None:
    """Serve la PWA compilata. Gli indirizzi che non sono file portano all'app (index.html)."""
    dist = dist.resolve()

    def file_response(path: Path) -> FileResponse:
        rel = path.relative_to(dist).as_posix()
        if rel in NO_CACHE_FILES or rel.startswith("icons/"):
            cache = "no-cache"
        elif rel.startswith("assets/"):
            cache = "public, max-age=31536000, immutable"
        else:
            cache = "public, max-age=3600"
        headers = {"Cache-Control": cache}
        if rel == "sw.js":
            headers["Service-Worker-Allowed"] = "/"
        media = "application/manifest+json" if rel.endswith(".webmanifest") else None
        return FileResponse(path, headers=headers, media_type=media)

    @app.api_route("/{path:path}", methods=["GET", "HEAD"], include_in_schema=False)
    def frontend(path: str):
        index = dist / "index.html"
        if not index.is_file():
            return HTMLResponse(
                "<!doctype html><meta charset=utf-8><title>Galactic Feed</title>"
                "<p>Il server funziona, ma l'interfaccia non è stata compilata. "
                "Le API sono su <a href=/api/docs>/api/docs</a>.</p>",
                status_code=503,
            )
        if path:
            candidate = (dist / path).resolve()
            if candidate.is_relative_to(dist) and candidate.is_file():
                return file_response(candidate)
        return file_response(index)
