"""Which reminders are due for one user right now. Pure: no I/O, no clock.

Every reminder is an event at an exact instant, keyed "YYYY-MM-DD:name" by the
local date it belongs to. An event is due from its time until GRACE later, so
a restart or a slow tick still delivers it, but a stale one is dropped."""
import datetime as dt
from zoneinfo import ZoneInfo

from . import content as c
from .prayer import PRAYERS, prayer_times

GRACE = dt.timedelta(minutes=10)


def _at(date, hhmm, tz):
    return dt.datetime.combine(date, dt.time(int(hhmm[:2]), int(hhmm[3:5])), tzinfo=tz)


def events(u, date, days, times):
    """[(name, instant, text)] for local `date`. days(date) -> prayer.Day or None."""
    lang, tz = u["lang"], ZoneInfo(u.get("tz") or "UTC")
    today, tomorrow = days(date), days(date + dt.timedelta(days=1))
    out = [("morning", _at(date, times["morning"], tz), c.morning_reminder(lang)),
           ("hadith", _at(date, times["hadith"], tz), c.hadith_message(c.hadith_of_day(date), lang)),
           ("tip", _at(date, times["tip"], tz),
            c.tr(lang, "🌿 *Sunnah of the day*\n\n", "🌿 *سنّة اليوم*\n\n") + c.tip(date.toordinal(), lang)),
           ("evening", _at(date, times["evening"], tz), c.evening_reminder(lang))]
    if today:
        h = today.hijri
        out.append(("occasion", _at(date, times["hadith"], tz),
                    c.occasion_message(c.occasion_keys(h["day"], h["month"]), h, lang)))
    th = tomorrow.hijri if tomorrow else {}
    out.append(("fast_eve", _at(date, times["fast_eve"], tz),
                c.fast_eve_message(c.fast_eve_keys((date.weekday() + 1) % 7, th.get("day"), th.get("month")), th, lang)))
    friday = date.weekday() == 4
    if friday:
        out.append(("jumuah", _at(date, times["friday"], tz), c.jumuah_reminder(lang)))
    if today:
        t = prayer_times(today, u.get("offsets"))
        for name in PRAYERS:
            out.append(("salah_" + name, t[name], c.salah_reminder(name, t[name].astimezone(tz).strftime("%H:%M"), lang)))
        if friday:
            out.append(("friday_dua", t["Maghrib"] - dt.timedelta(hours=1), c.friday_hour(lang)))
        night = c.qadr_night(today.hijri["day"], today.hijri["month"])
        if night:
            out.append(("qadr", t["Maghrib"], c.qadr_message(night, lang)))
    return [e for e in out if e[2]]


def due(u, now, days, times):
    """[(key, text)] of reminders due at `now` (aware) and not yet sent."""
    tz = ZoneInfo(u.get("tz") or "UTC")
    today = now.astimezone(tz).date()
    now = now.astimezone(dt.timezone.utc)
    out = []
    for date in (today - dt.timedelta(days=1), today):   # yesterday: Isha can fall after midnight
        for name, at, text in events(u, date, days, times):
            key = f"{date.isoformat()}:{name}"
            if key not in u["sent"] and at <= now < at + GRACE:
                out.append((key, text))
    return out


def prune(sent, today):
    """Keep only keys from yesterday on, so the list can't grow forever."""
    keep = (today - dt.timedelta(days=1)).isoformat()
    return [k for k in sent if k[:10] >= keep]
