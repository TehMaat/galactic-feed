"""AI: configurazione, filtro delle notizie (Ollama simulato) e riassunti (Claude simulato)."""

from __future__ import annotations

import asyncio
import json

import anthropic
import httpx
import httpx2
import pytest
import respx

from app.ai import providers

from conftest import invite_user
from helpers import entry, feed

OLLAMA = "http://ollama.test/v1"
LONG = " ".join(["Il telescopio ha osservato una galassia lontana con dettagli mai visti prima."] * 40)


def chat_reply(content: dict | str, status: int = 200) -> httpx.Response:
    text = content if isinstance(content, str) else json.dumps(content)
    return httpx.Response(
        status,
        json={"model": "finto", "choices": [{"message": {"content": text}, "finish_reason": "stop"}], "usage": {"prompt_tokens": 50, "completion_tokens": 9}},
    )


def use_ollama(admin):
    r = admin.put("/api/admin/ai", json={"provider": "ollama", "base_url": OLLAMA, "model": "finto"})
    assert r.status_code == 200, r.text
    return r.json()


def test_admin_config_and_status(admin, app):
    bruno = invite_user(admin, app, "bruno")
    assert bruno.get("/api/admin/ai").status_code == 403
    assert bruno.get("/api/ai/status").json() == {"enabled": False, "kind": None, "label": ""}

    r = admin.put("/api/admin/ai", json={"provider": "anthropic"}).json()
    assert r["model"] == "claude-opus-5-5" and r["enabled"] is False and r["has_key"] is False
    r = admin.put("/api/admin/ai", json={"provider": "anthropic", "model": "claude-haiku-5-5", "api_key": "sk-segreta"}).json()
    assert r["enabled"] is True and r["has_key"] is True
    assert "sk-segreta" not in json.dumps(r)
    # Senza api_key la chiave salvata resta.
    assert admin.put("/api/admin/ai", json={"provider": "anthropic", "model": "claude-haiku-5-5"}).json()["has_key"] is True
    assert bruno.get("/api/ai/status").json() == {"enabled": True, "kind": "cloud", "label": "Anthropic (Claude)"}
    assert bruno.get("/api/interests").json()["ai"]["enabled"] is True

    bad = admin.put("/api/admin/ai", json={"provider": "ollama", "base_url": "ollama:11434"})
    assert bad.status_code == 422 and "http://" in bad.json()["detail"]
    assert admin.put("/api/admin/ai", json={"provider": "altro"}).status_code == 422


@respx.mock
def test_test_button_reports_errors(admin):
    use_ollama(admin)
    respx.post(f"{OLLAMA}/chat/completions").mock(return_value=chat_reply({"risposta": "ok"}))
    r = admin.post("/api/admin/ai/test")
    assert r.status_code == 200 and r.json()["ok"] is True
    assert admin.get("/api/admin/ai").json()["usage_today"]["requests"] == 1

    respx.post(f"{OLLAMA}/chat/completions").mock(return_value=httpx.Response(404, json={"error": "model not found"}))
    r = admin.post("/api/admin/ai/test")
    assert r.status_code == 502 and "non trovato" in r.json()["detail"]
    assert "non trovato" in admin.get("/api/admin/ai").json()["last_error"]

    respx.post(f"{OLLAMA}/chat/completions").mock(side_effect=httpx.ConnectError("no"))
    assert "Non riesco a collegarmi" in admin.post("/api/admin/ai/test").json()["detail"]


@respx.mock
def test_ai_filter_modes(admin, app):
    ids = feed(app, admin, "https://orbita.example/feed", [
        entry("Una galassia lontana fotografata dal telescopio", excerpt="Astronomi entusiasti.", hours_ago=1),
        entry("Ricetta della carbonara", excerpt="Uova e guanciale.", hours_ago=2),
        entry("Il razzo è pronto al lancio", excerpt="Conto alla rovescia.", hours_ago=3),
    ], title="Orbita")
    use_ollama(admin)
    admin.post("/api/interests/keywords", json={"keyword": "razzo"})
    seen_prompts = []

    def answer(request):
        body = json.loads(request.content)
        prompt = body["messages"][1]["content"]
        seen_prompts.append(prompt)
        assert body["response_format"]["type"] == "json_schema"
        items = []
        for line in prompt.splitlines():
            if line.startswith("["):
                n = int(line[1 : line.index("]")])
                relevant = "galassia" in line
                items.append({"n": n, "pertinenza": "alta" if relevant else "no", "tema": "astronomia" if relevant else ""})
        return chat_reply({"articoli": items})

    respx.post(f"{OLLAMA}/chat/completions").mock(side_effect=answer)

    def perte():
        return {a["title"]: a["match"]["keyword"] for a in admin.get("/api/articles?view=perte").json()["items"]}

    # Solo parole chiave: l'AI non viene chiamata.
    assert asyncio.run(app.state.ctx.relevance.run()) == 0
    assert perte() == {"Il razzo è pronto al lancio": "razzo"}

    # Entrambi: l'AI valuta solo gli articoli senza un interesse.
    admin.patch("/api/me", json={"prefs": {"ai_mode": "entrambi", "ai_text": "Astronomia e spazio profondo"}})
    assert asyncio.run(app.state.ctx.relevance.run()) == 1
    assert "razzo" not in seen_prompts[-1] and "Astronomia e spazio profondo" in seen_prompts[-1]
    assert perte() == {"Il razzo è pronto al lancio": "razzo", "Una galassia lontana fotografata dal telescopio": "astronomia"}
    # Ogni articolo si valuta una volta sola.
    assert asyncio.run(app.state.ctx.relevance.run()) == 0

    # Solo AI: gli interessi non contano più; l'articolo del razzo va valutato.
    admin.patch("/api/me", json={"prefs": {"ai_mode": "ai"}})
    assert perte() == {"Una galassia lontana fotografata dal telescopio": "astronomia"}
    assert asyncio.run(app.state.ctx.relevance.run()) == 1
    assert perte() == {"Una galassia lontana fotografata dal telescopio": "astronomia"}

    # Descrizione nuova: si ricomincia da capo.
    admin.patch("/api/me", json={"prefs": {"ai_text": "Solo cucina"}})
    assert perte() == {}
    assert asyncio.run(app.state.ctx.relevance.run()) == 1
    assert len(ids) == 3


