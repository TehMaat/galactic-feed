"""Più Edizioni con regole (#18), ricorrenze settimanali e mensili (#19), nazione delle fonti (#20)."""

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from app.feeds.geo import detect
from app.reading import edition, schedule
from conftest import invite_user
from helpers import entry, feed, source_id, user_id

ROME = "Europe/Rome"


def ts(text: str) -> int:
    return int(datetime.fromisoformat(text).replace(tzinfo=ZoneInfo(ROME)).timestamp())


def local(t: int) -> str:
    return datetime.fromtimestamp(t, ZoneInfo(ROME)).strftime("%a %Y-%m-%d %H:%M")


# ---------- #19 Pianificazioni ----------


def test_weekly_and_monthly_occurrences():
    every_monday = schedule.check({"kind": "weekly", "days": [0], "times": ["07:30"]})
    assert [local(t) for t, _ in schedule.next_occurrences(every_monday, ROME, ts("2026-11-07 10:00"))] == [
        "Mon 2026-11-09 07:30", "Mon 2026-11-16 07:30", "Mon 2026-11-23 07:30",
    ]
    first_of_month = schedule.check({"kind": "monthly", "day": 1, "times": ["08:00"]})
    assert [local(t) for t, _ in schedule.next_occurrences(first_of_month, ROME, ts("2026-11-07 10:00"), 2)] == [
        "Tue 2026-12-01 08:00", "Fri 2027-01-01 08:00",
    ]
    # Il 31 nei mesi più corti diventa l'ultimo giorno.
    day31 = schedule.check({"kind": "monthly", "day": 31, "times": ["08:00"]})
    assert [local(t) for t, _ in schedule.next_occurrences(day31, ROME, ts("2027-01-31 09:00"), 3)] == [
        "Sun 2027-02-28 08:00", "Wed 2027-03-31 08:00", "Fri 2027-04-30 08:00",
    ]
    first_monday = schedule.check({"kind": "monthly", "nth": 1, "weekday": 0, "times": ["09:00"]})
    assert local(schedule.next_occurrences(first_monday, ROME, ts("2026-11-07 10:00"), 1)[0][0]) == "Mon 2026-12-07 09:00"
    last_day = schedule.check({"kind": "monthly", "day": -1, "times": ["20:00"]})
    assert local(schedule.next_occurrences(last_day, ROME, ts("2027-02-10 10:00"), 1)[0][0]) == "Sun 2027-02-28 20:00"


def test_daylight_saving_keeps_local_time():
    daily = schedule.check({"kind": "daily", "times": ["07:30"]})
    # In Italia l'ora legale finisce il 25 ottobre 2026: l'orario resta 07:30 ora locale.
    got = [local(t) for t, _ in schedule.next_occurrences(daily, ROME, ts("2026-10-24 10:00"), 2)]
    assert got == ["Sun 2026-10-25 07:30", "Mon 2026-10-26 07:30"]
    first, second = (t for t, _ in schedule.next_occurrences(daily, ROME, ts("2026-10-24 10:00"), 2))
    assert second - first == 24 * 3600


def test_weekly_is_due_only_on_its_days():
    mondays = schedule.check({"kind": "weekly", "days": [0], "times": ["07:30"]})
    assert schedule.is_due(mondays, ROME, ts("2026-11-09 08:00"), None) == "07:30"
    # Creata di martedì: aspetta lunedì prossimo invece di recuperare quella di ieri.
    assert schedule.is_due(mondays, ROME, ts("2026-11-10 12:00"), None) is None
    assert schedule.is_due(mondays, ROME, ts("2026-11-12 08:00"), ts("2026-11-09 07:31")) is None
    assert schedule.is_due(mondays, ROME, ts("2026-11-16 07:45"), ts("2026-11-09 07:31")) == "07:30"


def test_schedule_validation_and_description():
    with pytest.raises(ValueError):
        schedule.check({"kind": "weekly", "days": [], "times": ["07:30"]})
    with pytest.raises(ValueError):
        schedule.check({"kind": "monthly", "day": 32, "times": ["07:30"]})
    with pytest.raises(ValueError):
        schedule.check({"kind": "daily", "times": ["25:00"]})
    assert schedule.describe(schedule.check({"kind": "weekly", "days": [0, 1, 2, 3, 4], "times": ["07:30"]})) == "dal lunedì al venerdì alle 07:30"
    assert schedule.describe(schedule.check({"kind": "weekly", "days": [0, 4], "times": ["18:00"]})) == "lunedì e venerdì alle 18:00"
    assert schedule.describe(schedule.check({"kind": "monthly", "nth": 1, "weekday": 0, "times": ["09:00"]})) == "il primo lunedì del mese alle 09:00"


# ---------- #18 Più Edizioni con regole ----------


