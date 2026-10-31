import httpx
import pytest
import respx

from conftest import invite_user
from samples import (
    ARTICLE_PAGE, ATOM_FULL, PLAIN_PAGE, RSS_EXCERPT, SITE_PAGE, YOUTUBE_CHANNEL_PAGE, YOUTUBE_FEED,
)

RSS = {"content-type": "application/rss+xml"}
ATOM = {"content-type": "application/atom+xml"}
HTML = {"content-type": "text/html; charset=utf-8"}
YT_FEED = "https://www.youtube.com/feeds/videos.xml?channel_id=UCabcdefghijklmnopqrstuv"

@pytest.fixture
def web():
    with respx.mock(assert_all_called=False) as mock:
        yield mock

def _feed(web, url=" https://orbita.example/feed.xml", body=RSS_EXCERPT, headers=RSS):
    return web.get(url.strip()).mock(return_value=httpx.Response(200, text=body, headers=headers))

def _add(client, url="https://orbita.example/feed.xml", **extra):
    return client.post("/api/sources", json={"url": url, **extra})

def _db(app):
    return app.state.ctx.db.session()

# ---------- Ricerca dei feed ----------

def test_discover_from_site_page(admin, web):
    web.get("https://orbita.example/").mock(return_value=httpx.Response(200, text=SITE_PAGE, headers=HTML))
    _feed(web)
    web.get("https://orbita.example/approfondimenti.atom").mock(
        return_value=httpx.Response(200, text=ATOM_FULL, headers=ATOM)
    )
    comments = web.get("https://orbita.example/comments/feed").mock(return_value=httpx.Response(200, text=RSS_EXCERPT, headers=RSS))
    r = admin.post("/api/sources/discover", json={"url": "orbita.example"})
    assert r.status_code == 200, r.text
    found = r.json()["candidates"]
    assert [c["url"] for c in found] == ["https://orbita.example/feed.xml", "https://orbita.example/approfondimenti.atom"]
    assert found[0]["title"] == "Orbita" and found[0]["full_text"] is False and found[0]["items"] == 2
    assert found[1]["full_text"] is True
    assert all(not c["already_followed"] for c in found)
    assert comments.called  # controllato, ma scartato perché sono commenti

def test_discover_feed_url_directly(admin, web):
    _feed(web)
    found = admin.post("/api/sources/discover", json={"url": "https://orbita.example/feed.xml"}).json()["candidates"]
    assert len(found) == 1 and found[0]["kind"] == "rss"

def test_discover_tries_common_paths(admin, web):
    web.get("https://senzalink.example/").mock(return_value=httpx.Response(200, text=PLAIN_PAGE, headers=HTML))
    web.get("https://senzalink.example/rss.xml").mock(return_value=httpx.Response(200, text=RSS_EXCERPT, headers=RSS))
    web.get(url__regex=r"https://senzalink\.example/.+").mock(return_value=httpx.Response(404))
    found = admin.post("/api/sources/discover", json={"url": "https://senzalink.example"}).json()["candidates"]
    assert [c["url"] for c in found] == ["https://senzalink.example/rss.xml"]

def test_discover_nothing_found(admin, web):
    web.get("https://vuoto.example/").mock(return_value=httpx.Response(200, text=PLAIN_PAGE, headers=HTML))
    web.get(url__regex=r"https://vuoto\.example/.+").mock(return_value=httpx.Response(404))
    r = admin.post("/api/sources/discover", json={"url": "vuoto.example"})
    assert r.status_code == 422
    assert "non ho trovato nessun feed" in r.json()["detail"]

def test_discover_site_errors_are_clear(admin, web):
    web.get("https://bloccato.example/").mock(return_value=httpx.Response(403))
    r = admin.post("/api/sources/discover", json={"url": "bloccato.example"})
    assert r.status_code == 502
    assert "programmi automatici" in r.json()["detail"]
    web.get("https://lento.example/").mock(side_effect=httpx.ConnectTimeout("timeout"))
    r = admin.post("/api/sources/discover", json={"url": "lento.example"})
    assert "non ha risposto" in r.json()["detail"]

