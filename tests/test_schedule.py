import datetime as dt
from zoneinfo import ZoneInfo

from conftest import fixture
from sunnah import prayer, schedule

LONDON = ZoneInfo("Europe/London")
UTC = dt.timezone.utc
TIMES = {"morning": "07:00", "evening": "17:30", "tip": "09:00",
         "hadith": "08:00", "friday": "09:30", "fast_eve": "20:00"}


def calendar(*names):
    days = {}
    for n in names:
        days.update(prayer.parse_calendar(fixture(f"aladhan/{n}")))
    return days.get


def user(**kw):
    return {"lang": "en", "tz": "Europe/London", "offsets": {}, "sent": [], **kw}


def due(u, now, days=calendar("bristol_2026_09")):
    return dict(schedule.due(u, now, days, TIMES))


def london(*args):
    return dt.datetime(*args, tzinfo=LONDON)


def test_prayer_reminder_at_its_time():
    out = due(user(), london(2026, 9, 1, 13, 10))
    assert list(out) == ["2026-09-01:salah_Dhuhr"]
    assert "Dhuhr" in out["2026-09-01:salah_Dhuhr"] and "1:10 PM" in out["2026-09-01:salah_Dhuhr"]


def test_late_reminders_are_sent_within_ten_minutes_then_dropped():
    assert list(due(user(), london(2026, 9, 1, 13, 19, 59))) == ["2026-09-01:salah_Dhuhr"]
    assert due(user(), london(2026, 9, 1, 13, 20)) == {}


def test_nothing_is_due_between_events():
    assert due(user(), london(2026, 9, 1, 13, 9)) == {}


def test_sent_reminders_are_not_repeated():
    assert due(user(sent=["2026-09-01:salah_Dhuhr"]), london(2026, 9, 1, 13, 11)) == {}


def test_fixed_time_reminders():
    assert list(due(user(), london(2026, 9, 1, 7, 0))) == ["2026-09-01:morning"]
    assert list(due(user(), london(2026, 9, 1, 9, 0))) == ["2026-09-01:tip"]
    assert list(due(user(), london(2026, 9, 1, 17, 30))) == ["2026-09-01:evening"]


def test_tip_of_the_day_is_whole():
    text = due(user(), london(2026, 9, 1, 9, 0))["2026-09-01:tip"]
    assert any(text.endswith(en) for en, _ in schedule.c.TIPS)


def test_hadith_alone_on_an_ordinary_day():
    assert list(due(user(), london(2026, 9, 1, 8, 0))) == ["2026-09-01:hadith"]   # 19 Rabi I


def test_white_day_occasion_with_the_hadith():
    out = due(user(), london(2026, 9, 24, 8, 0))                                    # 13 Rabi II
    assert list(out) == ["2026-09-24:hadith", "2026-09-24:occasion"]
    assert "White Day" in out["2026-09-24:occasion"]


def test_eve_of_thursday_and_white_day():
    out = due(user(), london(2026, 9, 23, 20, 0))
    assert "Thursday" in out["2026-09-23:fast_eve"] and "White Day" in out["2026-09-23:fast_eve"]


def test_eve_of_monday():
    assert "Monday" in due(user(), london(2026, 9, 6, 20, 0))["2026-09-06:fast_eve"]


def test_no_fasting_nudge_before_an_ordinary_day():
    assert "2026-09-01:fast_eve" not in due(user(), london(2026, 9, 1, 20, 0))   # tomorrow: Wed, 21 Rabi I


def test_eid_eve_uses_the_real_next_hijri_date():
    # 29 Ramadan 1448 is the last day: tomorrow is 1 Shawwal, not "30 Ramadan".
    out = due(user(), london(2027, 3, 8, 20, 0), calendar("bristol_2027_03"))
    assert "Eid al-Fitr is expected tomorrow" in out["2027-03-08:fast_eve"]


def test_ramadan_eve_replaces_the_monday_nudge():
    out = due(user(), london(2027, 2, 7, 20, 0), calendar("bristol_2027_02"))
    assert "Ramadan is expected to begin tomorrow" in out["2027-02-07:fast_eve"]
    assert "Monday" not in out["2027-02-07:fast_eve"]


def test_odd_night_reminder_at_maghrib():
    out = due(user(), london(2027, 2, 27, 17, 47), calendar("bristol_2027_02"))     # 20 Ramadan
    assert list(out) == ["2027-02-27:salah_Maghrib", "2027-02-27:qadr"]
    assert "21st night" in out["2027-02-27:qadr"]


def test_friday_reminders():
    assert list(due(user(), london(2026, 9, 4, 9, 30))) == ["2026-09-04:jumuah"]
    assert list(due(user(), london(2026, 9, 4, 18, 50))) == ["2026-09-04:friday_dua"]   # Maghrib 19:50


def test_isha_after_midnight_belongs_to_the_previous_day():
    u = user(tz="Atlantic/Reykjavik")
    days = calendar("reykjavik_2026_06")
    assert list(due(u, dt.datetime(2026, 6, 21, 0, 4, tzinfo=UTC), days)) == ["2026-06-20:salah_Maghrib"]
    assert list(due(u, dt.datetime(2026, 6, 21, 0, 47, tzinfo=UTC), days)) == ["2026-06-20:salah_Isha"]


def test_first_morning_of_summer_time():
    days = calendar("bristol_2027_03")
    assert list(due(user(), dt.datetime(2027, 3, 28, 4, 21, tzinfo=UTC), days)) == ["2027-03-28:salah_Fajr"]
    assert due(user(), dt.datetime(2027, 3, 28, 5, 21, tzinfo=UTC), days) == {}


def test_mosque_offsets_move_the_reminder_and_its_time():
    u = user(offsets={"Maghrib": 3})
    assert due(u, london(2026, 9, 1, 19, 57)) == {}
    assert "8:00 PM" in due(u, london(2026, 9, 1, 20, 0))["2026-09-01:salah_Maghrib"]


def test_without_location_only_fixed_reminders_run_on_utc():
    u = user(tz=None)
    assert list(due(u, dt.datetime(2026, 9, 1, 7, 0, tzinfo=UTC), lambda d: None)) == ["2026-09-01:morning"]


def test_arabic_user_gets_arabic():
    assert "الظهر" in due(user(lang="ar"), london(2026, 9, 1, 13, 10))["2026-09-01:salah_Dhuhr"]


def test_prune_keeps_yesterday_and_today():
    sent = ["2026-08-30:a", "2026-08-31:b", "2026-09-01:c"]
    assert schedule.prune(sent, dt.date(2026, 9, 1)) == ["2026-08-31:b", "2026-09-01:c"]
