"""Pulizia dell'HTML degli articoli e utilità sul testo e sui link.

L'HTML che arriva da feed e siti può contenere script, pubblicità, pixel di
tracciamento e link per commentare. Qui teniamo solo quello che serve alla lettura.
"""

from __future__ import annotations

import re
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

import lxml.html
import nh3
from lxml import etree

ALLOWED_TAGS = {
    "a", "abbr", "b", "blockquote", "br", "caption", "cite", "code", "dd", "del", "dl", "dt", "em",
    "figcaption", "figure", "h3", "h4", "hr", "i", "img", "ins", "li", "mark", "ol", "p", "pre", "q",
    "s", "small", "strong", "sub", "sup", "table", "tbody", "td", "tfoot", "th", "thead", "tr", "u", "ul",
}
ALLOWED_ATTRIBUTES = {
    "a": {"href", "title"},
    "img": {"src", "alt", "title", "width", "height"},
    "abbr": {"title"},
    "td": {"colspan", "rowspan"},
    "th": {"colspan", "rowspan"},
}
# Titoli: nel lettore bastano due livelli, come nel mockup.
HEADING_MAP = {"h1": "h3", "h2": "h3", "h3": "h3", "h4": "h4", "h5": "h4", "h6": "h4"}
DROP_WITH_CONTENT = {"script", "style", "noscript", "iframe", "object", "embed", "form", "button", "svg", "template", "nav", "aside"}

COMMENT_HREF = re.compile(r"(#comments?\b|#respond\b|/comments?(/|$|\?|#)|comment-page-|replytocom=|/feed/?$)", re.I)
COMMENT_TEXT = re.compile(r"^\s*(\d+\s*)?(commenti?|comments?|commenta|lascia un commento|leave a (comment|reply)|reply|rispondi|discuss)\b", re.I)
JUNK_CLASS = re.compile(r"feedflare|share|social|related|newsletter|advert|sponsor|promo|subscribe", re.I)

TRACKING_PARAMS = re.compile(r"^(utm_\w+|fbclid|gclid|dclid|mc_cid|mc_eid|igshid|ref|ref_src|_hsenc|_hsmi|mkt_tok|spm|cmpid|wt_mc)$", re.I)


def _is_pixel(img) -> bool:
    w, h = img.get("width", ""), img.get("height", "")
    return (w.isdigit() and int(w) <= 2) or (h.isdigit() and int(h) <= 2)


def clean_html(html: str, base_url: str = "", drop_heading: str = "") -> str:
    """HTML sicuro e ordinato per il lettore. drop_heading toglie un titolo iniziale uguale a quello dell'articolo."""
    if not html or not html.strip():
        return ""
    try:
        root = lxml.html.fragment_fromstring(html, create_parent="div")
    except (etree.ParserError, ValueError):
        return nh3.clean(html, tags=set(ALLOWED_TAGS), attributes={}) if html else ""

    for el in list(root.iter()):
        if not isinstance(el.tag, str):
            continue
        tag = el.tag.lower()
        if tag in DROP_WITH_CONTENT or JUNK_CLASS.search(el.get("class", "") + " " + el.get("id", "")):
            if el.getparent() is not None:
                el.drop_tree()
            continue
        if tag in HEADING_MAP:
            el.tag = HEADING_MAP[tag]
        elif tag == "a":
            href = el.get("href", "")
            if COMMENT_HREF.search(href) or COMMENT_TEXT.match(el.text_content() or ""):
                el.drop_tree()
                continue
            if base_url and href:
                el.set("href", urljoin(base_url, href))
        elif tag == "img":
            src = el.get("src") or el.get("data-src") or el.get("data-lazy-src") or ""
            if not src or _is_pixel(el) or src.startswith("data:"):
                el.drop_tree()
                continue
            el.set("src", urljoin(base_url, src) if base_url else src)

    if drop_heading:
        first = next(root.iter("h3", "h4"), None)
        if first is not None and _norm(first.text_content()) == _norm(drop_heading):
            first.drop_tree()

    raw = lxml.html.tostring(root, encoding="unicode")
    cleaned = nh3.clean(
        raw,
        tags=set(ALLOWED_TAGS),
        attributes={k: set(v) for k, v in ALLOWED_ATTRIBUTES.items()},
        url_schemes={"http", "https", "mailto"},
        link_rel="noopener noreferrer nofollow",
        strip_comments=True,
    )
    # Paragrafi rimasti vuoti dopo la pulizia.
    cleaned = re.sub(r"<p>(\s|&nbsp;|<br>)*</p>", "", cleaned)
    return cleaned.strip()


def _norm(text: str) -> str:
    return " ".join(re.sub(r"[^\w\s]", " ", (text or "").lower()).split())


def html_to_text(html: str) -> str:
    if not html or not html.strip():
        return ""
    try:
        root = lxml.html.fragment_fromstring(html, create_parent="div")
    except (etree.ParserError, ValueError):
        return " ".join(re.sub(r"<[^>]+>", " ", html).split())
    for el in root.iter("br", "p", "li", "h1", "h2", "h3", "h4", "div", "blockquote"):
        el.tail = (el.tail or "") + " "
    return " ".join(root.text_content().split())


def excerpt(text: str, limit: int = 300) -> str:
    text = " ".join((text or "").split())
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0].rstrip(",;:.-–— ")
    return cut + "…"


def word_count(text: str) -> int:
    return len(re.findall(r"\w+", text or ""))


def first_image(html: str, base_url: str = "") -> str:
    if not html:
        return ""
    try:
        root = lxml.html.fragment_fromstring(html, create_parent="div")
    except (etree.ParserError, ValueError):
        return ""
    for img in root.iter("img"):
        src = img.get("src") or img.get("data-src") or ""
        if src and not src.startswith("data:") and not _is_pixel(img):
            return urljoin(base_url, src) if base_url else src
    return ""


def canonical_url(url: str) -> str:
    """Link ripulito per riconoscere la stessa notizia: niente schema, www, #, utm_ e simili."""
    if not url:
        return ""
    try:
        parts = urlsplit(url.strip())
    except ValueError:
        return url.strip().lower()
    host = (parts.hostname or "").lower().removeprefix("www.").removeprefix("m.")
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if not TRACKING_PARAMS.match(k)]
    path = parts.path.rstrip("/") or "/"
    return urlunsplit(("", host, path, urlencode(sorted(query)), "")).lstrip("/")


def normalize_feed_url(url: str) -> str:
    """Forma unica dell'indirizzo di un feed, per non scaricarlo due volte."""
    parts = urlsplit(url.strip())
    host = (parts.hostname or "").lower()
    netloc = host + (f":{parts.port}" if parts.port else "")
    if parts.username:
        netloc = parts.netloc
    return urlunsplit((parts.scheme.lower(), netloc, parts.path or "/", parts.query, ""))
