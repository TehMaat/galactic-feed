"""AI: configurazione (amministratore), prova del collegamento, stato e riassunti."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from ..ai import config, summary
from ..ai.providers import AIError, complete_json
from ..deps import AppContext, User, current_user, get_ctx, get_db, require_admin
from ..reading import query
from .common import prefs_with_defaults

router = APIRouter(prefix="/api", tags=["ai"])


def status_payload(cfg: config.AIConfig) -> dict:
    return {"enabled": cfg.enabled, "kind": cfg.kind if cfg.enabled else None, "label": cfg.label if cfg.enabled else ""}


@router.get("/ai/status")
def ai_status(_: User = Depends(current_user), conn: sqlite3.Connection = Depends(get_db)):
    return status_payload(config.load(conn))


def admin_payload(conn: sqlite3.Connection) -> dict:
    cfg = config.load(conn)
    last_error = config.get_setting(conn, config.PREFIX + "last_error") or None
    return {
        "provider": cfg.provider,
        "base_url": cfg.base_url,
        "model": cfg.model,
        "has_key": bool(cfg.api_key),
        "daily_limit": cfg.daily_limit,
        "enabled": cfg.enabled,
        "usage_today": config.usage_today(conn),
        "last_error": last_error,
        "providers": {
            k: {"kind": v["kind"], "label": v["label"], "base_url": v["base_url"], "model": v["model"], "needs_key": v["needs_key"]}
            for k, v in config.PROVIDERS.items()
        },
    }


@router.get("/admin/ai")
def get_ai_config(_: User = Depends(require_admin), conn: sqlite3.Connection = Depends(get_db)):
    return admin_payload(conn)


class AIConfigBody(BaseModel):
    provider: str = ""
    base_url: str = ""
    model: str = Field(default="", max_length=120)
    # None: la chiave resta quella salvata. "": si cancella.
    api_key: str | None = Field(default=None, max_length=400)
    daily_limit: int = Field(default=config.DEFAULT_DAILY_LIMIT, ge=1, le=100000)

    @field_validator("provider")
    @classmethod
    def _provider(cls, v: str) -> str:
        if v and v not in config.PROVIDERS:
            raise ValueError("Fornitore AI sconosciuto.")
        return v

    @field_validator("base_url")
    @classmethod
    def _url(cls, v: str) -> str:
        v = (v or "").strip()
        if v and not v.startswith(("http://", "https://")):
            raise ValueError("L'indirizzo deve iniziare con http:// o https://.")
        return v.rstrip("/")


@router.put("/admin/ai")
def put_ai_config(
    body: AIConfigBody,
    _: User = Depends(require_admin),
    conn: sqlite3.Connection = Depends(get_db),
    ctx: AppContext = Depends(get_ctx),
):
    current = config.load(conn)
    defaults = config.PROVIDERS.get(body.provider, {})
    cfg = config.AIConfig(
        provider=body.provider,
        base_url=body.base_url or defaults.get("base_url", ""),
        model=body.model.strip() or defaults.get("model", ""),
        api_key=current.api_key if body.api_key is None else body.api_key.strip(),
        daily_limit=body.daily_limit,
    )
    if body.provider == "ollama" and body.api_key is None:
        cfg.api_key = ""
    config.save(conn, cfg)
    config.set_error(conn, None)
    if ctx.relevance:
        ctx.relevance.paused_until = 0
    if ctx.scheduler:
        ctx.scheduler.wake()
    return admin_payload(conn)


@router.post("/admin/ai/test")
async def test_ai(_: User = Depends(require_admin), ctx: AppContext = Depends(get_ctx)):
    with ctx.db.session() as conn:
        cfg = config.load(conn)
    if not cfg.enabled:
        raise HTTPException(status_code=422, detail="Completa la configurazione: fornitore, modello e chiave se serve.")
    schema = {
        "type": "object",
        "properties": {"risposta": {"type": "string"}},
        "required": ["risposta"],
        "additionalProperties": False,
    }
    try:
        result = await complete_json(cfg, "Rispondi solo con il JSON richiesto.", 'Scrivi «ok» nel campo "risposta".', schema, max_tokens=2000)
    except AIError as exc:
        with ctx.db.session() as conn:
            config.set_error(conn, exc.message)
        raise HTTPException(status_code=502, detail=exc.message)
    with ctx.db.session() as conn:
        config.record_usage(conn, result.usage.input_tokens, result.usage.output_tokens)
        config.set_error(conn, None)
    return {"ok": True, "model": result.model, "message": f"Il modello {result.model} risponde."}


@router.post("/articles/{article_id}/summary")
async def article_summary(article_id: int, user: User = Depends(current_user), ctx: AppContext = Depends(get_ctx)):
    with ctx.db.session() as conn:
        if not query.is_visible(conn, user.id, article_id):
            raise HTTPException(status_code=404, detail="Articolo non trovato.")
        points = summary.cached(conn, article_id)
        if points:
            return {"points": points}
        if not prefs_with_defaults(user.prefs)["summaries"]:
            raise HTTPException(status_code=422, detail="I riassunti automatici sono spenti negli Interessi.")
        row = conn.execute("SELECT video_id, word_count FROM articles WHERE id = ?", (article_id,)).fetchone()
        if not summary.eligible(row):
            raise HTTPException(status_code=422, detail="L'articolo è troppo breve per un riassunto.")
    try:
        return {"points": await summary.summarize(ctx, article_id)}
    except AIError as exc:
        raise HTTPException(status_code=503, detail=exc.message)
