"""Tag delle fonti: proposti in automatico, modificabili, usati come filtri (issue #17)."""

import httpx
import respx

from app.reading import tagging
from conftest import invite_user
from helpers import entry, feed, source_id

TECH = [
    entry("Il nuovo smartphone di Google", categories=["Gadget"]),
    entry("Apple presenta il chip M9", categories=["Gadget"]),
    entry("Android 20: le novità del software", categories=["Gadget", "Senza categoria"]),
    entry("Un'app per tutto", categories=["Gadget"]),
    entry("La startup che fa computer quantistici"),
]


def _source(client, sid):
    return next(s for s in client.get("/api/sources").json()["sources"] if s["id"] == sid)


def _names(source):
    return [t["name"] for t in source["tags"]]


def _suggest(app, sid):
    with app.state.ctx.db.session() as conn:
        return tagging.apply_suggestions(conn, sid)


def test_suggestions_from_ready_groups_and_feed_categories(admin, app):
    feed(app, admin, "https://tech.example/feed", TECH, title="Bit e Byte")
    sid = source_id(admin, "Bit e Byte")
    assert _suggest(app, sid) == ["Tecnologia", "Gadget"]
    source = _source(admin, sid)
    assert _names(source) == ["Tecnologia", "Gadget"]
    assert {t["origin"] for t in source["tags"]} == {"auto"}
    # «Senza categoria» non dice niente: non diventa un tag.
    assert "Senza categoria" not in [t["name"] for t in admin.get("/api/tags").json()["tags"]]


def test_new_sources_get_tags_when_added(admin, app):
    rss = (
        '<?xml version="1.0"?><rss version="2.0"><channel><title>Gol</title><link>https://gol.example/</link>'
        + "".join(f"<item><title>Serie A: gol e calciomercato {i}</title><link>https://gol.example/{i}</link><guid>{i}</guid></item>" for i in range(4))
        + "</channel></rss>"
    )
    with respx.mock(assert_all_called=False) as web:
        web.get("https://gol.example/feed").mock(return_value=httpx.Response(200, text=rss, headers={"content-type": "application/rss+xml"}))
        r = admin.post("/api/sources", json={"url": "https://gol.example/feed"})
    assert r.status_code == 201, r.text
    assert _names(r.json()["source"]) == ["Calcio"]


def test_user_choices_are_never_undone(admin, app):
    feed(app, admin, "https://tech.example/feed", TECH, title="Bit e Byte")
    sid = source_id(admin, "Bit e Byte")
    _suggest(app, sid)
    # Tolgo «Gadget» e aggiungo «Lavoro»: la proposta automatica non rimette «Gadget».
    r = admin.put(f"/api/sources/{sid}/tags", json={"tags": ["Tecnologia", "Lavoro"]})
    assert _names(r.json()["source"]) == ["Tecnologia", "Lavoro"]
    assert {t["name"]: t["origin"] for t in r.json()["source"]["tags"]} == {"Tecnologia": "user", "Lavoro": "user"}
    r = admin.post(f"/api/sources/{sid}/tags/suggest")
    assert r.json()["added"] == [] and _names(r.json()["source"]) == ["Tecnologia", "Lavoro"]
    assert admin.put(f"/api/sources/{sid}/tags", json={"tags": [" "]}).status_code == 422


def test_tags_filter_the_stream_with_counts(admin, app):
    feed(app, admin, "https://tech.example/feed", TECH[:2], title="Bit e Byte")
    feed(app, admin, "https://spazio.example/feed", [entry("Una galassia lontana")], title="Orbita")
    sid = source_id(admin, "Bit e Byte")
    admin.put(f"/api/sources/{sid}/tags", json={"tags": ["Tecnologia"]})
    tag = admin.get("/api/tags").json()["tags"][0]
    assert tag["name"] == "Tecnologia" and tag["sources"] == 1 and tag["in_feed"] is True
    titles = {a["title"] for a in admin.get("/api/articles", params={"tag": tag["id"]}).json()["items"]}
    assert titles == {"Il nuovo smartphone di Google", "Apple presenta il chip M9"}
    assert admin.get("/api/articles/counts").json()["tags"] == {str(tag["id"]): 2}
    r = admin.post("/api/articles/mark-read", json={"tag": tag["id"]})
    assert r.json()["marked"] == 2
    assert [a["title"] for a in admin.get("/api/articles", params={"view": "nonletti"}).json()["items"]] == ["Una galassia lontana"]


