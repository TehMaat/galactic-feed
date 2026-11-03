"""Chiamate al modello: una sola funzione, `complete_json`, per tutti i fornitori.

- Anthropic (Claude): SDK ufficiale `anthropic`, con output strutturato (JSON Schema). Sui
  modelli che lo permettono si attiva il ripiego lato server: se il modello rifiuta una
  richiesta (per esempio un articolo su un attacco informatico scambiato per una richiesta
  pericolosa), il servizio la ripete da solo con un altro modello.
- Ollama e servizi compatibili con OpenAI: endpoint /chat/completions con httpx.

Gli errori diventano AIError con un messaggio in italiano, da mostrare all'amministratore.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

import anthropic
import httpx

from .config import AIConfig

TIMEOUT_LOCAL = 180.0  # un modello locale su hardware piccolo può essere lento
TIMEOUT_CLOUD = 90.0
ANTHROPIC_URL = "https://api.anthropic.com"

# Modelli Claude che accettano il ripiego lato server («fallbacks»).
FALLBACK_MODELS = ("claude-fable-5-1", "claude-opus-5-5", "claude-opus-5", "claude-sonnet-5-5")
FALLBACK_BETA = "server-side-fallback-2026-07-01"
# Modelli Claude che non accettano il parametro «effort».
NO_EFFORT_PREFIXES = ("claude-3", "claude-haiku-4", "claude-sonnet-4-5", "claude-opus-4-1", "claude-opus-4-0")


class AIError(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass
class Result:
    data: dict
    usage: Usage
    model: str


# Per i test: si può sostituire il client HTTP dei due fornitori.
anthropic_http_client = None
openai_transport = None


async def complete_json(cfg: AIConfig, system: str, prompt: str, schema: dict, max_tokens: int = 8000) -> Result:
    if not cfg.enabled:
        raise AIError("L'AI non è configurata.")
    if cfg.provider == "anthropic":
        return await _anthropic(cfg, system, prompt, schema, max_tokens)
    return await _openai(cfg, system, prompt, schema, max_tokens)


# ---------- Anthropic ----------


async def _anthropic(cfg: AIConfig, system: str, prompt: str, schema: dict, max_tokens: int) -> Result:
    client = anthropic.AsyncAnthropic(
        api_key=cfg.api_key,
        # Indirizzo esplicito: non deve dipendere da variabili d'ambiente del server.
        base_url=cfg.base_url or ANTHROPIC_URL,
        timeout=TIMEOUT_CLOUD,
        max_retries=2,
        http_client=anthropic_http_client,
    )
    output_config: dict = {"format": {"type": "json_schema", "schema": schema}}
    if not cfg.model.startswith(NO_EFFORT_PREFIXES):
        # Scegliere e riassumere notizie è un compito semplice: poco ragionamento, meno spesa.
        output_config["effort"] = "low"
    params = dict(
        model=cfg.model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": prompt}],
        output_config=output_config,
    )
    try:
        if cfg.model in FALLBACK_MODELS:
            response = await client.beta.messages.create(**params, betas=[FALLBACK_BETA], fallbacks="default")
        else:
            response = await client.messages.create(**params)
    except anthropic.AuthenticationError:
        raise AIError("Chiave API di Anthropic non valida.")
    except anthropic.PermissionDeniedError:
        raise AIError("La chiave API non ha il permesso di usare questo modello.")
    except anthropic.NotFoundError:
        raise AIError(f"Modello «{cfg.model}» non trovato: controlla il nome.")
    except anthropic.RateLimitError:
        raise AIError("Troppe richieste ad Anthropic: riprovo più tardi.")
    except anthropic.BadRequestError as exc:
        raise AIError(f"Anthropic ha rifiutato la richiesta: {exc.message}")
    except anthropic.APIStatusError as exc:
        if exc.status_code >= 500:
            raise AIError("Il servizio di Anthropic non risponde: riprovo più tardi.")
        raise AIError(f"Errore di Anthropic ({exc.status_code}): {exc.message}")
    except anthropic.APIConnectionError:
        raise AIError("Non riesco a collegarmi ad Anthropic. Controlla la rete del server.")
    finally:
        if anthropic_http_client is None:
            await client.close()

    if response.stop_reason == "refusal":
        raise AIError("Il modello ha rifiutato di rispondere a questa richiesta.")
    if response.stop_reason == "max_tokens":
        raise AIError("La risposta del modello è stata troppo lunga.")
    text = next((b.text for b in response.content if b.type == "text"), "")
    usage = Usage(response.usage.input_tokens or 0, response.usage.output_tokens or 0)
    return Result(_parse(text), usage, response.model)


# ---------- Ollama e compatibili OpenAI ----------


async def _openai(cfg: AIConfig, system: str, prompt: str, schema: dict, max_tokens: int) -> Result:
    url = cfg.base_url.rstrip("/") + "/chat/completions"
    body: dict = {
        "model": cfg.model,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
        "response_format": {"type": "json_schema", "json_schema": {"name": "risposta", "strict": True, "schema": schema}},
    }
    # Ollama usa max_tokens; OpenAI per i modelli recenti max_completion_tokens.
    body["max_tokens" if cfg.provider == "ollama" else "max_completion_tokens"] = max_tokens
    headers = {"Content-Type": "application/json"}
    if cfg.api_key:
        headers["Authorization"] = f"Bearer {cfg.api_key}"
    timeout = TIMEOUT_LOCAL if cfg.provider == "ollama" else TIMEOUT_CLOUD
    try:
        async with httpx.AsyncClient(timeout=timeout, transport=openai_transport) as client:
            res = await client.post(url, json=body, headers=headers)
    except httpx.TimeoutException:
        raise AIError("Il modello non ha risposto in tempo.")
    except httpx.HTTPError:
        raise AIError(f"Non riesco a collegarmi a {cfg.base_url}. Controlla l'indirizzo.")
    if res.status_code == 401:
        raise AIError("Chiave API non valida.")
    if res.status_code == 404:
        raise AIError(f"Modello «{cfg.model}» o indirizzo non trovato.")
    if res.status_code == 429:
        raise AIError("Troppe richieste al servizio AI: riprovo più tardi.")
    if res.status_code >= 400:
        detail = ""
        try:
            err = res.json().get("error")
            detail = err.get("message", "") if isinstance(err, dict) else str(err or "")
        except ValueError:
            pass
        raise AIError(f"Il servizio AI ha risposto con un errore ({res.status_code}). {detail}".strip())
    try:
        payload = res.json()
        choice = payload["choices"][0]
        text = choice["message"]["content"] or ""
    except (ValueError, KeyError, IndexError, TypeError):
        raise AIError("Risposta del servizio AI non valida.")
    if choice.get("finish_reason") == "length":
        raise AIError("La risposta del modello è stata troppo lunga.")
    u = payload.get("usage") or {}
    usage = Usage(int(u.get("prompt_tokens") or 0), int(u.get("completion_tokens") or 0))
    return Result(_parse(text), usage, payload.get("model") or cfg.model)


def _parse(text: str) -> dict:
    """JSON della risposta; i modelli locali a volte lo mettono tra ``` o aggiungono testo."""
    text = (text or "").strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fence:
        text = fence.group(1).strip()
    try:
        data = json.loads(text)
    except ValueError:
        start, end = text.find("{"), text.rfind("}")
        try:
            data = json.loads(text[start : end + 1]) if start >= 0 and end > start else None
        except ValueError:
            data = None
    if not isinstance(data, dict):
        raise AIError("Il modello non ha risposto nel formato richiesto.")
    return data
