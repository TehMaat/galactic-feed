#!/usr/bin/env python3
"""Documentazione di Galactic Feed: diagrammi e controlli (#55).

    python3 scripts/docs.py diagrammi     # docs/diagrammi/*.mmd → docs/img/diagrammi/*-chiaro.svg e *-scuro.svg
    python3 scripts/docs.py diagrammi --tutti   # …ridisegnando anche quelli già aggiornati
    python3 scripts/docs.py check         # le docs sono in ordine? (lo fa anche il job «documenti» dei test)

I diagrammi si scrivono in Mermaid in docs/diagrammi/ e diventano immagini SVG, una per il tema
chiaro e una per lo scuro, che si vedono ovunque (GitHub, GHCR, un editor, offline). Per
disegnarli serve Node: lo script usa @mermaid-js/mermaid-cli con npx, oppure il comando
indicato in MMDC. Con un Chromium già installato si indica in PUPPETEER_EXECUTABLE_PATH.

Ogni SVG porta l'impronta (sha256) del suo sorgente e del tema: il controllo si accorge se un
diagramma è cambiato senza rigenerare le immagini, senza bisogno di ridisegnarlo.

Il controllo verifica anche:
- che ogni variabile d'ambiente letta dal server sia nella tabella di docs/configurazione.md, e viceversa;
- che i link interni (file, immagini, ancore) di README e docs portino da qualche parte;
- che non ci siano dati reali: indirizzi IP fuori da quelli di documentazione, email e host di casa;
- che il badge «Full Vibe Coded» ci sia nel README e nell'indice delle docs (#53);
- che la serie consigliata (per esempio 0.10) scritta nelle docs sia quella di VERSION.
"""

from __future__ import annotations

import hashlib
import ipaddress
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
SOURCES = DOCS / "diagrammi"
IMAGES = DOCS / "img" / "diagrammi"
MERMAID_CLI = "@mermaid-js/mermaid-cli@11.4.2"

# Colori presi dall'app: verde petrolio come colore principale, blu notte per lo scuro.
FONT = "Inter, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"
THEMES = {
    "chiaro": {
        "theme": "base",
        "themeVariables": {
            "fontFamily": FONT,
            "fontSize": "15px",
            "background": "transparent",
            "primaryColor": "#E2F3EF",
            "primaryBorderColor": "#0B6E5F",
            "primaryTextColor": "#111827",
            "secondaryColor": "#EEF1F7",
            "secondaryBorderColor": "#8B93A7",
            "secondaryTextColor": "#111827",
            "tertiaryColor": "#F7F8FB",
            "tertiaryBorderColor": "#C7CDDA",
            "tertiaryTextColor": "#111827",
            "lineColor": "#5B6475",
            "textColor": "#111827",
            "clusterBkg": "#F4F6FA",
            "clusterBorder": "#C7CDDA",
            "edgeLabelBackground": "#FFFFFF",
            "noteBkgColor": "#FFF4D6",
            "noteBorderColor": "#D9A21B",
            "noteTextColor": "#3B2F0B",
            "actorBkg": "#E2F3EF",
            "actorBorder": "#0B6E5F",
            "actorTextColor": "#111827",
            "signalColor": "#3D4454",
            "signalTextColor": "#111827",
            "labelBoxBkgColor": "#E2F3EF",
            "labelBoxBorderColor": "#0B6E5F",
            "activationBkgColor": "#CDEBE4",
            "activationBorderColor": "#0B6E5F",
        },
    },
    "scuro": {
        "theme": "base",
        "themeVariables": {
            "darkMode": True,
            "fontFamily": FONT,
            "fontSize": "15px",
            "background": "transparent",
            "primaryColor": "#13302F",
            "primaryBorderColor": "#4FD1B5",
            "primaryTextColor": "#E8ECF5",
            "secondaryColor": "#1B2236",
            "secondaryBorderColor": "#7C86A2",
            "secondaryTextColor": "#E8ECF5",
            "tertiaryColor": "#121726",
            "tertiaryBorderColor": "#38425E",
            "tertiaryTextColor": "#E8ECF5",
            "lineColor": "#9AA3B8",
            "textColor": "#E8ECF5",
            "clusterBkg": "#111625",
            "clusterBorder": "#38425E",
            "edgeLabelBackground": "#0C0F1C",
            "noteBkgColor": "#3A2F12",
            "noteBorderColor": "#E0B341",
            "noteTextColor": "#FBEFCF",
            "actorBkg": "#13302F",
            "actorBorder": "#4FD1B5",
            "actorTextColor": "#E8ECF5",
            "signalColor": "#C3CAD9",
            "signalTextColor": "#E8ECF5",
            "labelBoxBkgColor": "#13302F",
            "labelBoxBorderColor": "#4FD1B5",
            "activationBkgColor": "#1D4743",
            "activationBorderColor": "#4FD1B5",
        },
    },
}
COMMON = {
    # Testo SVG vero (niente HTML dentro l'SVG): si vede anche dove l'SVG è mostrato come immagine.
    "htmlLabels": False,
    "flowchart": {"htmlLabels": False, "curve": "basis", "padding": 14, "nodeSpacing": 40, "rankSpacing": 46},
    "sequence": {"mirrorActors": False, "useMaxWidth": True},
}
STAMP = re.compile(r"<!-- galactic-feed: (?P<source>\S+) sha256=(?P<hash>[0-9a-f]{64}) -->")


