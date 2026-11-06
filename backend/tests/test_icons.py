"""Icone delle fonti al posto delle iniziali (issue #11)."""

import time

import httpx
import pytest
import respx

from app.api.images import sign
from app.feeds.icons import icon_candidates, youtube_avatar
from app.feeds.net import image_type
from conftest import invite_user
from helpers import entry, feed, source_id

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 40
ICO = b"\x00\x00\x01\x00\x01\x00\x10\x10" + b"\x00" * 40
PAGE = """<!doctype html><html><head><title>Orbita</title>
<link rel="icon" href="/favicon-32.png" sizes="32x32">
<link rel="icon" type="image/svg+xml" href="/icon.svg">
<link rel="apple-touch-icon" href="/apple.png">
<meta property="og:image" content="https://cdn.orbita.example/banner.jpg">
</head><body>Orbita</body></html>"""


@pytest.fixture
def web():
    with respx.mock(assert_all_called=False) as mock:
        yield mock


def _image(web, url, body=PNG, kind="image/png", status=200):
    return web.get(url).mock(return_value=httpx.Response(status, content=body, headers={"content-type": kind}))


def _page(web, url, html=PAGE):
    return web.get(url).mock(return_value=httpx.Response(200, text=html, headers={"content-type": "text/html"}))


def _follow(app, client, url="https://orbita.example/feed", site="https://orbita.example/", kind="rss", title="Orbita"):
    feed(app, client, url, [entry("Una notizia")], title=title)
    with app.state.ctx.db.session() as conn, conn:
        conn.execute(
            "UPDATE feeds SET site_url = ?, kind = ?, last_success_at = ? WHERE url = ?",
            (site, kind, int(time.time()), url),
        )
    return source_id(client, title)


def _run(client, app):
    return client.portal.call(app.state.ctx.icons.run_due)


def _source(client, sid):
    return next(s for s in client.get("/api/sources").json()["sources"] if s["id"] == sid)


# ---------- Regole ----------


def test_icon_candidates_prefer_sharp_raster_icons():
    found = icon_candidates(PAGE, "https://orbita.example/")
    assert found == [
        "https://orbita.example/apple.png",  # 180 px: nitida anche sui telefoni
        "https://orbita.example/favicon-32.png",
        "https://orbita.example/favicon.ico",
        "https://cdn.orbita.example/banner.jpg",  # og:image per ultima: di solito è un banner
    ]
    # Senza icone dichiarate restano /favicon.ico e og:image; le SVG si scartano sempre.
    assert icon_candidates("<link rel=icon href=/i.svg>", "https://a.example/x") == ["https://a.example/favicon.ico"]
    big = '<link rel="icon" href="/192.png" sizes="192x192"><link rel="icon" href="/96.png" sizes="96x96"><link rel="icon" href="/16.png" sizes="16x16">'
    assert icon_candidates(big, "https://a.example/")[:3] == ["https://a.example/96.png", "https://a.example/192.png", "https://a.example/16.png"]


def test_youtube_avatar():
    html = '<meta property="og:image" content="https://yt3.googleusercontent.com/abc=s900-c-k-c0x00ffffff-no-rj">'
    assert youtube_avatar(html) == "https://yt3.googleusercontent.com/abc=s176-c-k-c0x00ffffff-no-rj"
    assert youtube_avatar("<p>niente</p>") == ""


def test_image_type_trusts_content_not_headers():
    assert image_type(PNG, "text/plain") == "image/png"
    assert image_type(ICO, "application/octet-stream") == "image/x-icon"
    assert image_type(b"<html>non sono un'immagine</html>", "image/png") is None
    assert image_type(b"<svg/>", "image/svg+xml") is None


# ---------- Ricerca automatica ----------


def test_icon_is_found_and_shown_everywhere(admin, app, web):
    sid = _follow(app, admin)
    _page(web, "https://orbita.example/")
    _image(web, "https://orbita.example/apple.png")
    assert _run(admin, app) == 1
    s = _source(admin, sid)
    assert s["icon"].startswith("/api/img?u=https%3A%2F%2Forbita.example%2Fapple.png&s=") and s["icon"].endswith("&k=icon")
    assert s["icon_mode"] == "auto" and s["icon_auto"] == s["icon"] and s["icon_checked_at"]
    # Anche negli articoli (card, lettore, Edizione).
    item = admin.get("/api/articles").json()["items"][0]
    assert item["source"]["icon"] == s["icon"]
    assert admin.get(f"/api/articles/{item['id']}").json()["article"]["source"]["icon"] == s["icon"]
    # Il prossimo controllo è tra 7 giorni.
    assert _run(admin, app) == 0


