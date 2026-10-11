import copy
import datetime as dt

import pytest

from conftest import fixture
from sunnah import prayer

UTC = dt.timezone.utc


def day(name, iso):
    return prayer.parse_calendar(fixture(f"aladhan/{name}"))[dt.date.fromisoformat(iso)]


def utc(*args):
    return dt.datetime(*args, tzinfo=UTC)


def test_calendar_request_has_location_method_and_school():
    url, params = prayer.calendar_request(51.45, -2.59, 2026, 9, method=2, school=0)
    assert url == "https://api.aladhan.com/v1/calendar/2026/9"
    assert params == {"latitude": 51.45, "longitude": -2.59, "method": 2, "school": 0}


def test_calendar_request_without_method_lets_aladhan_pick():
    _, params = prayer.calendar_request(30.06, 31.25, 2026, 9, method=None, school=0)
    assert "method" not in params


def test_parse_calendar_reads_every_day_of_the_month():
    days = prayer.parse_calendar(fixture("aladhan/bristol_2026_09"))
    assert len(days) == 30
    assert min(days) == dt.date(2026, 9, 1) and max(days) == dt.date(2026, 9, 30)


def test_parse_calendar_strips_zone_suffix_from_times():
    d = day("bristol_2026_09", "2026-09-01")
    assert d.times == {"Fajr": "04:42", "Sunrise": "06:23", "Dhuhr": "13:10",
                       "Asr": "16:54", "Maghrib": "19:57", "Isha": "21:37"}


def test_parse_calendar_keeps_timezone_method_and_hijri():
    d = day("bristol_2026_09", "2026-09-01")
    assert d.tz == "Europe/London"
    assert d.method == "Islamic Society of North America (ISNA)"
    assert d.hijri == {"day": 19, "month": 3, "year": 1448, "days_in_month": 29,
                       "month_en": "Rabīʿ al-awwal", "month_ar": "رَبيع الأوّل"}


def test_error_response_raises_with_aladhan_message():
    with pytest.raises(prayer.AladhanError, match="invalid"):
        prayer.parse_calendar(fixture("aladhan/error_bad_latitude"))


def test_malformed_time_raises():
    payload = copy.deepcopy(fixture("aladhan/bristol_2026_09"))
    payload["data"][3]["timings"]["Asr"] = "25:99 (BST)"
    with pytest.raises(prayer.AladhanError):
        prayer.parse_calendar(payload)


def test_times_are_local_to_the_location_in_summer_time():
    t = prayer.prayer_times(day("bristol_2026_09", "2026-09-01"))
    assert t["Fajr"].astimezone(UTC) == utc(2026, 9, 1, 3, 42)
    assert t["Isha"].astimezone(UTC) == utc(2026, 9, 1, 20, 37)


def test_clocks_going_forward_shifts_utc_by_an_hour():
    before = prayer.prayer_times(day("bristol_2027_03", "2027-03-27"))
    after = prayer.prayer_times(day("bristol_2027_03", "2027-03-28"))
    assert before["Fajr"].astimezone(UTC) == utc(2027, 3, 27, 4, 24)   # 04:24 GMT
    assert after["Fajr"].astimezone(UTC) == utc(2027, 3, 28, 4, 21)    # 05:21 BST


def test_other_timezones():
    t = prayer.prayer_times(day("newyork_2026_09", "2026-09-01"))
    assert t["Fajr"].astimezone(UTC) == utc(2026, 9, 1, 9, 4)          # 05:04 EDT


def test_late_isha_before_midnight_stays_on_the_day():
    t = prayer.prayer_times(day("aberdeen_2026_06", "2026-06-01"))
    assert t["Isha"].astimezone(UTC) == utc(2026, 6, 1, 22, 29)        # 23:29 BST


def test_maghrib_and_isha_after_midnight_belong_to_the_next_calendar_day():
    # Reykjavik, 20 June: Asr 18:22, Maghrib 00:04, Isha 00:47 (GMT = UTC)
    t = prayer.prayer_times(day("reykjavik_2026_06", "2026-06-20"))
    assert t["Asr"] == utc(2026, 6, 20, 18, 22)
    assert t["Maghrib"] == utc(2026, 6, 21, 0, 4)
    assert t["Isha"] == utc(2026, 6, 21, 0, 47)


def test_offsets_shift_single_prayers():
    t = prayer.prayer_times(day("bristol_2026_09", "2026-09-01"), {"Maghrib": 3, "Fajr": -5})
    assert t["Maghrib"].astimezone(UTC) == utc(2026, 9, 1, 19, 0)       # 19:57 + 3 BST
    assert t["Fajr"].astimezone(UTC) == utc(2026, 9, 1, 3, 37)          # 04:42 - 5 BST
    assert t["Dhuhr"].astimezone(UTC) == utc(2026, 9, 1, 12, 10)        # untouched