def theme_config(tone: str) -> dict:
    return {**COMMON, **THEMES[tone]}


def fingerprint(source: Path, tone: str) -> str:
    data = source.read_bytes() + json.dumps(theme_config(tone), sort_keys=True).encode()
    return hashlib.sha256(data).hexdigest()


def image_path(source: Path, tone: str) -> Path:
    return IMAGES / f"{source.stem}-{tone}.svg"


def mmdc_command() -> list[str]:
    if os.environ.get("MMDC"):
        return shlex.split(os.environ["MMDC"])
    return ["npx", "--yes", "-p", MERMAID_CLI, "mmdc"]


def up_to_date(source: Path, tone: str) -> bool:
    out = image_path(source, tone)
    if not out.exists():
        return False
    match = STAMP.search(out.read_text(encoding="utf-8")[:400])
    return bool(match) and match["hash"] == fingerprint(source, tone)


def render(everything: bool = False) -> int:
    """Disegna i diagrammi cambiati (o tutti): quelli già aggiornati restano com'erano."""
    IMAGES.mkdir(parents=True, exist_ok=True)
    sources = sorted(SOURCES.glob("*.mmd"))
    for svg in IMAGES.glob("*.svg"):
        if not any(svg == image_path(s, t) for s in sources for t in THEMES):
            svg.unlink()
            print(f"✗ {svg.relative_to(ROOT)}: tolto, non ha più il sorgente")
    with tempfile.TemporaryDirectory() as tmp:
        puppeteer = Path(tmp) / "puppeteer.json"
        args = ["--no-sandbox", "--disable-gpu"]
        settings: dict = {"args": args}
        if os.environ.get("PUPPETEER_EXECUTABLE_PATH"):
            settings["executablePath"] = os.environ["PUPPETEER_EXECUTABLE_PATH"]
        puppeteer.write_text(json.dumps(settings), encoding="utf-8")
        for source in sources:
            for tone in THEMES:
                if not everything and up_to_date(source, tone):
                    continue
                config = Path(tmp) / f"{tone}.json"
                config.write_text(json.dumps(theme_config(tone)), encoding="utf-8")
                out = image_path(source, tone)
                cmd = [*mmdc_command(), "-i", str(source), "-o", str(out), "-c", str(config), "-p", str(puppeteer), "-b", "transparent", "-q"]
                subprocess.run(cmd, check=True)
                svg = out.read_text(encoding="utf-8")
                # Id stabile (mmdc mette «my-svg»): uno per file, così più SVG nella stessa pagina non si pestano i piedi.
                svg = svg.replace("my-svg", f"gf-{source.stem}-{tone}")
                rel = source.relative_to(ROOT).as_posix()
                stamp = f"<!-- galactic-feed: {rel} sha256={fingerprint(source, tone)} -->\n"
                out.write_text(stamp + svg.lstrip(), encoding="utf-8")
                print(f"✓ {out.relative_to(ROOT)}")
    return 0


# ---------- Controlli ----------

def doc_files() -> list[Path]:
    files = [ROOT / "README.md", ROOT / "CLAUDE.md", ROOT / "CHANGELOG.md"]
    files += sorted(p for p in DOCS.rglob("*.md"))
    return [p for p in files if p.exists()]


