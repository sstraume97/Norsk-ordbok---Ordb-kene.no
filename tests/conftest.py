import json
import sys
from pathlib import Path

TESTS_DIR = Path(__file__).parent
FIXTURES_DIR = TESTS_DIR / "fixtures"
GOLDEN_DIR = TESTS_DIR / "golden"

sys.path.insert(0, str(TESTS_DIR.parent / "scripts"))


def load_fixture(name: str) -> dict:
    """Leser en lagret ekte artikkel fra tests/fixtures/<name>.json.

    Fixturene er ekte data lastet ned fra ord.uib.no (CC-BY 4.0,
    UiB/Språkrådet) - se den enkelte testen for hvilken artikkel-id og
    ord det gjelder."""
    return json.loads((FIXTURES_DIR / f"{name}.json").read_text(encoding="utf-8"))
