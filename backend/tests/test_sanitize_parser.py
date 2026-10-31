import pytest

from app.feeds.net import FetchError, normalize_input_url
from app.feeds.parser import NotAFeed, parse_feed
from app.feeds.sanitize import canonical_url, clean_html, excerpt
from samples import ATOM_FULL, PLAIN_PAGE, RSS_EXCERPT, YOUTUBE_FEED


def test_clean_html_keeps_reading_and_drops_the_rest():
    html = (
        '<h2>Sottotitolo</h2><p onclick="x()">Testo <a href="/pagina">link</a></p>'
        '<script>alert(1)</script><iframe src="https://ads"></iframe>'
        '<img src="/a.jpg" alt="foto"><img src="https://t.example/p.gif" width="1" height="1">'
        '<p><a href="https://s.example/post#comments">5 commenti</a></p>'
        '<div class="share-buttons">Condividi</div>'
    )
    out = clean_html(html, "https://s.example/post")
    assert "<h3>Sottotitolo</h3>" in out
    assert 'href="https://s.example/pagina"' in out and "noopener" in out
    assert 'src="https://s.example/a.jpg"' in out
    for bad in ("script", "iframe", "onclick", "p.gif", "commenti", "Condividi"):
        assert bad not in out


def test_clean_html_drops_repeated_title():
    out = clean_html("<h1>Il titolo!</h1><p>Corpo</p>", drop_heading="Il titolo")
    assert "titolo" not in out and "Corpo" in out


def test_canonical_url():
    assert canonical_url("https://www.Example.com/a/b/?utm_source=x&id=3#top") == "example.com/a/b?id=3"
    assert canonical_url("http://example.com/a/b?id=3") == "example.com/a/b?id=3"


def test_excerpt_cuts_on_words():
    text = "parola " * 100
    out = excerpt(text, 50)
    assert out.endswith("…") and len(out) <= 51


def test_parse_rss_with_excerpt():
    feed = parse_feed(RSS_EXCERPT.encode(), "https://orbita.example/feed.xml")
    assert feed.title == "Orbita" and feed.kind == "rss"
    first = feed.entries[0]
    assert first.title.startswith("Perché")
    assert first.categories == ["Luna"]
    assert first.image_url == "https://orbita.example/img/luna.jpg"
    assert "commenti" not in first.content_html
    assert first.needs_full_text
    assert first.published_at is not None


def test_parse_atom_with_full_text():
    feed = parse_feed(ATOM_FULL.encode(), "https://bitebyte.example/atom.xml")
    e = feed.entries[0]
    assert e.url == "https://bitebyte.example/pwa-iphone"
    assert e.author == "Redazione"
    assert not e.needs_full_text
    assert "<script" not in e.content_html and "pixel.gif" not in e.content_html
    assert "<h3>" not in e.content_html  # il titolo ripetuto è stato tolto
    assert e.image_url == "https://bitebyte.example/foto.jpg"


def test_parse_youtube():
    feed = parse_feed(YOUTUBE_FEED.encode(), "https://www.youtube.com/feeds/videos.xml?channel_id=UCabcdefghijklmnopqrstuv")
    e = feed.entries[0]
    assert feed.kind == "youtube"
    assert e.video_id == "vid12345678"
    assert e.image_url.endswith("hqdefault.jpg")
    assert "Motori" in e.excerpt
    assert not e.needs_full_text


def test_html_is_not_a_feed():
    with pytest.raises(NotAFeed):
        parse_feed(PLAIN_PAGE.encode(), "https://x.example/", "text/html")


def test_normalize_input_url():
    assert normalize_input_url("Orbita.example") == "https://orbita.example/"
    assert normalize_input_url("@cronache") == "https://www.youtube.com/@cronache"
    assert normalize_input_url("feed://orbita.example/rss") == "https://orbita.example/rss"
    with pytest.raises(FetchError):
        normalize_input_url("ftp://x.example/feed")
    with pytest.raises(FetchError):
        normalize_input_url("  ")
    with pytest.raises(FetchError):
        normalize_input_url("javascript:alert(1)")
