import httpx
import respx

from app.api.images import sign
from app.feeds.scheduler import cleanup
from conftest import invite_user
from helpers import HOUR, entry, feed, source_id


def _list(client, **params):
    r = client.get("/api/articles", params=params)
    assert r.status_code == 200, r.text
    return r.json()


def _titles(client, **params):
    return [a["title"] for a in _list(client, **params)["items"]]


def _setup(app, client):
    tech = client.post("/api/folders", json={"name": "Tech"}).json()["folder"]["id"]
    spazio = client.post("/api/folders", json={"name": "Spazio"}).json()["folder"]["id"]
    feed(app, client, "https://orbita.example/feed", [
        entry("Perché le missioni lunari puntano al polo sud", excerpt="Ghiaccio nei crateri", hours_ago=1, categories=["Luna"]),
        entry("Come atterra un razzo", hours_ago=3, video_id="vid1"),
        entry("Oroscopo spaziale della settimana", hours_ago=4),
    ], title="Orbita", folder_id=spazio)
    feed(app, client, "https://bitebyte.example/feed", [
        entry("Docker in un mini PC da 150 euro", excerpt="Lo stack completo", hours_ago=2),
        entry("Le PWA su iPhone", excerpt="Notifiche e offline", hours_ago=5,
              content="<p>Le web app si installano dalla schermata Home.</p>"),
    ], title="Bit & Byte", folder_id=tech)
    return tech, spazio


def test_list_is_chronological_with_details(admin, app):
    _setup(app, admin)
    data = _list(admin)
    assert [a["title"] for a in data["items"]] == [
        "Perché le missioni lunari puntano al polo sud", "Docker in un mini PC da 150 euro",
        "Come atterra un razzo", "Oroscopo spaziale della settimana", "Le PWA su iPhone",
    ]
    first = data["items"][0]
    assert first["source"]["title"] == "Orbita" and first["source"]["kind"] == "rss"
    assert first["reading_minutes"] == 2 and first["read"] is False and first["saved"] is False
    assert first["match"] is None and data["next_cursor"] is None


def test_pagination(admin, app):
    feed(app, admin, "https://molti.example/feed", [entry(f"Articolo {i}", hours_ago=i) for i in range(1, 8)])
    page1 = _list(admin, limit=3)
    page2 = _list(admin, limit=3, cursor=page1["next_cursor"])
    page3 = _list(admin, limit=3, cursor=page2["next_cursor"])
    titles = [a["title"] for p in (page1, page2, page3) for a in p["items"]]
    assert titles == [f"Articolo {i}" for i in range(1, 8)]
    assert page3["next_cursor"] is None


def test_interests_and_per_te(admin, app):
    _setup(app, admin)
    admin.post("/api/interests/keywords", json={"keyword": "Docker", "level": "alta"})
    r = admin.post("/api/interests/keywords", json={"keyword": "Luna"})
    assert r.status_code == 201
    assert [k["keyword"] for k in r.json()["keywords"]] == ["Docker", "Luna"]
    items = _list(admin, view="perte")["items"]
    assert [(a["title"][:6], a["match"]) for a in items] == [
        ("Perché", {"keyword": "Luna", "level": "media"}),
        ("Docker", {"keyword": "Docker", "level": "alta"}),
    ]
    luna = r.json()["keywords"][1]["id"]
    admin.patch(f"/api/interests/keywords/{luna}", json={"level": "spento"})
    assert _titles(admin, view="perte") == ["Docker in un mini PC da 150 euro"]
    assert admin.post("/api/interests/keywords", json={"keyword": "docker"}).status_code == 409
    assert admin.post("/api/interests/keywords", json={"keyword": "!!"}).status_code == 422
    admin.delete(f"/api/interests/keywords/{luna}")
    assert len(admin.get("/api/interests").json()["keywords"]) == 1


def test_new_articles_are_matched_on_arrival(admin, app):
    admin.post("/api/interests/keywords", json={"keyword": "Razzi", "level": "alta"})
    feed(app, admin, "https://orbita.example/feed", [entry("Un nuovo razzo europeo")])
    assert _list(admin, view="perte")["items"][0]["match"]["keyword"] == "Razzi"