def check_diagrams() -> list[str]:
    errors = []
    sources = sorted(SOURCES.glob("*.mmd"))
    expected = set()
    for source in sources:
        for tone in THEMES:
            out = image_path(source, tone)
            expected.add(out)
            rel = out.relative_to(ROOT)
            if not out.exists():
                errors.append(f"Manca {rel}: rigenera i diagrammi con «python3 scripts/docs.py diagrammi».")
                continue
            if not up_to_date(source, tone):
                errors.append(f"{rel} non corrisponde a {source.relative_to(ROOT)}: rigenera con «python3 scripts/docs.py diagrammi».")
    for svg in sorted(IMAGES.glob("*.svg")):
        if svg not in expected:
            errors.append(f"{svg.relative_to(ROOT)} non ha più il suo sorgente in docs/diagrammi/: toglilo.")
    return errors


ENV_PATTERNS = [
    re.compile(r"""os\.environ\.get\(\s*["']([A-Z][A-Z0-9_]+)["']"""),
    re.compile(r"""os\.environ\[\s*["']([A-Z][A-Z0-9_]+)["']\s*\]"""),
    re.compile(r"""os\.getenv\(\s*["']([A-Z][A-Z0-9_]+)["']"""),
    re.compile(r"""_env_opt_\w+\(\s*["']([A-Z][A-Z0-9_]+)["']"""),
]


def env_in_code() -> set[str]:
    names: set[str] = set()
    for path in (ROOT / "backend" / "app").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for pattern in ENV_PATTERNS:
            names.update(pattern.findall(text))
    return names


def env_in_docs() -> set[str]:
    """Le variabili nella prima colonna delle tabelle di docs/configurazione.md."""
    path = DOCS / "configurazione.md"
    if not path.exists():
        return set()
    return set(re.findall(r"^\|\s*`([A-Z][A-Z0-9_]+)`\s*\|", path.read_text(encoding="utf-8"), re.M))


def check_env() -> list[str]:
    code, docs = env_in_code(), env_in_docs()
    errors = [f"La variabile {n} è letta dal server ma non è nella tabella di docs/configurazione.md." for n in sorted(code - docs)]
    errors += [f"La variabile {n} è in docs/configurazione.md ma il server non la legge più." for n in sorted(docs - code)]
    return errors


def slugify(heading: str) -> str:
    """L'ancora che GitHub dà a un titolo."""
    text = re.sub(r"`([^`]*)`", r"\1", heading.strip())
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = text.lower()
    text = "".join(c for c in text if c in " -_" or unicodedata.category(c)[0] in "LN")
    return text.replace(" ", "-")


def anchors(path: Path) -> set[str]:
    seen: dict[str, int] = {}
    out = set()
    in_code = False
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.lstrip().startswith("```"):
            in_code = not in_code
        if in_code:
            continue
        m = re.match(r"^#{1,6}\s+(.*?)\s*#*\s*$", line)
        if not m:
            continue
        slug = slugify(m.group(1))
        n = seen.get(slug, 0)
        seen[slug] = n + 1
        out.add(slug if n == 0 else f"{slug}-{n}")
    for name in re.findall(r"""<a\s+(?:name|id)=["']([^"']+)["']""", path.read_text(encoding="utf-8")):
        out.add(name)
    return out


LINK = re.compile(r"(?<!!)\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)|!\[[^\]]*\]\(([^)\s]+)\)|(?:src|srcset|href)=\"([^\"]+)\"")


def strip_code(text: str) -> str:
    text = re.sub(r"```.*?```", "", text, flags=re.S)
    return re.sub(r"`[^`\n]*`", "", text)


def check_links() -> list[str]:
    errors = []
    for path in doc_files():
        text = strip_code(path.read_text(encoding="utf-8"))
        for m in LINK.finditer(text):
            target = next(g for g in m.groups() if g)
            if re.match(r"^[a-z][a-z0-9+.-]*:", target) or target.startswith("//"):
                continue
            file_part, _, anchor = target.partition("#")
            dest = path if not file_part else (path.parent / file_part).resolve()
            where = path.relative_to(ROOT)
            if not dest.exists():
                errors.append(f"{where}: il link «{target}» porta a un file che non c'è.")
                continue
            if anchor and dest.suffix == ".md" and anchor not in anchors(dest):
                errors.append(f"{where}: il link «{target}» porta a una sezione che non c'è.")
    return errors


