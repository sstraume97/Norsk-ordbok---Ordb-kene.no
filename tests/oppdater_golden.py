#!/usr/bin/env python3
"""
Regenererer tests/golden/*.html fra gjeldende kode i scripts/. Kjør
denne når en formatteringsendring i ordbok_parser.py/
ordbok_til_stardict.py er tilsiktet:

    python3 tests/oppdater_golden.py
    git diff tests/golden/    # se over at endringen er som forventet
    git add tests/golden/ && git commit ...

Fixturene i tests/fixtures/ er ekte artikler fra ord.uib.no (CC-BY 4.0,
UiB/Språkrådet).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from conftest import GOLDEN_DIR, load_fixture  # noqa: E402
from ordbok_parser import parse_article  # noqa: E402
from ordbok_til_stardict import _render_definition  # noqa: E402

FIXTURES = ["trollmann", "haar", "fin", "stor", "skaar", "slaa", "haap", "jamfore", "han", "gjerne", "denne"]


def main() -> None:
    GOLDEN_DIR.mkdir(exist_ok=True)
    for name in FIXTURES:
        art = parse_article(load_fixture(name))
        html = _render_definition(art, {})
        (GOLDEN_DIR / f"{name}.html").write_text(html, encoding="utf-8")
        print(f"skrev golden/{name}.html")


if __name__ == "__main__":
    main()