def _news(app, client):
    politics = client.post("/api/folders", json={"name": "Attualità"}).json()["folder"]["id"]
    feed(app, client, "https://notizie.example.it/feed", [
        entry("Il governo approva la manovra", hours_ago=1),
        entry("Elezioni regionali: i risultati", hours_ago=2),
        entry("Nuova console Nintendo in arrivo", hours_ago=3),
    ], title="Notizie IT", folder_id=politics)
    feed(app, client, "https://news.example.com/feed", [
        entry("Congress votes on the budget", hours_ago=1),
        entry("New Xbox revealed", hours_ago=2),
    ], title="News US")
    with app.state.ctx.db.session() as conn, conn:
        conn.execute("UPDATE feeds SET country = 'IT' WHERE url LIKE '%.it/%'")
        conn.execute("UPDATE feeds SET country = 'US' WHERE url LIKE '%.com/%'")
    client.put(f"/api/sources/{source_id(client, 'Notizie IT')}/tags", json={"tags": ["Politica"]})
    client.put(f"/api/sources/{source_id(client, 'News US')}/tags", json={"tags": ["Politica"]})
    return politics


def _titles(ed):
    items = ([ed["hero"]] if ed["hero"] else []) + [a for s in ed["sections"] for a in s["items"]]
    return [a["title"] for a in items]


def _tag(client, name):
    return next(t["id"] for t in client.get("/api/tags").json()["tags"] if t["name"] == name)


def test_edition_with_tag_and_country_rules(admin, app):
    _news(app, admin)
    rules = {"tags": [_tag(admin, "Politica")], "countries": ["IT"]}
    r = admin.post("/api/edition-configs/preview", json={"rules": rules})
    assert r.status_code == 200 and r.json()["available"] == 3  # tutte le notizie della fonte italiana
    r = admin.post("/api/edition-configs", json={"name": "Politica · Italia", "rules": rules,
                                                 "schedule": {"kind": "weekly", "days": [0], "times": ["07:30"]}})
    assert r.status_code == 201, r.text
    config = next(c for c in r.json()["configs"] if c["name"] == "Politica · Italia")
    assert config["description"] == "lunedì alle 07:30" and len(config["next"]) == 3
    ed = admin.post("/api/editions", json={"config_id": config["id"]}).json()["edition"]
    assert ed["name"] == "Politica · Italia" and ed["number"] == 1
    assert sorted(_titles(ed)) == ["Elezioni regionali: i risultati", "Il governo approva la manovra", "Nuova console Nintendo in arrivo"]


def test_edition_with_word_group_rule(admin, app):
    _news(app, admin)
    preset = next(p for p in admin.get("/api/interests").json()["presets"] if p["name"] == "Videogiochi")
    group = admin.post("/api/groups", json={"preset_id": preset["id"]}).json()["groups"][0]["id"]
    r = admin.post("/api/edition-configs", json={"name": "Videogiochi", "rules": {"groups": [group]}})
    config = next(c for c in r.json()["configs"] if c["name"] == "Videogiochi")
    ed = admin.post("/api/editions", json={"config_id": config["id"]}).json()["edition"]
    assert sorted(_titles(ed)) == ["New Xbox revealed", "Nuova console Nintendo in arrivo"]


def test_folder_rule_and_max_items(admin, app):
    folder = _news(app, admin)
    r = admin.post("/api/edition-configs", json={"name": "Solo cartella", "rules": {"folders": [str(folder)]}, "max_items": 5})
    config = next(c for c in r.json()["configs"] if c["name"] == "Solo cartella")
    assert len(_titles(admin.post("/api/editions", json={"config_id": config["id"]}).json()["edition"])) == 3
    r = admin.post("/api/edition-configs", json={"name": "Senza cartella", "rules": {"folders": ["none"]}})
    config = next(c for c in r.json()["configs"] if c["name"] == "Senza cartella")
    assert sorted(_titles(admin.post("/api/editions", json={"config_id": config["id"]}).json()["edition"])) == [
        "Congress votes on the budget", "New Xbox revealed",
    ]


def test_several_editions_are_independent(admin, app):
    _news(app, admin)
    a = admin.post("/api/edition-configs", json={"name": "Mattina"}).json()["configs"]
    b = admin.post("/api/edition-configs", json={"name": "USA", "rules": {"countries": ["US"]}}).json()["configs"]
    mattina, usa = a[0]["id"], next(c["id"] for c in b if c["name"] == "USA")
    assert admin.get("/api/me").json()["user"]["prefs"]["edition"] is True
    admin.post("/api/editions", json={"config_id": mattina})
    ed = admin.post("/api/editions", json={"config_id": usa}).json()
    # Numerazione per Edizione, e il selettore in Oggi con l'ultima uscita per prima.
    assert ed["edition"]["number"] == 1 and ed["edition"]["name"] == "USA"
    assert [c["name"] for c in ed["configs"]] == ["USA", "Mattina"]
    assert admin.get("/api/editions/latest", params={"config": mattina}).json()["edition"]["name"] == "Mattina"
    assert admin.post("/api/editions", json={"config_id": usa}).status_code == 429


