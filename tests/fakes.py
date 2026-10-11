"""Test doubles: the recorded API fixtures served like the real APIs, and a
Telegram that records instead of sending. Also used by tests/console.py."""
import datetime as dt
import json
import pathlib
import re

from sunnah import geocode
from sunnah.net import NetError

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


def _load(path):
    return json.loads(path.read_text(encoding="utf-8"))


class FixtureHTTP:
    """get_json() for Aladhan's calendar and Open-Meteo's search, from tests/fixtures.

    Aladhan: the month's fixture recorded nearest the coordinates (within 0.5°);
    a month or place with no fixture behaves like a network failure."""

    def __init__(self):
        self.calls = []
        self.months = []   # (year, month, lat, lng, path)
        for p in (FIXTURES / "aladhan").glob("*_20*.json"):
            first = _load(p)["data"][0]
            day = dt.datetime.strptime(first["date"]["gregorian"]["date"], "%d-%m-%Y")
            self.months.append((day.year, day.month, first["meta"]["latitude"], first["meta"]["longitude"], p))

    def get_json(self, url, params, timeout=30):
        self.calls.append((url, dict(params)))
        if url == geocode.URL:
            name = params["name"].casefold()
            if name == "bristol":
                return _load(FIXTURES / "openmeteo" / ("bristol_uk.json" if params.get("countryCode") == "GB" else "bristol.json"))
            if name == "القاهرة":
                return _load(FIXTURES / "openmeteo" / "cairo_ar.json")
            return _load(FIXTURES / "openmeteo" / "nomatch.json")
        m = re.fullmatch(r"https://api\.aladhan\.com/v1/calendar/(\d+)/(\d+)", url)
        if m:
            lat, lng = float(params["latitude"]), float(params["longitude"])
            if abs(lat) > 90:
                return _load(FIXTURES / "aladhan" / "error_bad_latitude.json")
            for y, mo, flat, flng, path in self.months:
                if (y, mo) == (int(m[1]), int(m[2])) and abs(flat - lat) < 0.5 and abs(flng - lng) < 0.5:
                    return _load(path)
        raise NetError("no fixture for this request")

    def count(self, prefix):
        return sum(url.startswith(prefix) for url, _ in self.calls)


class FakeTelegram:
    """Records sent messages. status(chat_id) decides what send() returns."""

    def __init__(self):
        self.sent, self.updates, self.status = [], [], lambda chat_id: "ok"

    def send(self, chat_id, text, **extra):
        self.sent.append((chat_id, text, extra))
        return self.status(chat_id)

    def get_updates(self, offset, timeout):
        out, self.updates = [u for u in self.updates if u["update_id"] >= offset], []
        return out

    def texts(self, chat_id=None):
        return [t for c, t, _ in self.sent if chat_id is None or c == chat_id]

    def last(self):
        return self.sent[-1][1]


class MemoryStore:
    def __init__(self, data=None):
        self.data, self.saves = data, 0

    def load(self):
        return self.data

    def save(self, text):
        self.data, self.saves = json.loads(text), self.saves + 1
