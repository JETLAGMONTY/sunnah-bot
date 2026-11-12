"""Prayer times from the Aladhan monthly calendar (free, no key).

One request covers a whole month for one place, so the bot asks Aladhan
about once a month per location instead of once a day per user.
"""
import datetime as dt
import re
from dataclasses import dataclass
from zoneinfo import ZoneInfo

PRAYERS = ["Fajr", "Dhuhr", "Asr", "Maghrib", "Isha"]
# The day's events in order; Sunrise marks the end of Fajr time.
TIMES = ["Fajr", "Sunrise", "Dhuhr", "Asr", "Maghrib", "Isha"]
HHMM = re.compile(r"([01][0-9]|2[0-3]):[0-5][0-9]")


class AladhanError(Exception):
    pass


@dataclass
class Day:
    date: dt.date
    times: dict     # {"Fajr": "04:42", ...} local clock times
    tz: str         # IANA zone of the location, e.g. "Europe/London"
    hijri: dict     # {"day", "month", "year", "days_in_month", "month_en", "month_ar"}
    method: str     # calculation method name, as Aladhan reports it


def calendar_request(lat, lng, year, month, method, school):
    """URL and query params for a month of times at (lat, lng).
    method=None lets Aladhan pick the authority closest to the location."""
    params = {"latitude": lat, "longitude": lng, "school": school}
    if method:
        params["method"] = method
    return f"https://api.aladhan.com/v1/calendar/{year}/{month}", params


def parse_calendar(payload):
    """{date: Day} from an Aladhan calendar response; AladhanError if unusable."""
    if not isinstance(payload, dict) or payload.get("code") != 200 or not isinstance(payload.get("data"), list):
        raise AladhanError(str((payload or {}).get("data") or "unexpected response"))
    days = {}
    try:
        for item in payload["data"]:
            times = {k: str(item["timings"][k])[:5] for k in TIMES}
            if not all(HHMM.fullmatch(v) for v in times.values()):
                raise AladhanError("malformed time")
            date = dt.datetime.strptime(item["date"]["gregorian"]["date"], "%d-%m-%Y").date()
            h = item["date"]["hijri"]
            days[date] = Day(
                date=date, times=times, tz=item["meta"]["timezone"],
                hijri={"day": int(h["day"]), "month": int(h["month"]["number"]), "year": int(h["year"]),
                       "days_in_month": int(h["month"]["days"]),
                       "month_en": h["month"]["en"], "month_ar": h["month"]["ar"]},
                method=str(item["meta"]["method"]["name"]))
    except (KeyError, TypeError, ValueError) as e:
        raise AladhanError(f"unexpected response ({type(e).__name__})") from e
    return days


def prayer_times(day, offsets=None):
    """{name: aware datetime} for Day, with the user's minute offsets.

    Near the poles in summer, Maghrib and Isha can fall after midnight: a time
    earlier than the one before it belongs to the next calendar day."""
    tz, out, shift, prev = ZoneInfo(day.tz), {}, 0, "00:00"
    for name in TIMES:
        hhmm = day.times[name]
        if hhmm < prev:
            shift += 1
        prev = hhmm
        t = dt.datetime.combine(day.date + dt.timedelta(days=shift),
                                dt.time(int(hhmm[:2]), int(hhmm[3:])), tzinfo=tz)
        out[name] = t + dt.timedelta(minutes=int((offsets or {}).get(name, 0)))
    return out