def test_manage_tags(admin, app):
    feed(app, admin, "https://tech.example/feed", TECH[:1], title="Bit e Byte")
    feed(app, admin, "https://altro.example/feed", [entry("Altro")], title="Altro")
    a, b = source_id(admin, "Bit e Byte"), source_id(admin, "Altro")
    admin.put(f"/api/sources/{a}/tags", json={"tags": ["Tech"]})
    admin.put(f"/api/sources/{b}/tags", json={"tags": ["Tecnologia"]})
    tags = {t["name"]: t for t in admin.get("/api/tags").json()["tags"]}
    # Rinomina, colore, chip nel Flusso.
    r = admin.patch(f"/api/tags/{tags['Tech']['id']}", json={"name": "Hi-tech", "color": "verde", "in_feed": False})
    hitech = next(t for t in r.json()["tags"] if t["name"] == "Hi-tech")
    assert hitech["color"] == "verde" and hitech["in_feed"] is False
    assert admin.patch(f"/api/tags/{hitech['id']}", json={"name": "tecnologia"}).status_code == 409
    assert admin.patch(f"/api/tags/{hitech['id']}", json={"color": "oro"}).status_code == 422
    # Unisci: le fonti di «Hi-tech» passano a «Tecnologia».
    r = admin.post(f"/api/tags/{hitech['id']}/merge", json={"into": tags["Tecnologia"]["id"]})
    assert [(t["name"], t["sources"]) for t in r.json()["tags"]] == [("Tecnologia", 2)]
    assert _names(_source(admin, a)) == ["Tecnologia"]
    # Ordine ed eliminazione.
    admin.post("/api/tags", json={"name": "Spazio", "color": "viola"})
    ids = [t["id"] for t in admin.get("/api/tags").json()["tags"]]
    r = admin.put("/api/tags/order", json={"ids": list(reversed(ids))})
    assert [t["name"] for t in r.json()["tags"]] == ["Spazio", "Tecnologia"]
    assert admin.post("/api/tags", json={"name": "spazio"}).status_code == 409
    r = admin.delete(f"/api/tags/{tags['Tecnologia']['id']}")
    assert [t["name"] for t in r.json()["tags"]] == ["Spazio"] and _names(_source(admin, a)) == []


def test_tags_are_personal(admin, app):
    feed(app, admin, "https://tech.example/feed", TECH[:1], title="Bit e Byte")
    bruno = invite_user(admin, app, "bruno")
    feed(app, bruno, "https://tech.example/feed", [], title="Bit e Byte")
    admin.put(f"/api/sources/{source_id(admin, 'Bit e Byte')}/tags", json={"tags": ["Tecnologia"]})
    assert bruno.get("/api/tags").json()["tags"] == []
    assert _names(_source(bruno, source_id(bruno, "Bit e Byte"))) == []
    tag = admin.get("/api/tags").json()["tags"][0]
    assert bruno.patch(f"/api/tags/{tag['id']}", json={"name": "x"}).status_code == 404
    assert bruno.get("/api/articles", params={"tag": tag["id"]}).json()["items"] == []


def test_scheduler_suggests_only_if_wanted(admin, app):
    feed(app, admin, "https://tech.example/feed", TECH, title="Bit e Byte")
    bruno = invite_user(admin, app, "bruno")
    feed(app, bruno, "https://tech.example/feed", [], title="Bit e Byte")
    bruno.patch("/api/me", json={"prefs": {"auto_tags": False}})
    with app.state.ctx.db.session() as conn, conn:
        conn.execute("UPDATE feeds SET last_success_at = 1")
    with app.state.ctx.db.session() as conn:
        assert tagging.run_due(conn) == 2
        assert tagging.run_due(conn) == 0
    assert _names(_source(admin, source_id(admin, "Bit e Byte"))) == ["Tecnologia", "Gadget"]
    assert _names(_source(bruno, source_id(bruno, "Bit e Byte"))) == []
