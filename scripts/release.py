#!/usr/bin/env python3
"""Versioni di Galactic Feed.

Il numero di versione sta in un solo posto, il file VERSION alla radice del repository;
il server lo legge all'avvio. Questo script lo copia anche nei file dei pacchetti, che
devono restare uguali (lo controllano i test), e prepara le note di una release.

    python3 scripts/release.py check              # VERSION, pacchetti e CHANGELOG coincidono?
    python3 scripts/release.py check v0.4.0       # …e coincidono anche con questo tag?
    python3 scripts/release.py bump 0.4.0         # nuova versione in tutti i file (e «Da pubblicare» → 0.4.0)
    python3 scripts/release.py notes 0.4.0        # note della versione, prese da CHANGELOG.md

Le versioni seguono semver: MAGGIORE.MINORE.CORRETTIVA (per esempio 0.3.1), con un
eventuale suffisso per le prove (0.4.0-rc.1).
"""

from __future__ import annotations

import json
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEMVER = re.compile(r"^(\d+)\.(\d+)\.(\d+)(-[0-9A-Za-z.-]+)?$")
PYPROJECT = ROOT / "backend" / "pyproject.toml"
PACKAGE = ROOT / "frontend" / "package.json"
LOCK = ROOT / "frontend" / "package-lock.json"
CHANGELOG = ROOT / "CHANGELOG.md"
COMPOSE = ROOT / "docker-compose.yml"


def read_version() -> str:
    return (ROOT / "VERSION").read_text(encoding="utf-8").strip()


def package_versions() -> dict[str, str]:
    """La versione scritta in ogni file che ne ha una copia."""
    pyproject = re.search(r'^version\s*=\s*"([^"]+)"', PYPROJECT.read_text(encoding="utf-8"), re.M)
    lock = json.loads(LOCK.read_text(encoding="utf-8"))
    return {
        "backend/pyproject.toml": pyproject.group(1) if pyproject else "",
        "frontend/package.json": json.loads(PACKAGE.read_text(encoding="utf-8"))["version"],
        "frontend/package-lock.json": lock["version"],
        "frontend/package-lock.json (packages)": lock["packages"][""]["version"],
    }


def notes(version: str) -> str | None:
    """Il testo della sezione «## [versione]» di CHANGELOG.md, senza il titolo."""
    text = CHANGELOG.read_text(encoding="utf-8")
    match = re.search(rf"^## \[{re.escape(version)}\][^\n]*\n(.*?)(?=^## \[|\Z)", text, re.M | re.S)
    return match.group(1).strip() if match else None


def check(tag: str | None = None) -> list[str]:
    """Gli errori trovati: lista vuota se è tutto in ordine."""
    version = read_version()
    errors = []
    if not SEMVER.match(version):
        errors.append(f"VERSION contiene «{version}», che non è una versione MAGGIORE.MINORE.CORRETTIVA.")
    for name, value in package_versions().items():
        if value != version:
            errors.append(f"{name} dice {value}, VERSION dice {version}: usa «scripts/release.py bump {version}».")
    if not notes(version):
        errors.append(f"In CHANGELOG.md manca la sezione «## [{version}]».")
    if tag is not None and tag.removeprefix("refs/tags/").removeprefix("v") != version:
        errors.append(f"Il tag {tag} non corrisponde a VERSION ({version}).")
    return errors


def bump(version: str) -> None:
    if not SEMVER.match(version):
        raise SystemExit(f"«{version}» non è una versione valida (esempio: 0.4.0).")
    (ROOT / "VERSION").write_text(version + "\n", encoding="utf-8")
    PYPROJECT.write_text(
        re.sub(r'^version\s*=\s*"[^"]+"', f'version = "{version}"', PYPROJECT.read_text(encoding="utf-8"), count=1, flags=re.M),
        encoding="utf-8",
    )
    package = json.loads(PACKAGE.read_text(encoding="utf-8"))
    package["version"] = version
    PACKAGE.write_text(json.dumps(package, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    lock = json.loads(LOCK.read_text(encoding="utf-8"))
    lock["version"] = version
    lock["packages"][""]["version"] = version
    LOCK.write_text(json.dumps(lock, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    # Il docker-compose.yml d'esempio usa la serie MAGGIORE.MINORE (riceve le correttive da solo).
    major, minor = SEMVER.match(version).groups()[:2]
    if not SEMVER.match(version).group(4):
        COMPOSE.write_text(
            re.sub(r"(ghcr\.io/tehmaat/galactic-feed:)[\w.-]+", rf"\g<1>{major}.{minor}", COMPOSE.read_text(encoding="utf-8")),
            encoding="utf-8",
        )
    text = CHANGELOG.read_text(encoding="utf-8")
    if not notes(version) and "## [Da pubblicare]" in text:
        # Le novità raccolte durante lo sviluppo diventano quelle della versione.
        CHANGELOG.write_text(text.replace("## [Da pubblicare]", f"## [{version}] – {date.today().isoformat()}", 1), encoding="utf-8")
        print(f"La sezione «Da pubblicare» di CHANGELOG.md ora è la {version}.")
    elif not notes(version):
        head = f"## [{version}] – {date.today().isoformat()}\n\n- …\n\n"
        first = text.find("\n## [")
        text = text[: first + 1] + head + text[first + 1 :] if first >= 0 else text + "\n" + head
        CHANGELOG.write_text(text, encoding="utf-8")
        print(f"Aggiunta in CHANGELOG.md la sezione {version}: scrivi cosa cambia.")
    print(f"Versione {version}. Al merge su main il workflow pubblica immagini, tag v{version} e release.")


def main(argv: list[str]) -> int:
    if len(argv) >= 2 and argv[1] == "check":
        errors = check(argv[2] if len(argv) > 2 else None)
        for e in errors:
            print("✗ " + e, file=sys.stderr)
        if not errors:
            print(f"✓ Versione {read_version()}: file e CHANGELOG coincidono.")
        return 1 if errors else 0
    if len(argv) == 3 and argv[1] == "bump":
        bump(argv[2])
        return 0
    if len(argv) == 3 and argv[1] == "notes":
        text = notes(argv[2].removeprefix("v"))
        if text is None:
            print(f"In CHANGELOG.md non c'è la sezione {argv[2]}.", file=sys.stderr)
            return 1
        print(text)
        return 0
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