@respx.mock
def test_ai_filter_pauses_after_error_and_respects_limit(admin, app):
    feed(app, admin, "https://a.example/feed", [entry(f"Notizia {i}", hours_ago=1) for i in range(3)], title="A")
    admin.put("/api/admin/ai", json={"provider": "ollama", "base_url": OLLAMA, "model": "finto", "daily_limit": 1})
    admin.patch("/api/me", json={"prefs": {"ai_mode": "ai", "ai_text": "tutto"}})
    route = respx.post(f"{OLLAMA}/chat/completions").mock(return_value=chat_reply("non è JSON"))
    worker = app.state.ctx.relevance
    assert asyncio.run(worker.run()) == 0
    assert "formato" in admin.get("/api/admin/ai").json()["last_error"]
    assert asyncio.run(worker.run()) == 0 and route.call_count == 1  # in pausa
    worker.paused_until = 0
    route.mock(return_value=chat_reply({"articoli": []}))
    assert asyncio.run(worker.run()) == 1
    assert admin.get("/api/admin/ai").json()["last_error"] is None
    # Tetto giornaliero (1 richiesta): niente altre chiamate.
    admin.patch("/api/me", json={"prefs": {"ai_text": "altro"}})
    assert asyncio.run(worker.run()) == 0


@pytest.fixture
def claude(monkeypatch):
    """Claude simulato: risponde alle richieste dell'SDK senza rete."""
    calls = []
    state = {"stop_reason": "end_turn", "text": json.dumps({"punti": ["Primo fatto.", "Secondo fatto.", "Terzo fatto.", "Quarto."]})}

    def handler(request: httpx2.Request) -> httpx2.Response:
        calls.append(request)
        return httpx2.Response(200, json={
            "id": "msg_1", "type": "message", "role": "assistant", "model": "claude-opus-5-5",
            "content": [{"type": "text", "text": state["text"]}],
            "stop_reason": state["stop_reason"], "stop_sequence": None,
            "usage": {"input_tokens": 1200, "output_tokens": 60},
        })

    client = anthropic.DefaultAsyncHttpxClient(transport=httpx2.MockTransport(handler))
    monkeypatch.setattr(providers, "anthropic_http_client", client)
    return calls, state


def test_summary_with_claude(admin, app, claude):
    calls, state = claude
    [long_id, short_id] = feed(app, admin, "https://lungo.example/feed", [
        entry("Articolo lungo", content=f"<p>{LONG}</p>", words=600, hours_ago=1),
        entry("Breve", excerpt="Due righe.", words=20, hours_ago=1),
    ], title="Lungo")
    art = admin.get(f"/api/articles/{long_id}").json()["article"]
    assert art["summary"] is None and art["summary_available"] is False  # AI spenta

    admin.put("/api/admin/ai", json={"provider": "anthropic", "api_key": "sk-test"})
    assert admin.get(f"/api/articles/{long_id}").json()["article"]["summary_available"] is True
    assert admin.get(f"/api/articles/{short_id}").json()["article"]["summary_available"] is False

    r = admin.post(f"/api/articles/{long_id}/summary")
    assert r.status_code == 200, r.text
    assert r.json()["points"] == ["Primo fatto.", "Secondo fatto.", "Terzo fatto."]
    req = calls[0]
    body = json.loads(req.content)
    assert str(req.url).startswith("https://api.anthropic.com/v1/messages")
    assert "sk-test" in (req.headers.get("x-api-key", "") + req.headers.get("authorization", ""))
    # Ripiego lato server sui modelli che lo permettono, effort basso, output strutturato.
    assert "server-side-fallback-2026-07-01" in req.headers["anthropic-beta"] and body["fallbacks"] == "default"
    assert body["model"] == "claude-opus-5-5"
    assert body["output_config"]["effort"] == "low" and body["output_config"]["format"]["type"] == "json_schema"
    assert "galassia" in body["messages"][0]["content"]

    # Dalla seconda volta arriva dal database, anche per gli altri utenti.
    assert admin.post(f"/api/articles/{long_id}/summary").json()["points"][0] == "Primo fatto."
    assert len(calls) == 1
    assert admin.get(f"/api/articles/{long_id}").json()["article"]["summary"][2] == "Terzo fatto."
    assert admin.post(f"/api/articles/{short_id}/summary").status_code == 422

    # Modello senza ripiego, e rifiuto del modello.
    admin.put("/api/admin/ai", json={"provider": "anthropic", "model": "claude-haiku-5-5"})
    state["stop_reason"] = "refusal"
    [other] = feed(app, admin, "https://altro.example/feed", [entry("Altro lungo", content=f"<p>{LONG}</p>", words=600)], title="Altro")
    r = admin.post(f"/api/articles/{other}/summary")
    assert r.status_code == 503 and "rifiutato" in r.json()["detail"]
    assert "anthropic-beta" not in calls[-1].headers and json.loads(calls[-1].content)["model"] == "claude-haiku-5-5"

    # Riassunti spenti dall'utente.
    admin.patch("/api/me", json={"prefs": {"summaries": False}})
    assert admin.post(f"/api/articles/{other}/summary").status_code == 422
