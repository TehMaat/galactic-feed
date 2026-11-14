"""Preferenza «Nascondi gli articoli senza testo completo» (#32)."""

from __future__ import annotations

from app.db import now
from app.push.notifier import unread_count
from app.reading import edition

from conftest import invite_user
from helpers import entry, feed


def _source(client, title):
    return next(s for s in client.get("/api/sources").json()["sources"] if s["title"] == title)

LONG = "<p>" + "Testo completo dell'articolo. " * 60 + "</p>"


def _status(app, article_id: int, status: str) -> None:
    with app.state.ctx.db.session() as conn, conn:
        conn.execute("UPDATE articles SET full_status = ? WHERE id = ?", (status, article_id))


def _titles(client, **params):
    r = client.get("/api/articles", params=params)
    assert r.status_code == 200, r.text
    return [a["title"] for a in r.json()["items"]]


def _setup(app, client):
    """Un articolo per ogni stato del testo completo, più un video."""
    ids = feed(app, client, "https://misto.example/feed", [
        entry("Completo nel feed", content=LONG, hours_ago=1),
        entry("Estratto dal sito", hours_ago=2),
        entry("In arrivo", hours_ago=3),
        entry("Solo estratto", hours_ago=4),
        entry("Vecchio solo estratto", hours_ago=5),
        entry("Video", video_id="vid1", hours_ago=6),
    ], title="Misto")
    for article_id, status in zip(ids[1:5], ("ok", "pending", "failed", "skipped")):
        _status(app, article_id, status)
    return ids


ALL = ["Completo nel feed", "Estratto dal sito", "In arrivo", "Solo estratto", "Vecchio solo estratto", "Video"]
FULL = ["Completo nel feed", "Estratto dal sito", "In arrivo", "Video"]


def test_preference_defaults_and_validation(admin):
    assert admin.get("/api/me").json()["user"]["prefs"]["hide_partial"] is False
    me = admin.patch("/api/me", json={"prefs": {"hide_partial": True}}).json()
    assert me["user"]["prefs"]["hide_partial"] is True
    assert admin.patch("/api/me", json={"prefs": {"hide_partial": "forse"}}).status_code == 422
    # Si può scegliere anche tra i predefiniti per i nuovi utenti.
    assert "hide_partial" in admin.get("/api/admin/defaults").json()["prefs"]


def test_flow_hides_partial_articles(admin, app):
    _setup(app, admin)
    data = admin.get("/api/articles").json()
    assert [a["title"] for a in data["items"]] == ALL and data["hidden_partial"] == 0

    admin.patch("/api/me", json={"prefs": {"hide_partial": True}})
    data = admin.get("/api/articles").json()
    # In arrivo (pending) resta visibile; i video non sono toccati.
    assert [a["title"] for a in data["items"]] == FULL
    assert data["hidden_partial"] == 2
    assert _titles(admin, view="nonletti") == FULL
    counts = admin.get("/api/articles/counts").json()
    assert counts["tutti"] == 4 and counts["nonletti"] == 4

    # «Mostra»: per una volta si vedono tutti.
    data = admin.get("/api/articles", params={"show_partial": True}).json()
    assert [a["title"] for a in data["items"]] == ALL and data["hidden_partial"] == 0
    assert admin.get("/api/articles/counts", params={"show_partial": True}).json()["tutti"] == 6

    # Nella fonte, il conteggio dei non letti segue la preferenza.
    assert _source(admin, "Misto")["unread"] == 4


def test_saved_partial_articles_stay_visible(admin, app):
    ids = _setup(app, admin)
    admin.put(f"/api/articles/{ids[3]}/saved")
    admin.patch("/api/me", json={"prefs": {"hide_partial": True}})
    assert _titles(admin, view="salvati") == ["Solo estratto"]
    assert "Solo estratto" in _titles(admin)
    assert "Vecchio solo estratto" not in _titles(admin)


def test_duplicate_with_full_text_is_shown_instead(admin, app):
    [partial] = feed(app, admin, "https://chiuso.example/feed", [
        entry("Artemis III: la NASA rinvia lo sbarco sulla Luna al 2027", hours_ago=2),
    ], title="Chiuso")
    feed(app, admin, "https://aperto.example/feed", [
        entry("La NASA rinvia lo sbarco sulla Luna di Artemis III al 2027", content=LONG, hours_ago=1),
    ], title="Aperto")
    _status(app, partial, "failed")
    [item] = admin.get("/api/articles").json()["items"]
    assert item["source"]["title"] == "Chiuso"  # di solito si mostra chi l'ha pubblicata per primo

    admin.patch("/api/me", json={"prefs": {"hide_partial": True}})
    data = admin.get("/api/articles").json()
    [item] = data["items"]
    assert item["source"]["title"] == "Aperto"
    # La notizia c'è ancora: non conta come nascosta.
    assert data["hidden_partial"] == 0


def test_preference_is_per_user(admin, app):
    _setup(app, admin)
    other = invite_user(admin, app, "bruno")
    feed(app, other, "https://misto.example/feed", [], title="Misto")
    admin.patch("/api/me", json={"prefs": {"hide_partial": True}})
    assert _titles(admin) == FULL
    assert _titles(other) == ALL


def test_edition_skips_partial_articles(admin, app):
    _setup(app, admin)
    admin.post("/api/interests/keywords", json={"keyword": "estratto"})
    admin.patch("/api/me", json={"prefs": {"edition": True, "hide_partial": True}})
    assert len(edition.run_due(app.state.ctx)) == 1
    ed = admin.get("/api/editions/latest").json()["edition"]
    titles = [a["title"] for a in [ed["hero"], *[i for s in ed["sections"] for i in s["items"]]] if a]
    assert "Estratto dal sito" in titles
    assert "Solo estratto" not in titles and "Vecchio solo estratto" not in titles


def test_notifications_wait_for_full_text(admin, app):
    ids = _setup(app, admin)
    admin.post("/api/interests/keywords", json={"keyword": "estratto"})
    admin.post("/api/interests/keywords", json={"keyword": "arrivo"})
    notifier = app.state.ctx.notifier
    uid = admin.get("/api/me").json()["user"]["id"]

    def pending(hide_partial):
        with app.state.ctx.db.session() as conn:
            rows = notifier.pending_news(conn, uid, ["none"], 0, now(), hide_partial)
        return sorted(r["title"] for r in rows)

    assert pending(False) == ["Estratto dal sito", "In arrivo", "Solo estratto", "Vecchio solo estratto"]
    # Con la preferenza: solo i testi completi; quello in arrivo aspetta l'estrazione.
    assert pending(True) == ["Estratto dal sito"]
    _status(app, ids[2], "ok")
    assert pending(True) == ["Estratto dal sito", "In arrivo"]
    # Il badge conta come il Flusso.
    with app.state.ctx.db.session() as conn:
        assert unread_count(conn, uid, True, False) == 6
        assert unread_count(conn, uid, True, True) == 4


def test_source_mostly_partial(admin, app):
    ids = feed(app, admin, "https://paywall.example/feed", [entry(f"Articolo {i}", hours_ago=i) for i in range(1, 6)], title="Paywall")
    for article_id in ids[:2]:
        _status(app, article_id, "failed")
    # Due tentativi falliti: troppo pochi per dirlo.
    assert _source(admin, "Paywall")["mostly_partial"] is False
    _status(app, ids[2], "failed")
    _status(app, ids[3], "ok")
    assert _source(admin, "Paywall")["mostly_partial"] is True
    _status(app, ids[4], "ok")
    _status(app, ids[0], "ok")
    assert _source(admin, "Paywall")["mostly_partial"] is False
