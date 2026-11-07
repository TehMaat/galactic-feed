"""Quando esce un'Edizione (issue #19): ogni giorno, in alcuni giorni della settimana, una volta al mese.

Una pianificazione è un dizionario:
- {"kind": "daily", "times": ["07:30", "19:00"]}
- {"kind": "weekly", "days": [0, 4], "times": ["07:30"]}         (0 = lunedì … 6 = domenica)
- {"kind": "monthly", "day": 1, "times": ["08:00"]}               (giorno del mese; -1 = l'ultimo)
- {"kind": "monthly", "nth": 1, "weekday": 0, "times": ["08:00"]} (il primo lunedì; nth -1 = l'ultimo)
Il giorno 31 nei mesi più corti diventa l'ultimo giorno del mese. Gli orari sono nel fuso
dell'utente e tengono conto dell'ora legale (zoneinfo).
"""

from __future__ import annotations

import calendar
import re
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

TIME_RE = re.compile(r"^([01][0-9]|2[0-3]):[0-5][0-9]$")
KINDS = ("daily", "weekly", "monthly")
MAX_TIMES = 6
WEEKDAYS = ["lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica"]


def zone(tz: str) -> ZoneInfo:
    try:
        return ZoneInfo(tz)
    except Exception:
        return ZoneInfo("UTC")


def check(schedule: dict) -> dict:
    """La pianificazione ripulita, oppure ValueError con un messaggio in italiano."""
    if not isinstance(schedule, dict):
        raise ValueError("Pianificazione non valida.")
    kind = schedule.get("kind", "daily")
    if kind not in KINDS:
        raise ValueError("Pianificazione non valida: ogni giorno, ogni settimana oppure ogni mese.")
    times = sorted({str(t).strip() for t in schedule.get("times") or []})
    if not times:
        raise ValueError("Serve almeno un orario.")
    if len(times) > MAX_TIMES:
        raise ValueError(f"Al massimo {MAX_TIMES} orari.")
    if any(not TIME_RE.match(t) for t in times):
        raise ValueError("Orario non valido: scrivilo come 07:30.")
    out: dict = {"kind": kind, "times": times}
    if kind == "weekly":
        days = sorted({int(d) for d in schedule.get("days") or [] if str(d).lstrip("-").isdigit()})
        if not days or any(d < 0 or d > 6 for d in days):
            raise ValueError("Scegli almeno un giorno della settimana.")
        out["days"] = days
    elif kind == "monthly":
        if schedule.get("nth") is not None:
            nth, weekday = int(schedule["nth"]), int(schedule.get("weekday", 0))
            if nth not in (1, 2, 3, 4, -1) or not 0 <= weekday <= 6:
                raise ValueError("Scegli quale giorno del mese: per esempio il primo lunedì.")
            out.update(nth=nth, weekday=weekday)
        else:
            day = int(schedule.get("day", 1))
            if day != -1 and not 1 <= day <= 31:
                raise ValueError("Il giorno del mese va da 1 a 31, oppure «ultimo».")
            out["day"] = day
    return out


def _runs_on(schedule: dict, d: date) -> bool:
    kind = schedule["kind"]
    if kind == "daily":
        return True
    if kind == "weekly":
        return d.weekday() in schedule["days"]
    last = calendar.monthrange(d.year, d.month)[1]
    if "nth" in schedule:
        if d.weekday() != schedule["weekday"]:
            return False
        if schedule["nth"] == -1:
            return d.day + 7 > last
        return (d.day - 1) // 7 + 1 == schedule["nth"]
    day = schedule["day"]
    return d.day == (last if day == -1 else min(day, last))


def _occurrences(schedule: dict, tz: str, first: date, last: date):
    zone_ = zone(tz)
    d = first
    while d <= last:
        if _runs_on(schedule, d):
            for t in schedule["times"]:
                h, m = (int(x) for x in t.split(":"))
                yield datetime(d.year, d.month, d.day, h, m, tzinfo=zone_), t
        d += timedelta(days=1)


def last_occurrence(schedule: dict, tz: str, ts: int, lookback_days: int = 70) -> tuple[int, str] | None:
    """L'uscita più recente già passata: (momento, «HH:MM»), oppure None."""
    today = datetime.fromtimestamp(ts, zone(tz)).date()
    past = [(dt, t) for dt, t in _occurrences(schedule, tz, today - timedelta(days=lookback_days), today + timedelta(days=1)) if dt.timestamp() <= ts]
    if not past:
        return None
    dt, t = past[-1]
    return int(dt.timestamp()), t


def next_occurrences(schedule: dict, tz: str, ts: int, count: int = 3, horizon_days: int = 400) -> list[tuple[int, str]]:
    today = datetime.fromtimestamp(ts, zone(tz)).date()
    out = []
    for dt, t in _occurrences(schedule, tz, today - timedelta(days=1), today + timedelta(days=horizon_days)):
        if dt.timestamp() > ts:
            out.append((int(dt.timestamp()), t))
            if len(out) >= count:
                break
    return out


def is_due(schedule: dict, tz: str, ts: int, last_created: int | None) -> str | None:
    """L'orario dell'uscita da comporre adesso, oppure None se è già fatta (o non è il giorno)."""
    found = last_occurrence(schedule, tz, ts)
    if found is None:
        return None
    slot_ts, slot = found
    if last_created is not None and last_created >= slot_ts:
        return None
    if last_created is None and ts - slot_ts > (86400 if schedule["kind"] == "daily" else 3 * 3600):
        # Prima uscita: un'Edizione giornaliera parte subito; una settimanale o mensile appena
        # creata aspetta la sua data invece di recuperarne una di giorni fa.
        return None
    return slot


def window_seconds(schedule: dict, period: str = "auto") -> tuple[int, int]:
    """(periodo per la prima uscita, periodo massimo) coperti da un'Edizione, in secondi."""
    day = 86400
    fixed = {"day": day, "week": 7 * day, "month": 31 * day}
    if period in fixed:
        return fixed[period], fixed[period]
    kind = schedule.get("kind", "daily")
    if kind == "weekly":
        return 7 * day, 8 * day
    if kind == "monthly":
        return 31 * day, 32 * day
    return day, 2 * day


def describe(schedule: dict) -> str:
    """«ogni giorno alle 07:30», «lunedì e venerdì alle 08:00», «il primo lunedì del mese alle 09:00»."""
    times = " e ".join(schedule.get("times", []))
    kind = schedule.get("kind", "daily")
    if kind == "weekly":
        days = [WEEKDAYS[d] for d in schedule.get("days", [])]
        when = "dal lunedì al venerdì" if schedule.get("days") == [0, 1, 2, 3, 4] else ", ".join(days[:-1]) + (" e " if len(days) > 1 else "") + days[-1] if days else ""
        return f"{when} alle {times}"
    if kind == "monthly":
        if "nth" in schedule:
            nth = {1: "il primo", 2: "il secondo", 3: "il terzo", 4: "il quarto", -1: "l'ultimo"}[schedule["nth"]]
            return f"{nth} {WEEKDAYS[schedule['weekday']]} del mese alle {times}"
        day = schedule.get("day", 1)
        if day == -1:
            return f"l'ultimo giorno di ogni mese alle {times}"
        tail = " (o l'ultimo, nei mesi più corti)" if day > 28 else ""
        return f"il giorno {day} di ogni mese{tail} alle {times}"
    return f"ogni giorno alle {times}"