def test_new_subscriber_gets_matches_for_existing_articles(admin, app):
    feed(app, admin, "https://orbita.example/feed", [entry("Un nuovo razzo europeo")])
    bruno = invite_user(admin, app, "bruno")
    bruno.post("/api/interests/keywords", json={"keyword": "razzi"})
    feed(app, bruno, "https://orbita.example/feed", [])
    assert _titles(bruno, view="perte") == ["Un nuovo razzo europeo"]
    assert _titles(admin, view="perte") == []


def test_muted_words(admin, app):
    _setup(app, admin)
    r = admin.post("/api/interests/muted", json={"word": "Oroscopo"})
    assert r.json()["muted"][0]["word"] == "oroscopo"
    data = _list(admin)
    assert "Oroscopo spaziale della settimana" not in [a["title"] for a in data["items"]]
    assert data["hidden"] == 1
    shown = _list(admin, show_muted="true")["items"]
    assert any(a["muted"] for a in shown)
    preview = admin.get("/api/interests/preview").json()
    assert preview == {"matching": 0, "total": 4, "hidden": 1, "hours": 24}
    admin.delete(f"/api/interests/muted/{r.json()['muted'][0]['id']}")
    assert _list(admin)["hidden"] == 0


def test_filters(admin, app):
    tech, spazio = _setup(app, admin)
    assert _titles(admin, view="video") == ["Come atterra un razzo"]
    assert _titles(admin, folder=str(tech)) == ["Docker in un mini PC da 150 euro", "Le PWA su iPhone"]
    feed(app, admin, "https://libera.example/feed", [entry("Senza cartella", hours_ago=9)], title="Libera")
    assert _titles(admin, folder="none") == ["Senza cartella"]
    assert _titles(admin, source=source_id(admin, "Bit & Byte")) == ["Docker in un mini PC da 150 euro", "Le PWA su iPhone"]
    assert admin.get("/api/articles", params={"view": "boh"}).status_code == 422


def test_search(admin, app):
    _setup(app, admin)
    assert _titles(admin, q="perche") == ["Perché le missioni lunari puntano al polo sud"]
    assert _titles(admin, q="lunar") == ["Perché le missioni lunari puntano al polo sud"]
    assert _titles(admin, q="schermata home") == ["Le PWA su iPhone"]  # nel testo, non nel titolo
    assert _titles(admin, q="bit & byte") == ["Docker in un mini PC da 150 euro", "Le PWA su iPhone"]  # nome della fonte
    assert _titles(admin, q="nessuna corrispondenza") == []
    # Caratteri strani non rompono la ricerca.
    for odd in ('"', "a AND OR", "NEAR(", "*", "-x"):
        assert admin.get("/api/articles", params={"q": odd}).status_code == 200


def test_counts(admin, app):
    tech, spazio = _setup(app, admin)
    admin.post("/api/interests/keywords", json={"keyword": "Docker"})
    admin.post("/api/interests/muted", json={"word": "oroscopo"})
    first = _list(admin)["items"][0]["id"]
    admin.put(f"/api/articles/{first}/read")
    admin.put(f"/api/articles/{first}/saved")
    c = admin.get("/api/articles/counts").json()
    assert c["tutti"] == 4 and c["perte"] == 1 and c["nonletti"] == 3 and c["video"] == 1 and c["salvati"] == 1
    assert c["folders"] == {str(tech): 2, str(spazio): 2} and c["hidden"] == 1
    assert admin.get("/api/articles/counts", params={"q": "docker"}).json()["tutti"] == 1


def test_read_unread_and_unread_counts(admin, app):
    _setup(app, admin)
    first = _list(admin)["items"][0]
    r = admin.put(f"/api/articles/{first['id']}/read")
    assert r.json() == {"id": first["id"], "read": True, "saved": False}
    assert first["title"] not in _titles(admin, view="nonletti")
    unread = {s["title"]: s["unread"] for s in admin.get("/api/sources").json()["sources"]}
    assert unread == {"Orbita": 2, "Bit & Byte": 2}
    admin.delete(f"/api/articles/{first['id']}/read")
    assert first["title"] in _titles(admin, view="nonletti")