def test_manage_configs(admin, app):
    r = admin.post("/api/edition-configs", json={"name": "Una"}).json()["configs"]
    cid = r[0]["id"]
    r = admin.patch(f"/api/edition-configs/{cid}", json={"active": False, "max_items": 50, "period": "week",
                                                         "schedule": {"kind": "monthly", "nth": -1, "weekday": 4, "times": ["18:00"]}})
    c = r.json()["configs"][0]
    assert (c["active"], c["max_items"], c["period"]) == (False, 50, "week") and c["next"] == []
    assert c["description"] == "l'ultimo venerdì del mese alle 18:00"
    assert admin.get("/api/me").json()["user"]["prefs"]["edition"] is False
    r = admin.post(f"/api/edition-configs/{cid}/duplicate").json()["configs"]
    assert [x["name"] for x in r] == ["Una", "Una (copia)"]
    r = admin.put("/api/edition-configs/order", json={"ids": [r[1]["id"], cid]}).json()["configs"]
    assert [x["name"] for x in r] == ["Una (copia)", "Una"]
    assert admin.delete(f"/api/edition-configs/{cid}").json()["configs"][0]["name"] == "Una (copia)"
    # Validazione: pianificazione, regole di un altro utente, nome.
    assert admin.post("/api/edition-configs", json={"schedule": {"kind": "weekly", "days": [], "times": ["07:30"]}}).status_code == 422
    bruno = invite_user(admin, app, "bruno")
    bruno.post("/api/tags", json={"name": "Suo"})
    other_tag = bruno.get("/api/tags").json()["tags"][0]["id"]
    assert admin.post("/api/edition-configs", json={"rules": {"tags": [other_tag]}}).status_code == 422
    assert admin.post("/api/edition-configs", json={"name": " "}).status_code == 422
    assert bruno.patch(f"/api/edition-configs/{r[0]['id']}", json={"active": True}).status_code == 404


def test_delete_a_single_issue(admin, app):
    _news(app, admin)
    cid = admin.post("/api/edition-configs", json={"name": "Prova"}).json()["configs"][0]["id"]
    first = admin.post("/api/editions", json={"config_id": cid}).json()["edition"]
    with app.state.ctx.db.session() as conn, conn:
        conn.execute("UPDATE editions SET created_at = created_at - 120 WHERE id = ?", (first["id"],))
    second = admin.post("/api/editions", json={"config_id": cid}).json()["edition"]
    r = admin.delete(f"/api/editions/{second['id']}")
    assert r.status_code == 200 and r.json()["edition"]["id"] == first["id"]
    assert admin.get(f"/api/editions/{second['id']}").status_code == 404
    assert admin.delete(f"/api/editions/{first['id']}").json()["edition"] is None
    # L'Edizione resta, senza uscite.
    assert [c["name"] for c in admin.get("/api/edition-configs").json()["configs"]] == ["Prova"]
    bruno = invite_user(admin, app, "bruno")
    third = admin.post("/api/editions", json={"config_id": cid}).json()["edition"]
    assert bruno.delete(f"/api/editions/{third['id']}").status_code == 404


def test_weekly_edition_is_composed_by_the_scheduler_on_its_day(admin, app):
    _news(app, admin)
    admin.post("/api/edition-configs", json={"name": "Lunedì", "schedule": {"kind": "weekly", "days": [0], "times": ["07:30"]}})
    assert edition.run_due(app.state.ctx, ts("2026-11-10 08:00")) == []  # martedì
    made = edition.run_due(app.state.ctx, ts("2026-11-16 07:31"))
    assert len(made) == 1 and made[0][0] == user_id(admin)
    assert edition.run_due(app.state.ctx, ts("2026-11-16 09:00")) == []


def test_existing_edition_becomes_the_first_config(admin, app):
    """Chi aveva già l'Edizione (versioni precedenti) ritrova «La mia Edizione» con orari e numeri."""
    feed(app, admin, "https://a.example/feed", [entry("Prima", hours_ago=1)], title="A")
    uid = user_id(admin)
    with app.state.ctx.db.session() as conn, conn:
        conn.execute("UPDATE users SET prefs = ?, editions_ready = 0 WHERE id = ?",
                     ('{"edition": true, "edition_times": ["06:45", "18:00"]}', uid))
        conn.execute("INSERT INTO editions (user_id, number, slot, since, stats, created_at) VALUES (?, 7, '06:45', 0, '{}', 1)", (uid,))
    configs = admin.get("/api/edition-configs").json()["configs"]
    assert [(c["name"], c["active"], c["schedule"]) for c in configs] == [
        ("La mia Edizione", True, {"kind": "daily", "times": ["06:45", "18:00"]}),
    ]
    assert configs[0]["rules"] == {"tags": [], "folders": [], "countries": [], "groups": []}
    # La numerazione continua da dove era arrivata.
    ed = admin.post("/api/editions").json()["edition"]
    assert ed["number"] == 8 and ed["name"] == "La mia Edizione"
    # Le preferenze di prima (API precedenti) cambiano la prima Edizione.
    admin.patch("/api/me", json={"prefs": {"edition_times": ["08:00"]}})
    assert admin.get("/api/edition-configs").json()["configs"][0]["schedule"]["times"] == ["08:00"]