def test_falls_back_to_the_next_icon(admin, app, web):
    sid = _follow(app, admin)
    _page(web, "https://orbita.example/")
    _image(web, "https://orbita.example/apple.png", status=404)
    _image(web, "https://orbita.example/favicon-32.png", body=b"<html>errore</html>", kind="image/png")
    _image(web, "https://orbita.example/favicon.ico", body=ICO, kind="text/plain")
    _run(admin, app)
    assert "favicon.ico" in _source(admin, sid)["icon"]


def test_no_icon_keeps_the_initials(admin, app, web):
    sid = _follow(app, admin)
    web.get("https://orbita.example/").mock(return_value=httpx.Response(500))
    web.get("https://orbita.example/favicon.ico").mock(return_value=httpx.Response(404))
    _run(admin, app)
    s = _source(admin, sid)
    assert s["icon"] is None and s["icon_checked_at"]


def test_youtube_channel_avatar(admin, app, web):
    channel = "https://www.youtube.com/channel/UCabcdefghijklmnopqrstuv"
    sid = _follow(app, admin, url="https://www.youtube.com/feeds/videos.xml?channel_id=UCabcdefghijklmnopqrstuv",
                  site=channel, kind="youtube", title="Canale")
    avatar = "https://yt3.googleusercontent.com/abc=s176-c-k"
    _page(web, channel, '<meta property="og:image" content="https://yt3.googleusercontent.com/abc=s900-c-k">')
    _image(web, avatar, body=b"\xff\xd8\xff\xe0" + b"\x00" * 20, kind="image/jpeg")
    _run(admin, app)
    assert "yt3.googleusercontent.com%2Fabc%3Ds176" in _source(admin, sid)["icon"]


def test_icon_proxy_serves_ico_files(admin, app, web):
    url = "https://orbita.example/favicon.ico"
    _image(web, url, body=ICO, kind="text/plain")
    r = admin.get("/api/img", params={"u": url, "s": sign(app.state.ctx.secret, url), "k": "icon"})
    assert r.status_code == 200 and r.headers["content-type"] == "image/x-icon"


# ---------- Scelte dell'utente ----------


def test_refresh_icon_now(admin, app, web):
    sid = _follow(app, admin)
    web.get("https://orbita.example/").mock(return_value=httpx.Response(500))
    web.get("https://orbita.example/favicon.ico").mock(return_value=httpx.Response(404))
    r = admin.post(f"/api/sources/{sid}/icon/refresh")
    assert r.status_code == 200 and r.json()["found"] is False
    _page(web, "https://orbita.example/")
    _image(web, "https://orbita.example/apple.png")
    r = admin.post(f"/api/sources/{sid}/icon/refresh")
    assert r.json()["found"] is True and "apple.png" in r.json()["source"]["icon"]


def test_custom_image_and_initials_are_per_user_and_survive_refresh(admin, app, web):
    sid = _follow(app, admin)
    bruno = invite_user(admin, app, "bruno")
    bid = _follow(app, bruno)
    _page(web, "https://orbita.example/")
    _image(web, "https://orbita.example/apple.png")
    _image(web, "https://cdn.example/logo.png")
    _run(admin, app)

    r = admin.put(f"/api/sources/{sid}/icon", json={"mode": "custom", "url": "cdn.example/logo.png"})
    assert r.status_code == 200, r.text
    s = r.json()["source"]
    assert "cdn.example%2Flogo.png" in s["icon"] and s["icon_mode"] == "custom"
    assert s["icon_custom"] == "https://cdn.example/logo.png" and "apple.png" in s["icon_auto"]
    # La nuova ricerca automatica non tocca la scelta dell'utente.
    admin.post(f"/api/sources/{sid}/icon/refresh")
    assert "logo.png" in _source(admin, sid)["icon"]
    # Gli altri che seguono lo stesso feed vedono ancora l'icona automatica.
    assert "apple.png" in _source(bruno, bid)["icon"]

    r = admin.put(f"/api/sources/{sid}/icon", json={"mode": "none"})
    assert r.json()["source"]["icon"] is None
    assert admin.get("/api/articles").json()["items"][0]["source"]["icon"] is None
    r = admin.put(f"/api/sources/{sid}/icon", json={"mode": "auto"})
    assert "apple.png" in r.json()["source"]["icon"]


def test_custom_image_must_be_an_image(admin, app, web):
    sid = _follow(app, admin)
    _page(web, "https://cdn.example/pagina", "<p>non è un'immagine</p>")
    r = admin.put(f"/api/sources/{sid}/icon", json={"mode": "custom", "url": "https://cdn.example/pagina"})
    assert r.status_code == 422 and "immagine" in r.json()["detail"]
    assert admin.put(f"/api/sources/{sid}/icon", json={"mode": "custom", "url": ""}).status_code == 422
    assert admin.put(f"/api/sources/{sid}/icon", json={"mode": "altro"}).status_code == 422
    bruno = invite_user(admin, app, "bruno")
    assert bruno.put(f"/api/sources/{sid}/icon", json={"mode": "none"}).status_code == 404
