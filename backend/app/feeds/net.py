"""Download dal web: client HTTP condiviso, limiti e messaggi d'errore chiari.

Ogni richiesta del server verso i siti passa da qui, così timeout, user agent,
dimensione massima e blocco della rete locale valgono ovunque.
"""

from __future__ import annotations

import asyncio
import ipaddress
import socket
from dataclasses import dataclass, field
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit, urlunsplit

import httpx

from ..config import Settings

TIMEOUT_SECONDS = 20
MAX_FEED_BYTES = 10 * 1024 * 1024
MAX_PAGE_BYTES = 5 * 1024 * 1024

FEED_ACCEPT = "application/rss+xml, application/atom+xml, application/xml;q=0.9, text/xml;q=0.9, */*;q=0.5"
PAGE_ACCEPT = "text/html, application/xhtml+xml, application/xml;q=0.9, */*;q=0.5"


class FetchError(Exception):
    """Errore di download con un messaggio da mostrare all'utente."""

    def __init__(self, message: str, status: int | None = None, retry_after: int | None = None):
        super().__init__(message)
        self.message = message
        self.status = status
        self.retry_after = retry_after


@dataclass
class Fetched:
    url: str  # indirizzo finale, dopo eventuali redirect
    status: int
    content: bytes
    headers: dict[str, str] = field(default_factory=dict)
    permanent_redirect: str | None = None

    @property
    def content_type(self) -> str:
        return self.headers.get("content-type", "").split(";")[0].strip().lower()

    def text(self) -> str:
        charset = None
        for part in self.headers.get("content-type", "").split(";")[1:]:
            key, _, value = part.strip().partition("=")
            if key.lower() == "charset":
                charset = value.strip("\"' ")
        try:
            return self.content.decode(charset or "utf-8")
        except (LookupError, UnicodeDecodeError):
            return self.content.decode("utf-8", errors="replace")


def normalize_input_url(raw: str) -> str:
    """Rende utilizzabile quello che l'utente incolla: spazi, schema mancante, maiuscole."""
    value = (raw or "").strip()
    if not value:
        raise FetchError("Scrivi l'indirizzo di un sito, di un feed o di un canale YouTube.")
    if value.startswith("@"):
        value = "https://www.youtube.com/" + value
    if value.startswith("feed:"):
        value = value[5:].lstrip("/")
        if not value.startswith("http"):
            value = "https://" + value
    if "://" not in value:
        value = "https://" + value
    try:
        parts = urlsplit(value)
        parts.port  # solleva ValueError se la porta non è un numero
    except ValueError:
        raise FetchError("Questo indirizzo non è valido.")
    if parts.scheme.lower() not in ("http", "https") or not parts.hostname:
        raise FetchError("L'indirizzo deve iniziare con http:// o https://.")
    netloc = parts.netloc.lower() if "@" not in parts.netloc else parts.netloc
    return urlunsplit((parts.scheme.lower(), netloc, parts.path or "/", parts.query, ""))


def _is_private(ip: str) -> bool:
    addr = ipaddress.ip_address(ip)
    if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped:
        addr = addr.ipv4_mapped
    return not addr.is_global


async def check_destination(url: str, settings: Settings) -> None:
    """Con BLOCK_PRIVATE_NETWORKS=true rifiuta gli indirizzi della rete locale."""
    if not settings.block_private_networks:
        return
    host = urlsplit(url).hostname or ""
    try:
        ipaddress.ip_address(host)
        addresses = [host]
    except ValueError:
        try:
            infos = await asyncio.get_running_loop().getaddrinfo(host, None, type=socket.SOCK_STREAM)
        except socket.gaierror:
            raise FetchError("Impossibile raggiungere il sito: l'indirizzo non esiste.")
        addresses = [info[4][0] for info in infos]
    if any(_is_private(a) for a in addresses):
        raise FetchError("Su questo server le fonti nella rete locale sono disattivate (BLOCK_PRIVATE_NETWORKS).")