def test_saved(admin, app):
    _setup(app, admin)
    items = _list(admin)["items"]
    admin.put(f"/api/articles/{items[3]['id']}/saved")
    admin.put(f"/api/articles/{items[0]['id']}/saved")
    # Ordinati per data di salvataggio, il più recente prima.
    saved = _list(admin, view="salvati")["items"]
    assert {a["id"] for a in saved} == {items[0]["id"], items[3]["id"]}
    assert all(a["saved"] for a in saved)
    admin.delete(f"/api/articles/{items[3]['id']}/saved")
    assert [a["id"] for a in _list(admin, view="salvati")["items"]] == [items[0]["id"]]


def test_saved_articles_survive_unsubscribe_and_cleanup(admin, app):
    ids = feed(app, admin, "https://orbita.example/feed", [entry("Da tenere"), entry("Da buttare")], title="Orbita")
    admin.put(f"/api/articles/{ids[0]}/saved")
    admin.delete(f"/api/sources/{source_id(admin, 'Orbita')}")
    assert _titles(admin, view="salvati") == ["Da tenere"]
    assert _titles(admin) == ["Da tenere"]
    detail = admin.get(f"/api/articles/{ids[0]}").json()["article"]
    assert detail["source"]["id"] is None and detail["source"]["title"] == "Orbita"
    assert admin.get(f"/api/articles/{ids[1]}").status_code == 404

    with app.state.ctx.db.session() as conn, conn:
        conn.execute("UPDATE articles SET published_at = 1, fetched_at = 1")
    cleanup(app.state.ctx)
    assert _titles(admin, view="salvati") == ["Da tenere"]
    admin.delete(f"/api/articles/{ids[0]}/saved")
    cleanup(app.state.ctx)
    with app.state.ctx.db.session() as conn:
        assert conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM feeds").fetchone()[0] == 0


def test_retention_keeps_recent_articles(admin, app):
    feed(app, admin, "https://orbita.example/feed", [entry("Recente"), entry("Vecchio", hours_ago=24 * 120)])
    with app.state.ctx.db.session() as conn, conn:
        conn.execute("UPDATE articles SET fetched_at = 1 WHERE title = 'Vecchio'")
    cleanup(app.state.ctx)
    assert _titles(admin) == ["Recente"]


def test_duplicates_are_merged(admin, app):
    feed(app, admin, "https://orbita.example/feed", [
        entry("Artemis III: la NASA rinvia lo sbarco sulla Luna al 2027", url="https://orbita.example/artemis?utm_source=rss", hours_ago=2),
    ], title="Orbita")
    feed(app, admin, "https://altra.example/feed", [
        entry("La NASA rinvia lo sbarco sulla Luna di Artemis III al 2027", url="https://altra.example/nasa", hours_ago=1),
        entry("Stesso link, titolo diverso", url="https://www.orbita.example/artemis", hours_ago=1.5),
    ], title="Altra")
    items = _list(admin)["items"]
    assert len(items) == 1
    assert items[0]["source"]["title"] == "Orbita"  # si mostra chi l'ha pubblicata per primo
    assert sorted(o["title"] for o in items[0]["also_on"]) == ["Altra", "Altra"]

    # Letta una volta, letta ovunque.
    admin.put(f"/api/articles/{items[0]['id']}/read")
    admin.patch("/api/me", json={"prefs": {"dedupe": False}})
    all_items = _list(admin)["items"]
    assert len(all_items) == 3 and all(a["read"] for a in all_items)


