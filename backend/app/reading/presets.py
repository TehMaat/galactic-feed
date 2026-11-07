"""Gruppi di parole pronti, forniti con l'app: un punto di partenza per interessi e silenziati.

All'avvio si aggiungono quelli che mancano (seed); quelli già presenti non si toccano, così
le modifiche dell'amministratore restano. Le parole si confrontano come gli interessi:
parole intere, senza maiuscole né accenti, singolare e plurale. Si evitano parole troppo
generiche o con un altro significato comune (per esempio «Roma» per il calcio).
"""

from __future__ import annotations

import json
import sqlite3

from ..db import now

BUILTIN: list[tuple[str, str, list[str]]] = [
    ("motori", "Motori", ["auto", "automobile", "motore", "macchina", "moto", "Formula 1", "MotoGP", "Ferrari", "Ducati",
                          "auto elettrica", "pilota", "Gran Premio", "salone dell'auto", "concessionaria"]),
    ("politica", "Politica", ["governo", "parlamento", "elezioni", "ministro", "premier", "senato", "camera dei deputati",
                              "partito", "opposizione", "legge di bilancio", "decreto", "sondaggio", "referendum", "sindaco"]),
    ("economia", "Economia", ["economia", "inflazione", "borsa", "Pil", "tassi", "Bce", "spread", "mercati", "bolletta",
                              "stipendi", "pensioni", "tasse", "fisco", "mutuo", "disoccupazione"]),
    ("tecnologia", "Tecnologia", ["tecnologia", "smartphone", "app", "software", "intelligenza artificiale", "Apple", "Google",
                                  "Microsoft", "Android", "iPhone", "computer", "chip", "startup", "cybersicurezza", "hacker"]),
    ("videogiochi", "Videogiochi", ["videogioco", "gaming", "PlayStation", "Xbox", "Nintendo", "Steam", "console",
                                    "esports", "gameplay", "Game Pass", "Nintendo Switch"]),
    ("sport", "Sport", ["sport", "Olimpiadi", "tennis", "basket", "pallavolo", "ciclismo", "Giro d'Italia", "atletica",
                        "nuoto", "sci", "rugby", "campionato", "medaglia"]),
    ("calcio", "Calcio", ["calcio", "Serie A", "Champions League", "Europa League", "gol", "allenatore", "calciomercato",
                          "Juventus", "Inter", "Milan", "Nazionale", "rigore", "Coppa Italia"]),
    ("scienza", "Scienza", ["scienza", "scoperta scientifica", "fisica", "chimica", "biologia", "astronomia",
                            "spazio", "Nasa", "Esa", "clima", "ricercatori", "università"]),
    ("salute", "Salute", ["salute", "medicina", "ospedale", "medico", "vaccino", "malattia", "virus", "farmaco",
                          "sanità", "dieta", "benessere", "tumore", "Oms"]),
    ("spettacolo", "Spettacolo", ["cinema", "film", "serie tv", "attore", "attrice", "regista", "Sanremo", "concerto",
                                  "musica", "album", "Netflix", "festival", "gossip", "televisione"]),
    ("cronaca", "Cronaca", ["cronaca", "incidente", "arresto", "omicidio", "polizia", "carabinieri", "indagine",
                            "processo", "tribunale", "rapina", "furto"]),
]


def seed(conn: sqlite3.Connection) -> int:
    """Aggiunge i gruppi forniti con l'app che non ci sono ancora. Restituisce quanti ne ha aggiunti."""
    existing = {r["key"] for r in conn.execute("SELECT key FROM preset_groups WHERE key IS NOT NULL")}
    taken = {r["name"].lower() for r in conn.execute("SELECT name FROM preset_groups")}
    added = 0
    with conn:
        for position, (key, name, words) in enumerate(BUILTIN):
            if key in existing or name.lower() in taken:
                continue
            conn.execute(
                "INSERT INTO preset_groups (key, name, words, builtin, position, updated_at) VALUES (?, ?, ?, 1, ?, ?)",
                (key, name, json.dumps(words, ensure_ascii=False), position, now()),
            )
            added += 1
    return added