def test_discover_youtube_handle(admin, web):
    page = web.get("https://www.youtube.com/@cronache").mock(
        return_value=httpx.Response(200, text=YOUTUBE_CHANNEL_PAGE, headers=HTML)
    )
    web.get(YT_FEED).mock(return_value=httpx.Response(200, text=YOUTUBE_FEED, headers=ATOM))
    found = admin.post("/api/sources/discover", json={"url": "@cronache"}).json()["candidates"]
    assert found[0]["url"] == YT_FEED and found[0]["kind"] == "youtube"
    assert found[0]["title"] == "Cronache Spaziali"
    assert "SOCS=CAI" in page.calls[0].request.headers.get("cookie", "")

def test_discover_youtube_channel_link_needs_no_page(admin, web):
    web.get(YT_FEED).mock(return_value=httpx.Response(200, text=YOUTUBE_FEED, headers=ATOM))
    r = admin.post("/api/sources/discover", json={"url": "https://www.youtube.com/channel/UCabcdefghijklmnopqrstuv/videos"})
    assert r.json()["candidates"][0]["url"] == YT_FEED

def test_discover_marks_already_followed(admin, web):
    _feed(web)
    _add(admin)
    found = admin.post("/api/sources/discover", json={"url": "https://orbita.example/feed.xml"}).json()["candidates"]
    assert found[0]["already_followed"] is True

# ---------- Aggiunta e fetch ----------

def test_add_source_fetches_articles(admin, app, web):
    _feed(web)
    r = _add(admin)
    assert r.status_code == 201, r.text
    src = r.json()["source"]
    assert src["title"] == "Orbita" and src["status"] == "ok" and src["articles"] == 2
    assert src["site_url"] == "https://orbita.example/"
    with _db(app) as conn:
        a = conn.execute("SELECT * FROM articles ORDER BY published_at DESC").fetchone()
        assert a["canonical_url"] == "orbita.example/luna-polo-sud"
        assert a["full_status"] in ("pending", "skipped")
        hits = conn.execute("SELECT rowid FROM articles_fts WHERE articles_fts MATCH 'perche'").fetchall()
        assert [h[0] for h in hits] == [a["id"]]

def test_add_not_a_feed_is_rejected(admin, app, web):
    web.get("https://orbita.example/").mock(return_value=httpx.Response(200, text=PLAIN_PAGE, headers=HTML))
    r = _add(admin, "https://orbita.example/")
    assert r.status_code == 422
    assert "feed RSS o Atom" in r.json()["detail"]
    with _db(app) as conn:
        assert conn.execute("SELECT COUNT(*) FROM feeds").fetchone()[0] == 0

def test_add_twice(admin, web):
    _feed(web)
    _add(admin)
    r = _add(admin, "HTTPS://ORBITA.example/feed.xml")
    assert r.status_code == 409

def test_shared_feed_is_downloaded_once(admin, app, web):
    route = _feed(web)
    bruno = invite_user(admin, app, "bruno")
    _add(admin)
    r = _add(bruno, interval_min=15)
    assert r.status_code == 201
    assert route.call_count == 1
    with _db(app) as conn:
        assert conn.execute("SELECT COUNT(*) FROM feeds").fetchone()[0] == 1
        assert conn.execute("SELECT interval_min FROM feeds").fetchone()[0] == 15

def test_conditional_get_and_not_modified(admin, app, web):
    route = web.get("https://orbita.example/feed.xml").mock(
        side_effect=[
            httpx.Response(200, text=RSS_EXCERPT, headers={**RSS, "ETag": '"v1"', "Last-Modified": "Sat, 31 Oct 2026 08:00:00 GMT"}),
            httpx.Response(304),
        ]
    )
    src = _add(admin).json()["source"]
    r = admin.post(f"/api/sources/{src['id']}/refresh")
    assert r.status_code == 200 and r.json()["new_articles"] == 0
    second = route.calls[1].request.headers
    assert second["if-none-match"] == '"v1"'
    assert second["if-modified-since"] == "Sat, 31 Oct 2026 08:00:00 GMT"
    assert r.json()["source"]["status"] == "ok"

def test_user_agent(admin, web):
    route = _feed(web)
    _add(admin)
    assert route.calls[0].request.headers["user-agent"].startswith("GalacticFeed/")
    assert "https://feed.example.org" in route.calls[0].request.headers["user-agent"]