def test_user_timezone(admin):
    admin.post("/api/edition-configs", json={"name": "NY", "schedule": {"kind": "daily", "times": ["07:00"]}})
    assert admin.get("/api/edition-configs").json()["timezone"] == "Europe/Rome"
    admin.patch("/api/me", json={"prefs": {"timezone": "America/New_York"}})
    data = admin.get("/api/edition-configs").json()
    assert data["timezone"] == "America/New_York"
    at = datetime.fromisoformat(data["configs"][0]["next"][0]["at"].replace("Z", "+00:00"))
    assert at.astimezone(ZoneInfo("America/New_York")).strftime("%H:%M") == "07:00"
    assert admin.patch("/api/me", json={"prefs": {"timezone": "Marte/Base"}}).status_code == 422


# ---------- #20 Nazione delle fonti ----------


def test_country_and_language_are_guessed():
    assert detect(["https://www.ilpost.it/", "https://www.ilpost.it/feed"], None, []) == ("", "IT")
    assert detect(["https://www.bbc.co.uk/news"], "en-gb", []) == ("en", "GB")
    assert detect(["https://www.theverge.com/"], "en-US", []) == ("en", "US")
    assert detect(["https://www.theverge.com/"], "en", []) == ("en", "")
    assert detect(["https://example.com/"], None, ["Il governo e la manovra", "La Luna e il polo sud", "Una nuova legge per la scuola"]) == ("it", "IT")
    assert detect(["https://lemonde.fr/"], "fr-FR", []) == ("fr", "FR")


def test_country_from_fetch_override_and_filter(admin, app):
    _news(app, admin)
    it, us = source_id(admin, "Notizie IT"), source_id(admin, "News US")
    sources = {s["id"]: s for s in admin.get("/api/sources").json()["sources"]}
    assert (sources[it]["country"], sources[it]["country_origin"]) == ("IT", "auto")
    titles = lambda **p: sorted(a["title"] for a in admin.get("/api/articles", params=p).json()["items"])  # noqa: E731
    assert titles(country="US") == ["Congress votes on the budget", "New Xbox revealed"]
    assert admin.get("/api/articles/counts").json()["countries"] == {"IT": 3, "US": 2}
    # L'utente la cambia per sé; null torna a quella automatica.
    s = admin.patch(f"/api/sources/{us}", json={"country": "gb"}).json()["source"]
    assert (s["country"], s["country_origin"], s["country_auto"]) == ("GB", "user", "US")
    assert titles(country="GB") == ["Congress votes on the budget", "New Xbox revealed"]
    assert admin.patch(f"/api/sources/{us}", json={"country": None}).json()["source"]["country"] == "US"
    assert admin.patch(f"/api/sources/{us}", json={"country": "USA"}).status_code == 422
    assert admin.get("/api/articles", params={"country": "123"}).status_code == 422


def test_admin_corrects_the_shared_country(admin, app):
    _news(app, admin)
    bruno = invite_user(admin, app, "bruno")
    feed(app, bruno, "https://news.example.com/feed", [], title="News US")
    assert bruno.get("/api/admin/feeds").status_code == 403
    feeds = admin.get("/api/admin/feeds").json()["feeds"]
    us = next(f for f in feeds if f["url"] == "https://news.example.com/feed")
    assert (us["country"], us["followers"]) == ("US", 2)
    r = admin.patch(f"/api/admin/feeds/{us['id']}", json={"country": "CA"})
    assert next(f for f in r.json()["feeds"] if f["id"] == us["id"])["country"] == "CA"
    # Vale per tutti, tranne per chi l'ha scelta per sé.
    s = next(x for x in bruno.get("/api/sources").json()["sources"] if x["title"] == "News US")
    assert (s["country"], s["country_origin"]) == ("CA", "admin")
    admin.patch(f"/api/admin/feeds/{us['id']}", json={"country": None})
    s = next(x for x in bruno.get("/api/sources").json()["sources"] if x["title"] == "News US")
    assert (s["country"], s["country_origin"]) == ("US", "auto")
