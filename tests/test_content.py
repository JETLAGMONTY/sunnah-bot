import datetime as dt
import re

import pytest

from sunnah import content

LATIN = re.compile(r"[A-Za-z]")
DHUL_HIJJAH, MUHARRAM, RAMADAN, SHAWWAL, RABI2 = 12, 1, 9, 10, 4


def test_tr_picks_language():
    assert content.tr("en", "hi", "مرحبا") == "hi"
    assert content.tr("ar", "hi", "مرحبا") == "مرحبا"


def test_md_escapes_legacy_markdown():
    assert content.md("a_b*c`d[e") == "a\\_b\\*c\\`d\\[e"


@pytest.mark.parametrize("day,month,want", [
    (12, RABI2, []),
    (13, RABI2, ["white"]), (14, RABI2, ["white"]), (15, RABI2, ["white"]),
    (16, RABI2, []),
    (13, RAMADAN, ["ramadan"]),                    # fasting is already obligatory
    (9, MUHARRAM, ["ashura"]), (10, MUHARRAM, ["ashura"]), (11, MUHARRAM, []),
    (1, DHUL_HIJJAH, ["dhul_hijjah_10"]), (8, DHUL_HIJJAH, ["dhul_hijjah_10"]),
    (9, DHUL_HIJJAH, ["dhul_hijjah_10", "arafah"]),
    (10, DHUL_HIJJAH, ["eid_adha"]),
    (11, DHUL_HIJJAH, ["tashreeq"]),
    (13, DHUL_HIJJAH, ["tashreeq"]),              # a day of Tashreeq, never a white-day fast
    (14, DHUL_HIJJAH, ["white"]),
    (1, SHAWWAL, ["eid_fitr"]),
    (2, SHAWWAL, ["shawwal6"]), (7, SHAWWAL, ["shawwal6"]), (8, SHAWWAL, []),
])
def test_occasions_of_the_hijri_calendar(day, month, want):
    assert content.occasion_keys(day, month) == want


@pytest.mark.parametrize("weekday,hday,hmonth,want", [
    (0, 5, RABI2, ["monday"]),
    (3, 5, RABI2, ["thursday"]),
    (2, 5, RABI2, []),
    (0, None, None, ["monday"]),                  # Hijri date unknown: weekdays still work
    (2, 13, RABI2, ["white"]),
    (3, 14, RABI2, ["thursday", "white"]),
    (3, 9, DHUL_HIJJAH, ["thursday", "arafah"]),
    (3, 13, DHUL_HIJJAH, []),                     # Tashreeq on a Thursday: don't fast
    (0, 10, DHUL_HIJJAH, []),                     # Eid on a Monday: don't fast
    (0, 1, RAMADAN, ["ramadan_start"]),
    (3, 14, RAMADAN, []),                         # mid-Ramadan: no voluntary-fast nudges
    (0, 1, SHAWWAL, ["eid_fitr_eve"]),
    (2, 10, MUHARRAM, ["ashura"]),
])
def test_what_to_plan_for_tomorrow(weekday, hday, hmonth, want):
    assert content.fast_eve_keys(weekday, hday, hmonth) == want


@pytest.mark.parametrize("day,month,night", [
    (20, RAMADAN, 21), (22, RAMADAN, 23), (28, RAMADAN, 29),
    (21, RAMADAN, None), (18, RAMADAN, None), (20, SHAWWAL, None),
])
def test_odd_nights_of_the_last_ten(day, month, night):
    # The Islamic night begins at Maghrib, so the 21st night is the evening of the 20th day.
    assert content.qadr_night(day, month) == night


def test_clock_is_12_hour():
    assert content.clock("21:37", "en") == "9:37 PM"
    assert content.clock("00:28", "en") == "12:28 AM"
    assert content.clock("12:05", "ar") == "12:05 م"


def all_ar_messages():
    hijri = {"day": 9, "month": DHUL_HIJJAH, "year": 1448, "month_ar": "ذوالحجة", "month_en": "Dhū al-Ḥijjah"}
    yield content.occasion_message(list(content.OCCASIONS), hijri, "ar")
    yield content.fast_eve_message(list(content.FAST_EVE), hijri, "ar")
    yield content.qadr_message(21, "ar")
    yield content.morning_reminder("ar")
    yield content.evening_reminder("ar")
    yield content.jumuah_reminder("ar")
    yield content.friday_hour("ar")
    yield from (content.salah_reminder(p, "21:37", "ar") for p in ("Fajr", "Dhuhr", "Asr", "Maghrib", "Isha"))
    yield content.checklist("ar")
    yield content.friday("ar")
    yield from (content.tip(i, "ar") for i in range(len(content.TIPS)))
    yield from (content.dua(i, "ar") for i in range(len(content.DUAS)))
    yield from (content.hadith_message(n, "ar") for n in range(1, 43))
    yield from content.azkar_messages("morning", "ar") + content.azkar_messages("evening", "ar")


def test_arabic_content_has_no_latin_text():
    for text in all_ar_messages():
        text = re.sub(r"/[a-z_]+", "", text)   # Telegram commands are Latin by necessity
        assert not LATIN.search(text), text[:200]


def test_occasion_message_is_none_without_occasions():
    assert content.occasion_message([], {}, "en") is None
    assert content.fast_eve_message([], {}, "en") is None


def test_hadith_of_the_day_cycles_through_all_42():
    start = dt.date(2026, 9, 1)
    assert {content.hadith_of_day(start + dt.timedelta(days=k)) for k in range(42)} == set(range(1, 43))


def test_hadith_message_has_text_and_number():
    msg = content.hadith_message(16, "en")
    assert "16" in msg and "angry" in msg


def test_every_message_fits_telegram_limit():
    for n in range(1, 43):
        for lang in ("en", "ar"):
            assert len(content.hadith_message(n, lang)) <= content.LIMIT
    for kind in ("morning", "evening"):
        for lang in ("en", "ar"):
            assert all(len(m) <= content.LIMIT for m in content.azkar_messages(kind, lang))


def test_azkar_covers_every_dhikr_with_its_count():
    joined = "\n".join(content.azkar_messages("morning", "en"))
    for z in content.AZKAR["morning"]:
        assert content.md(z["ar"]) in joined
    assert "×100" in joined and "×3" in joined


def test_azkar_transliteration_has_no_markdown_inside_italics():
    # Legacy Markdown can't escape inside _italics_; the data writes ʿayn as a backtick.
    joined = "\n".join(content.azkar_messages("morning", "en"))
    assert "_Alḥamdulillahi waḥdah waṣ-ṣalatu was-salam ʿalā man lā nabiyya baʿdah._" in joined


def test_azkar_in_arabic_drops_transliteration_and_translation():
    joined = "\n".join(content.azkar_messages("evening", "ar"))
    assert content.AZKAR["evening"][0]["en"] not in joined
