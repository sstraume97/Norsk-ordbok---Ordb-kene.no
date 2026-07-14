"""
Golden-snapshot-tester: renderer hele StarDict-definisjonen for et
utvalg ekte artikler og sammenligner mot lagrede referanseutdata i
tests/golden/. Disse fanger opp ENHVER endring i sluttresultatet -
tilsiktet eller ikke - i motsetning til test_parser.py, som tester
spesifikke, navngitte detaljer og er lettere å forstå når den feiler.

Hvis en endring i formatteringen er tilsiktet:
    python3 tests/oppdater_golden.py
    git diff tests/golden/    # se over at endringen er som forventet
"""

import pytest
from conftest import GOLDEN_DIR, load_fixture
from ordbok_parser import parse_article
from ordbok_til_stardict import _render_definition

FIXTURES = ["trollmann", "haar", "fin", "stor", "skaar", "slaa", "haap", "jamfore"]


@pytest.mark.parametrize("name", FIXTURES)
def test_golden(name):
    art = parse_article(load_fixture(name))
    actual = _render_definition(art, {})
    expected = (GOLDEN_DIR / f"{name}.html").read_text(encoding="utf-8")
    assert actual == expected