def test_errors_and_backoff(admin, app, web):
    web.get("https://orbita.example/feed.xml").mock(
        side_effect=[httpx.Response(200, text=RSS_EXCERPT, headers=RSS), httpx.Response(404), httpx.Response(404), httpx.Response(404)]
    )
    src = _add(admin).json()["source"]
    for expected in ("warn", "warn", "err"):
        s = admin.post(f"/api/sources/{src['id']}/refresh").json()["source"]
        assert s["status"] == expected
    assert "404" in s["error"] and s["error_since"]
    with _db(app) as conn:
        f = conn.execute("SELECT * FROM feeds").fetchone()
        # Dopo 3 errori il prossimo controllo è tra 30 × 2³ = 240 minuti.
        assert f["next_fetch_at"] - f["last_fetch_at"] == 240 * 60

def test_retry_after_is_respected(admin, app, web):
    web.get("https://orbita.example/feed.xml").mock(
        side_effect=[httpx.Response(200, text=RSS_EXCERPT, headers=RSS), httpx.Response(429, headers={"Retry-After": "7200"})]
    )
    src = _add(admin).json()["source"]
    s = admin.post(f"/api/sources/{src['id']}/refresh").json()["source"]
    assert "rallentare" in s["error"]
    with _db(app) as conn:
        f = conn.execute("SELECT * FROM feeds").fetchone()
        assert f["next_fetch_at"] - f["last_fetch_at"] == 7200

def test_permanent_redirect_updates_feed_url(admin, app, web):
    web.get("https://vecchio.example/rss").mock(
        return_value=httpx.Response(301, headers={"Location": "https://nuovo.example/rss"})
    )
    web.get("https://nuovo.example/rss").mock(return_value=httpx.Response(200, text=RSS_EXCERPT, headers=RSS))
    src = _add(admin, "https://vecchio.example/rss").json()["source"]
    assert src["url"] == "https://nuovo.example/rss"

def test_full_text_extraction(admin, app, web):
    _feed(web)
    web.get(url__regex=r"https://orbita\.example/luna-polo-sud.*").mock(
        return_value=httpx.Response(200, text=ARTICLE_PAGE, headers=HTML)
    )
    web.get("https://orbita.example/galassie").mock(return_value=httpx.Response(403))
    _add(admin)
    with _db(app) as conn, conn:
        conn.execute("UPDATE articles SET full_status = 'pending', published_at = strftime('%s','now')")

    ctx = app.state.ctx
    ok = admin.portal.call(ctx.extractor.extract_pending)
    assert ok == 1
    with _db(app) as conn:
        rows = {r["url"]: r for r in conn.execute("SELECT * FROM articles")}
        luna = rows["https://orbita.example/luna-polo-sud?utm_source=rss"]
        assert luna["full_status"] == "ok"
        assert "Secondo paragrafo" in luna["full_html"] and "Menu Home" not in luna["full_html"]
        assert "Commento di un lettore" not in luna["full_html"]
        assert rows["https://orbita.example/galassie"]["full_status"] == "failed"
        body = conn.execute("SELECT body FROM articles_fts WHERE rowid = ?", (luna["id"],)).fetchone()[0]
        assert "Secondo paragrafo" in body

def test_hook_receives_new_articles(admin, app, web):
    seen = []

    async def hook(feed_id, ids):
        seen.append((feed_id, ids))

    app.state.ctx.hooks.new_articles.append(hook)
    _feed(web)
    _add(admin)
    assert len(seen) == 1 and len(seen[0][1]) == 2

def test_scheduler_fetches_due_feeds(admin, app, web):
    route = _feed(web)
    _add(admin)
    with _db(app) as conn, conn:
        conn.execute("UPDATE feeds SET next_fetch_at = 0")
    admin.portal.call(app.state.ctx.scheduler.run_once)
    assert route.call_count == 2

def test_private_networks_can_be_blocked(admin, app, web):
    app.state.ctx.settings.block_private_networks = True
    r = _add(admin, "http://192.168.1.20/feed.xml")
    assert r.status_code == 422
    assert "rete locale" in r.json()["detail"]
    r = admin.post("/api/sources/discover", json={"url": "http://127.0.0.1:8080/"})
    assert r.status_code == 502 and "rete locale" in r.json()["detail"]

