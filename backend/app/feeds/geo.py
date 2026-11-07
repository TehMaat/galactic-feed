"""Nazione e lingua di una fonte, proposte in automatico (issue #20).

- Lingua: quella dichiarata dal feed (<language>, xml:lang), altrimenti indovinata dalle
  parole più comuni dei titoli (italiano, inglese, francese, tedesco, spagnolo, portoghese).
- Nazione: dal dominio nazionale (.it, .co.uk, .de…); per i domini generici (.com, .org…)
  dalla regione della lingua (en-US → US), oppure dalla lingua se è legata a una nazione
  (it → IT). L'inglese da solo non dice la nazione: resta vuota.
"""

from __future__ import annotations

import re
from collections import Counter
from urllib.parse import urlsplit

from ..reading.text import normalize

# Domini nazionali che non coincidono con il codice ISO, più i secondi livelli comuni.
TLD_COUNTRY = {"uk": "GB", "eu": ""}
GENERIC_TLDS = {"com", "org", "net", "info", "io", "co", "eu", "app", "dev", "news", "blog", "tv", "me", "xyz", "online", "site", "media", "biz", "int", "edu", "gov", "mil"}
LANGUAGE_COUNTRY = {"it": "IT", "fr": "FR", "de": "DE", "es": "ES", "pt": "PT", "nl": "NL", "ja": "JP", "pl": "PL", "sv": "SE", "da": "DK", "fi": "FI", "el": "GR", "cs": "CZ", "hu": "HU", "ro": "RO"}

STOPWORDS = {
    "it": "il lo la gli le di del della dei che per con una un non sono anche come più nel alla questo".split(),
    "en": "the of and to in for on with is are this that from by at how why what new will".split(),
    "fr": "le la les des du de et pour avec une dans est sur pas qui plus aux par".split(),
    "de": "der die das und den mit von für ist ein eine nicht auf dem des im zu".split(),
    "es": "el la los las de del y para con una por que en es más se como".split(),
    "pt": "o a os as de do da e para com uma em que não no na por mais".split(),
}
_CODE = re.compile(r"^[a-z]{2,3}$")


def clean_language(value: str | None) -> str:
    """«it-IT» → «it»; quello che non è un codice di lingua diventa ""."""
    code = (value or "").strip().lower().replace("_", "-").split("-")[0]
    return code if _CODE.match(code) else ""


def language_region(value: str | None) -> str:
    """«en-US» → «US»."""
    parts = (value or "").strip().replace("_", "-").split("-")
    return parts[1].upper() if len(parts) > 1 and len(parts[1]) == 2 and parts[1].isalpha() else ""


def guess_language(titles: list[str]) -> str:
    """La lingua dei titoli, dalle parole più comuni. "" se non è chiaro."""
    words = Counter(w for t in titles for w in normalize(t).split())
    scores = {lang: sum(words[w] for w in sw) for lang, sw in STOPWORDS.items()}
    best = max(scores, key=scores.get)
    second = sorted(scores.values())[-2]
    return best if scores[best] >= 3 and scores[best] >= 1.5 * max(second, 1) else ""


def country_from_host(url: str) -> str:
    host = (urlsplit(url or "").hostname or "").lower().rstrip(".")
    if not host or host.replace(".", "").isdigit():
        return ""
    tld = host.rsplit(".", 1)[-1]
    if tld in GENERIC_TLDS or len(tld) != 2:
        return ""
    return TLD_COUNTRY.get(tld, tld.upper())


def guess_country(urls: list[str], declared_language: str | None, language: str) -> str:
    for url in urls:
        country = country_from_host(url)
        if country:
            return country
    region = language_region(declared_language)
    if region:
        return region
    return LANGUAGE_COUNTRY.get(language, "")


def detect(urls: list[str], declared_language: str | None, titles: list[str]) -> tuple[str, str]:
    """(lingua, nazione) proposte per una fonte."""
    language = clean_language(declared_language) or guess_language(titles)
    return language, guess_country(urls, declared_language, language)


def backfill(conn, limit: int = 50) -> int:
    """Lingua e nazione per i feed che non le hanno ancora (per esempio seguiti prima di questa versione)."""
    from ..db import now

    feeds = conn.execute(
        "SELECT id, url, site_url FROM feeds WHERE geo_checked_at IS NULL AND last_success_at IS NOT NULL LIMIT ?", (limit,)
    ).fetchall()
    with conn:
        for f in feeds:
            titles = [r["title"] for r in conn.execute(
                "SELECT title FROM articles WHERE feed_id = ? ORDER BY published_at DESC LIMIT 40", (f["id"],)
            )]
            language, country = detect([f["site_url"], f["url"]], None, titles)
            conn.execute(
                "UPDATE feeds SET language = ?, country = ?, geo_checked_at = ? WHERE id = ?",
                (language, country, now(), f["id"]),
            )
    return len(feeds)
