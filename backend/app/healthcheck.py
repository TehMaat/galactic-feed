"""Controllo di salute del container: `python -m app.healthcheck`.

Lo usa l'HEALTHCHECK del Dockerfile (nell'immagine non c'è curl). Esce con 0 se il server
risponde su /api/health e il database è leggibile, con 1 altrimenti.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request


def main() -> int:
    port = os.environ.get("PORT", "8080")
    url = f"http://127.0.0.1:{port}/api/health"
    # Senza proxy: il controllo parla con il server nello stesso container.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(url, timeout=5) as res:
            ok = res.status == 200 and json.load(res).get("status") == "ok"
    except Exception as exc:  # qualsiasi errore vuol dire «non in salute»
        print(f"Galactic Feed non risponde: {exc}", file=sys.stderr)
        return 1
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
