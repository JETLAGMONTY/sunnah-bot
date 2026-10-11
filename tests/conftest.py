import json
import pathlib

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


def fixture(name):
    """Parsed JSON of tests/fixtures/<name>.json, e.g. fixture("aladhan/bristol_2026_09")."""
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))