def test_article_detail(admin, app):
    ids = feed(app, admin, "https://orbita.example/feed", [
        entry("Con immagine", content='<p>Testo</p><img src="https://cdn.example/a.jpg?x=1&amp;y=2" alt="">',
              image="https://cdn.example/cover.jpg", categories=["Spazio"]),
    ], title="Orbita")
    a = admin.get(f"/api/articles/{ids[0]}").json()["article"]
    assert a["image"].startswith("/api/img?u=https%3A%2F%2Fcdn.example%2Fcover.jpg&s=")
    assert 'src="/api/img?u=https%3A%2F%2Fcdn.example%2Fa.jpg%3Fx%3D1%26y%3D2&amp;s=' in a["content_html"]
    assert a["categories"] == ["Spazio"]
    # Il feed dà poco testo: il server proverà a estrarre l'articolo completo.
    assert a["full_text"] is False and a["full_text_status"] == "pending"

    with app.state.ctx.db.session() as conn, conn:
        conn.execute("UPDATE articles SET full_status = 'ok', full_html = '<p>Testo completo</p>'")
    a = admin.get(f"/api/articles/{ids[0]}").json()["article"]
    assert a["content_html"] == "<p>Testo completo</p>" and a["full_text"] is True


def test_articles_are_private(admin, app):
    ids = feed(app, admin, "https://orbita.example/feed", [entry("Solo di Anna")])
    bruno = invite_user(admin, app, "bruno")
    assert _titles(bruno) == []
    assert bruno.get(f"/api/articles/{ids[0]}").status_code == 404
    assert bruno.put(f"/api/articles/{ids[0]}/saved").status_code == 404
    assert bruno.post("/api/articles/sync", json={"actions": [{"id": ids[0], "saved": True}]}).json()["skipped"] == 1
    assert _titles(bruno, view="salvati") == []


def test_read_state_is_per_user(admin, app):
    ids = feed(app, admin, "https://orbita.example/feed", [entry("Condiviso")])
    bruno = invite_user(admin, app, "bruno")
    feed(app, bruno, "https://orbita.example/feed", [])
    admin.put(f"/api/articles/{ids[0]}/read")
    assert _list(bruno)["items"][0]["read"] is False


def test_mark_all_read(admin, app):
    tech, _ = _setup(app, admin)
    r = admin.post("/api/articles/mark-read", json={"folder": str(tech)})
    assert r.json()["marked"] == 2
    assert _titles(admin, view="nonletti") == ["Perché le missioni lunari puntano al polo sud", "Come atterra un razzo", "Oroscopo spaziale della settimana"]
    assert _list(admin)["server_time"].endswith("Z")
    import datetime as dt

    # L'elenco era stato caricato 10 secondi fa; poi è arrivato un articolo nuovo.
    before = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(seconds=10)).isoformat()
    feed(app, admin, "https://orbita.example/feed", [entry("Arrivato dopo", hours_ago=0)])
    admin.post("/api/articles/mark-read", json={"before": before})
    assert _titles(admin, view="nonletti") == ["Arrivato dopo"]


def test_sync_offline_actions(admin, app):
    ids = feed(app, admin, "https://orbita.example/feed", [entry("Uno"), entry("Due", hours_ago=2)])
    r = admin.post("/api/articles/sync", json={"actions": [
        {"id": ids[0], "read": True}, {"id": ids[1], "saved": True}, {"id": 99999, "read": True},
    ]})
    assert r.json() == {"applied": 2, "skipped": 1}
    items = {a["title"]: a for a in _list(admin)["items"]}
    assert items["Uno"]["read"] and items["Due"]["saved"]


def test_image_proxy(admin, app):
    secret = app.state.ctx.secret
    url = "https://cdn.example/foto.jpg"
    with respx.mock(assert_all_called=False) as web:
        web.get(url).mock(return_value=httpx.Response(200, content=b"\xff\xd8\xff", headers={"content-type": "image/jpeg"}))
        web.get("https://cdn.example/logo.svg").mock(
            return_value=httpx.Response(200, text="<svg/>", headers={"content-type": "image/svg+xml"})
        )
        r = admin.get("/api/img", params={"u": url, "s": sign(secret, url)})
        assert r.status_code == 200 and r.content == b"\xff\xd8\xff"
        assert r.headers["content-type"] == "image/jpeg" and "max-age" in r.headers["cache-control"]
        assert admin.get("/api/img", params={"u": url, "s": "falsa"}).status_code == 403
        svg = "https://cdn.example/logo.svg"
        assert admin.get("/api/img", params={"u": svg, "s": sign(secret, svg)}).status_code == 415
    from conftest import new_client

    assert new_client(app).get("/api/img", params={"u": url, "s": sign(secret, url)}).status_code == 401