# ---------- Modifica, rimozione, cartelle ----------

def test_list_patch_and_delete(admin, app, web):
    _feed(web)
    src = _add(admin).json()["source"]
    folder = admin.post("/api/folders", json={"name": "Spazio"}).json()["folder"]
    assert folder["color"] == "indaco"

    r = admin.patch(f"/api/sources/{src['id']}", json={"title": "La mia Orbita", "folder_id": folder["id"], "interval_min": 60})
    s = r.json()["source"]
    assert s["title"] == "La mia Orbita" and s["folder_id"] == folder["id"] and s["interval_min"] == 60
    assert admin.patch(f"/api/sources/{src['id']}", json={"interval_min": 7}).status_code == 422

    # Togliere la cartella senza toccare il resto.
    s = admin.patch(f"/api/sources/{src['id']}", json={"folder_id": None}).json()["source"]
    assert s["folder_id"] is None and s["title"] == "La mia Orbita"

    listed = admin.get("/api/sources").json()
    assert [x["title"] for x in listed["sources"]] == ["La mia Orbita"]
    assert 15 in listed["intervals"]

    assert admin.delete(f"/api/sources/{src['id']}").status_code == 200
    with _db(app) as conn:
        assert conn.execute("SELECT COUNT(*) FROM feeds").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM articles_fts").fetchone()[0] == 0

def test_delete_keeps_feed_followed_by_others(admin, app, web):
    _feed(web)
    bruno = invite_user(admin, app, "bruno")
    mine = _add(admin).json()["source"]
    _add(bruno)
    admin.delete(f"/api/sources/{mine['id']}")
    assert len(bruno.get("/api/sources").json()["sources"]) == 1
    assert admin.get("/api/sources").json()["sources"] == []

def test_sources_are_private(admin, app, web):
    _feed(web)
    src = _add(admin).json()["source"]
    bruno = invite_user(admin, app, "bruno")
    assert bruno.get("/api/sources").json()["sources"] == []
    assert bruno.patch(f"/api/sources/{src['id']}", json={"title": "x"}).status_code == 404
    assert bruno.delete(f"/api/sources/{src['id']}").status_code == 404

def test_folders_crud(admin, app, web):
    a = admin.post("/api/folders", json={"name": "Spazio"}).json()["folder"]
    b = admin.post("/api/folders", json={"name": "Tech"}).json()["folder"]
    assert b["color"] == "blu"
    assert admin.post("/api/folders", json={"name": "spazio"}).status_code == 409
    assert admin.post("/api/folders", json={"name": "  "}).status_code == 422
    r = admin.patch(f"/api/folders/{a['id']}", json={"name": "Astronomia", "color": "viola"})
    assert r.json()["folder"]["name"] == "Astronomia"
    assert admin.patch(f"/api/folders/{a['id']}", json={"name": "Tech"}).status_code == 409

    _feed(web)
    src = _add(admin, folder_id=a["id"]).json()["source"]
    assert admin.delete(f"/api/folders/{a['id']}").status_code == 200
    assert admin.get("/api/sources").json()["sources"][0]["folder_id"] is None
    assert [f["name"] for f in admin.get("/api/folders").json()["folders"]] == ["Tech"]

    bruno = invite_user(admin, app, "bruno")
    assert bruno.get("/api/folders").json()["folders"] == []
    assert bruno.delete(f"/api/folders/{b['id']}").status_code == 404
    assert bruno.patch(f"/api/sources/{src['id']}", json={"folder_id": b["id"]}).status_code == 404

def test_refresh_all(admin, app, web):
    _feed(web)
    web.get("https://bitebyte.example/atom.xml").mock(return_value=httpx.Response(200, text=ATOM_FULL, headers=ATOM))
    _add(admin)
    _add(admin, "https://bitebyte.example/atom.xml")
    r = admin.post("/api/sources/refresh").json()
    # Appena aggiunte: controllate meno di un minuto fa, quindi saltate.
    assert r["sources"] == 2 and r["skipped"] == 2 and r["checked"] == 0
    with _db(app) as conn, conn:
        conn.execute("UPDATE feeds SET last_fetch_at = 0")
    r = admin.post("/api/sources/refresh").json()
    assert r["checked"] == 2 and r["errors"] == 0 and r["new_articles"] == 0