def make_client(settings: Settings) -> httpx.AsyncClient:
    async def guard(request: httpx.Request) -> None:
        # Vale anche per ogni redirect, non solo per il primo indirizzo.
        await check_destination(str(request.url), settings)

    return httpx.AsyncClient(
        timeout=httpx.Timeout(TIMEOUT_SECONDS),
        follow_redirects=True,
        max_redirects=5,
        headers={"User-Agent": settings.user_agent, "Accept-Language": "it, en;q=0.8"},
        event_hooks={"request": [guard]},
    )


def _retry_after(value: str | None) -> int | None:
    if not value:
        return None
    value = value.strip()
    if value.isdigit():
        return int(value)
    try:
        when = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    import time

    return max(0, int(when.timestamp() - time.time()))


def status_message(status: int) -> str:
    if status == 401:
        return "Il sito chiede una password per questo feed (errore 401)."
    if status == 403:
        return "Il sito blocca l'accesso ai programmi automatici (errore 403)."
    if status == 404:
        return "A questo indirizzo non c'è più niente (errore 404)."
    if status == 410:
        return "Il sito ha eliminato questo feed (errore 410)."
    if status == 429:
        return "Il sito chiede di rallentare (errore 429): riprovo più tardi."
    if 500 <= status < 600:
        return f"Il sito ha un problema temporaneo (errore {status})."
    return f"Il sito ha risposto con un errore ({status})."


async def fetch(
    client: httpx.AsyncClient,
    url: str,
    *,
    accept: str = FEED_ACCEPT,
    max_bytes: int = MAX_FEED_BYTES,
    etag: str | None = None,
    last_modified: str | None = None,
    cookies: dict[str, str] | None = None,
) -> Fetched:
    """Scarica un indirizzo. Restituisce anche le risposte 304; gli altri errori diventano FetchError."""
    headers = {"Accept": accept}
    if etag:
        headers["If-None-Match"] = etag
    if last_modified:
        headers["If-Modified-Since"] = last_modified
    try:
        async with client.stream("GET", url, headers=headers, cookies=cookies) as resp:
            permanent = None
            for hop in resp.history:
                if hop.status_code in (301, 308):
                    permanent = str(resp.url)
                else:
                    permanent = None
                    break
            if resp.status_code == 304:
                return Fetched(str(resp.url), 304, b"", dict(resp.headers), permanent)
            if resp.status_code >= 400:
                raise FetchError(
                    status_message(resp.status_code),
                    status=resp.status_code,
                    retry_after=_retry_after(resp.headers.get("retry-after")),
                )
            declared = resp.headers.get("content-length", "")
            if declared.isdigit() and int(declared) > max_bytes:
                raise FetchError("La risposta del sito è troppo grande.", status=resp.status_code)
            chunks, size = [], 0
            async for chunk in resp.aiter_bytes():
                size += len(chunk)
                if size > max_bytes:
                    raise FetchError("La risposta del sito è troppo grande.", status=resp.status_code)
                chunks.append(chunk)
            return Fetched(str(resp.url), resp.status_code, b"".join(chunks), dict(resp.headers), permanent)
    except FetchError:
        raise
    except httpx.TimeoutException:
        raise FetchError(f"Il sito non ha risposto entro {TIMEOUT_SECONDS} secondi.")
    except httpx.TooManyRedirects:
        raise FetchError("Il sito rimanda da un indirizzo all'altro senza fermarsi (troppi redirect).")
    except httpx.ProxyError:
        raise FetchError("Il proxy di rete del server ha rifiutato la connessione al sito.")
    except httpx.ConnectError as exc:
        text = str(exc).lower()
        if "certificate" in text or "ssl" in text:
            raise FetchError("Il certificato HTTPS del sito non è valido.")
        if "name or service" in text or "nodename" in text or "getaddrinfo" in text or "resolution" in text:
            raise FetchError("Impossibile raggiungere il sito: l'indirizzo non esiste.")
        raise FetchError("Impossibile collegarsi al sito: è spento o rifiuta la connessione.")
    except httpx.HTTPError:
        raise FetchError("Il collegamento con il sito si è interrotto.")