# Indirizzi ammessi negli esempi: quelli riservati alla documentazione (RFC 5737), il computer
# stesso, «tutti» e le reti interne di Docker.
ALLOWED_NETS = [ipaddress.ip_network(n) for n in ("192.0.2.0/24", "198.51.100.0/24", "203.0.113.0/24", "127.0.0.0/8", "0.0.0.0/32", "172.16.0.0/12")]
IP = re.compile(r"(?<![\w.])(\d{1,3}(?:\.\d{1,3}){3})(?![\w.])")
EMAIL = re.compile(r"[\w.+-]+@([\w-]+(?:\.[\w-]+)+)")
HOME_HOST = re.compile(r"\b[\w-]+\.(?:lan|home|local|internal|localdomain|fritz\.box)\b", re.I)
EMAIL_OK = re.compile(r"(^|\.)example\.(org|com|net)$|^anthropic\.com$|^users\.noreply\.github\.com$")


def check_anonymous() -> list[str]:
    errors = []
    files = [*doc_files(), *sorted(SOURCES.glob("*.mmd")), ROOT / "docker-compose.yml"]
    for path in files:
        if path.name == "CHANGELOG.md":
            continue  # la storia delle versioni resta com'è
        where = path.relative_to(ROOT)
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for ip in IP.findall(line):
                try:
                    addr = ipaddress.ip_address(ip)
                except ValueError:
                    continue
                if not any(addr in net for net in ALLOWED_NETS):
                    errors.append(f"{where}:{n}: l'indirizzo {ip} sembra vero; negli esempi usa 192.0.2.x, 198.51.100.x o 203.0.113.x.")
            for domain in EMAIL.findall(line):
                if not EMAIL_OK.search(domain.lower()):
                    errors.append(f"{where}:{n}: un'email @{domain}; negli esempi usa nome@example.org.")
            for host in HOME_HOST.findall(line):
                errors.append(f"{where}:{n}: l'host «{host}» sembra di una rete vera; usa *.example.org.")
    return errors


BADGE = "Full Vibe Coded"


def check_badge() -> list[str]:
    errors = []
    for path in (ROOT / "README.md", DOCS / "README.md"):
        if not path.exists() or BADGE not in path.read_text(encoding="utf-8"):
            errors.append(f"{path.relative_to(ROOT)}: manca il badge «{BADGE}» (#53).")
    return errors


def check_series() -> list[str]:
    """La serie consigliata scritta nelle docs è quella di VERSION (0.10.2 → 0.10)."""
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    m = re.match(r"^(\d+)\.(\d+)\.(\d+)(-.+)?$", version)
    if not m or m.group(4):
        return []
    series = f"{m.group(1)}.{m.group(2)}"
    errors = []
    for path in [*doc_files(), ROOT / "docker-compose.yml"]:
        if path.name == "CHANGELOG.md":
            continue
        text = path.read_text(encoding="utf-8")
        where = path.relative_to(ROOT)
        for found in re.findall(r"ghcr\.io/tehmaat/galactic-feed:(\d+\.\d+)(?![\d.])", text):
            if found != series:
                errors.append(f"{where}: l'immagine usa la serie {found}, ma la versione è {version}: scrivi {series}.")
        for found in re.findall(r"`(\d+\.\d+)` \(consigliata\)", text):
            if found != series:
                errors.append(f"{where}: la serie consigliata è scritta {found}, ma la versione è {version}: scrivi {series}.")
    return errors


def check() -> list[str]:
    return [*check_diagrams(), *check_env(), *check_links(), *check_anonymous(), *check_badge(), *check_series()]


def main(argv: list[str]) -> int:
    if len(argv) in (2, 3) and argv[1] == "diagrammi" and argv[2:] in ([], ["--tutti"]):
        return render(everything=argv[2:] == ["--tutti"])
    if len(argv) == 2 and argv[1] == "check":
        errors = check()
        for e in errors:
            print("✗ " + e, file=sys.stderr)
        if not errors:
            print("✓ Documentazione in ordine: diagrammi, variabili, link, dati anonimi, badge e versione.")
        return 1 if errors else 0
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
