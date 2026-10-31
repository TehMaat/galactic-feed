from app.reading.dedupe import similar
from app.reading.matching import word_pattern
from app.reading.text import normalize, title_key


def _m(keyword, text):
    return bool(word_pattern(keyword).search(normalize(text)))


def test_whole_words_case_and_accents():
    assert _m("Docker", "Il mio stack DOCKER in casa")
    assert not _m("Docker", "dockerfile")
    assert _m("perché", "Perche succede")
    assert _m("caffè", "Il caffe del mattino")


def test_italian_singular_and_plural():
    assert _m("Razzi", "Un razzo riutilizzabile")
    assert _m("Galassie", "Come si misura una galassia")
    assert _m("amica", "Le amiche del liceo")
    assert _m("Luna", "Missioni verso le lune di Giove")
    assert not _m("Luna", "Un viaggio lungo")
    assert not _m("Luna", "Il modulo lunare")
    assert not _m("RSS", "rssi")


def test_phrases():
    assert _m("Self-hosting", "Guida al self hosting")
    assert _m("self hosting", "Self-Hosting per tutti")
    assert not _m("self hosting", "self service hosting")


def test_title_key_and_similarity():
    a = title_key("Artemis III: la NASA rinvia lo sbarco sulla Luna al 2027")
    b = title_key("La NASA rinvia lo sbarco sulla Luna di Artemis III al 2027")
    c = title_key("SpaceX lancia altri 20 satelliti Starlink")
    assert similar(a, b)
    assert not similar(a, c)
    # Titoli corti: solo se identici.
    assert similar(title_key("Notizie del giorno"), title_key("Le notizie del giorno")) is False
    assert similar(title_key("Borsa Milano chiusura"), title_key("Milano borsa: chiusura"))
