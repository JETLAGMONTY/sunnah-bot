import datetime as dt
from zoneinfo import ZoneInfo

import pytest

from fakes import FakeTelegram, FixtureHTTP, MemoryStore
from sunnah import bot as botmod
from sunnah.bot import Bot

LONDON = ZoneInfo("Europe/London")
ALADHAN = "https://api.aladhan.com/v1/calendar/"
GEOCODE = "https://geocoding-api.open-meteo.com/"


class Env:
    """A bot wired to fixtures, a recording Telegram and a settable clock."""

    def __init__(self, when=dt.datetime(2026, 9, 1, 12, 0, tzinfo=LONDON), data=None):
        self.when, self.tg, self.http, self.store, self.logs = when, FakeTelegram(), FixtureHTTP(), MemoryStore(data), []
        self.bot = Bot(self.store, self.tg, http_get=self.http.get_json, now=lambda: self.when,
                       log=self.logs.append, sleep=lambda s: None)

    def say(self, text, chat=1):
        self.bot.process_update({"update_id": 1, "message": {"chat": {"id": chat}, "text": text}})
        return self.tg.last()

    def share(self, lat, lng, chat=1):
        self.bot.process_update({"update_id": 1, "message": {"chat": {"id": chat},
                                                              "location": {"latitude": lat, "longitude": lng}}})
        return self.tg.last()

    def user(self, chat=1):
        return self.bot.db["users"].get(str(chat))


@pytest.fixture
def env():
    return Env()


@pytest.fixture
def bristol(env):
    env.say("/city Bristol")
    env.tg.sent.clear()
    return env


# --- signing up --------------------------------------------------------------

def test_start_registers_and_explains(env):
    reply = env.say("/start")
    assert env.user() is not None and "/location" in reply


def test_reading_content_does_not_register(env):
    for cmd in ("/hadith", "/tip", "/today", "/dua", "/friday", "/help", "/times", "/azkar", "/fasting"):
        env.say(cmd)
    assert env.user() is None


def test_users_have_separate_settings(env):
    env.say("/city Bristol", chat=1)
    env.say("/language ar", chat=2)
    assert env.user(1)["lang"] == "en" and env.user(2)["lang"] == "ar"
    assert "Bristol" not in env.say("/times", chat=2)


def test_stop_needs_a_sign_up(env):
    assert "/start" in env.say("/stop")
    assert env.user() is None


def test_stop_and_resume(env):
    env.say("/start")
    env.say("/stop")
    assert env.user()["paused"]
    env.say("/resume")
    assert not env.user()["paused"]


def test_forget_deletes_the_user(bristol):
    bristol.say("/forget")
    assert bristol.user() is None


def test_message_from_a_blocked_user_unblocks_them(bristol):
    bristol.user()["blocked"] = True
    bristol.say("/times")
    assert not bristol.user()["blocked"]


def test_language_explicit_and_toggle(env):
    env.say("/language ar")
    assert env.user()["lang"] == "ar"
    env.say("/language")
    assert env.user()["lang"] == "en"
    env.say("/arabic")
    assert env.user()["lang"] == "ar"


# --- parsing ------------------------------------------------------------------

def test_group_command_with_bot_username(bristol):
    assert "Fajr" in bristol.say("/times@SunnahCompanionBot")


def test_non_text_messages_are_ignored(env):
    env.bot.process_update({"update_id": 1, "message": {"chat": {"id": 1}, "sticker": {}}})
    assert env.tg.sent == []


def test_unknown_command(env):
    assert "/help" in env.say("/blah")


# --- location -----------------------------------------------------------------

def test_city_sets_coordinates_timezone_and_country(env):
    reply = env.say("/city Bristol")
    u = env.user()
    assert (u["lat"], u["lng"], u["tz"], u["cc"]) == (51.46, -2.6, "Europe/London", "GB")
    assert "Bristol, England, United Kingdom" in reply and "4:42 AM" in reply   # Fajr, 1 Sep


def test_city_with_country(env):
    env.say("/city Bristol, USA")
    assert env.user()["tz"] == "America/New_York"


def test_city_in_arabic(env):
    env.say("/language ar")
    env.say("/city القاهرة")
    assert env.user()["cc"] == "EG" and env.user()["tz"] == "Africa/Cairo"


def test_unknown_city_keeps_the_old_location(bristol):
    reply = bristol.say("/city Xyzzy")
    assert "Xyzzy" in reply and bristol.user()["lat"] == 51.46


def test_city_needs_a_name(env):
    assert "/city Cairo, Egypt" in env.say("/city")
    assert "/city Cairo, Egypt" in env.say("/city " + "x" * 81)


def test_city_reply_escapes_markdown(env):
    assert "Xy\\_zzy" in env.say("/city Xy_zzy")


def test_shared_location_is_rounded_and_takes_the_timezone_from_aladhan(env):
    reply = env.share(51.454512, -2.587911)
    u = env.user()
    assert (u["lat"], u["lng"], u["tz"]) == (51.45, -2.59, "Europe/London")
    assert "Fajr" in reply


def test_times_without_location_asks_for_one(env):
    assert "/location" in env.say("/times")


def test_times_marks_the_next_prayer(bristol):
    reply = bristol.say("/times")                                   # 12:00 BST, Dhuhr 13:10
    assert "*Dhuhr* — 1:10 PM ←" in reply and "*Fajr* — 4:42 AM\n" in reply


def test_times_show_the_hijri_date(bristol):
    assert "19 Rabīʿ al-awwal 1448 AH" in bristol.say("/times")


def test_times_after_midnight_are_marked(env):
    env.when = dt.datetime(2026, 6, 20, 12, 0, tzinfo=dt.timezone.utc)
    env.share(64.1466, -21.9426)                                    # Reykjavik
    reply = env.say("/times")
    assert "*Maghrib* — 12:04 AM (+1)" in reply


def test_times_in_arabic(bristol):
    bristol.say("/language ar")
    assert "الظهر" in bristol.say("/times")


def test_one_aladhan_request_per_place_per_month(env):
    env.say("/city Bristol", chat=1)
    env.say("/city Bristol", chat=2)
    env.say("/times", chat=1)
    assert env.http.count(ALADHAN) == 1


def test_failed_fetch_is_not_retried_for_ten_minutes(env):
    env.when = dt.datetime(2026, 10, 1, 12, 0, tzinfo=LONDON)       # no fixture for October
    assert "Couldn't load" in env.say("/city Bristol")
    env.say("/times")
    assert env.http.count(ALADHAN) == 1
    env.when += dt.timedelta(minutes=11)
    env.say("/times")
    assert env.http.count(ALADHAN) == 2


# --- calculation settings ---------------------------------------------------------

def test_uk_defaults_to_moonsighting_committee(bristol):
    _, params = bristol.http.calls[-1]
    assert params["method"] == 15 and params["school"] == 0


def test_pakistan_defaults_to_karachi_and_hanafi(env):
    u = env.bot.register(env.bot.user(1))
    u.update(cc="PK")
    assert botmod.calc_settings(u) == (1, 1)


def test_unknown_country_lets_aladhan_pick(env):
    assert botmod.calc_settings(env.bot.user(1)) == (None, 0)


def test_method_choice(bristol):
    bristol.say("/method 2")
    assert bristol.user()["method"] == 2
    assert "ISNA" in bristol.tg.last()
    bristol.say("/method 0")
    assert bristol.user()["method"] is None
    assert "`15`" in bristol.say("/method 99")                     # unknown: show the list


def test_asr_school(bristol):
    bristol.say("/asr hanafi")
    assert bristol.user()["school"] == 1
    bristol.say("/asr standard")
    assert bristol.user()["school"] == 0


def test_adjust(bristol):
    bristol.say("/adjust maghrib +3")
    assert bristol.user()["offsets"] == {"Maghrib": 3}
    bristol.say("/adjust fajr 90")                                  # beyond ±60: rejected
    assert bristol.user()["offsets"] == {"Maghrib": 3}
    bristol.say("/adjust reset")
    assert bristol.user()["offsets"] == {}


# --- content commands ---------------------------------------------------------------

def test_hadith_by_number(env):
    assert "angry" in env.say("/hadith 16")


def test_azkar_sends_every_part(env):
    env.say("/azkar evening")
    assert len(env.tg.sent) >= 2 and "Evening adhkar" in env.tg.sent[0][1]


def test_azkar_picks_morning_before_asr(bristol):
    bristol.say("/azkar")                                           # 12:00, Asr 16:54
    assert "Morning adhkar" in bristol.tg.sent[0][1]


def test_fasting_shows_todays_hijri_date(bristol):
    assert "19 Rabīʿ al-awwal 1448 AH" in bristol.say("/fasting")


# --- reminders --------------------------------------------------------------------

def test_tick_sends_a_due_reminder_once(bristol):
    bristol.when = dt.datetime(2026, 9, 1, 13, 10, tzinfo=LONDON)
    bristol.bot.tick()
    bristol.bot.tick()
    assert len(bristol.tg.sent) == 1 and "Dhuhr" in bristol.tg.last()


def test_failed_send_is_retried_next_tick(bristol):
    bristol.when = dt.datetime(2026, 9, 1, 13, 10, tzinfo=LONDON)
    bristol.tg.status = lambda c: "failed"
    bristol.bot.tick()
    bristol.tg.status = lambda c: "ok"
    bristol.bot.tick()
    assert len(bristol.tg.sent) == 2 and bristol.user()["sent"] == ["2026-09-01:salah_Dhuhr"]


def test_blocked_user_is_marked_and_skipped(bristol):
    bristol.when = dt.datetime(2026, 9, 1, 13, 10, tzinfo=LONDON)
    bristol.tg.status = lambda c: "blocked"
    bristol.bot.tick()
    bristol.bot.tick()
    assert bristol.user()["blocked"] and len(bristol.tg.sent) == 1


def test_paused_users_get_nothing(bristol):
    bristol.say("/stop")
    bristol.tg.sent.clear()
    bristol.when = dt.datetime(2026, 9, 1, 13, 10, tzinfo=LONDON)
    bristol.bot.tick()
    assert bristol.tg.sent == []


def test_tick_serves_every_user_in_their_language(env):
    env.say("/city Bristol", chat=1)
    env.say("/language ar", chat=2)
    env.say("/city Bristol", chat=2)
    env.tg.sent.clear()
    env.when = dt.datetime(2026, 9, 1, 13, 10, tzinfo=LONDON)
    env.bot.tick()
    assert "Dhuhr" in env.tg.texts(1)[0] and "الظهر" in env.tg.texts(2)[0]


def test_users_from_the_deployed_bot_keep_working():
    # A user who typed a city on origin/main has no coordinates yet.
    data = {"last_update_id": 3, "users": {"9": {
        "chat_id": 9, "lang": "en", "city": "Bristol", "country": "UK", "lat": None, "lng": None,
        "method": 2, "school": 0, "offsets": {}, "tz": "Europe/London", "tz_fixed": False,
        "paused": False, "blocked": False, "sent_today": [], "sent_date": "2026-09-01"}}}
    e = Env(when=dt.datetime(2026, 9, 1, 13, 10, tzinfo=LONDON), data=data)
    e.bot.tick()
    assert e.user(9)["lat"] == 51.46 and e.user(9)["cc"] == "GB"
    assert "Dhuhr" in e.tg.texts(9)[0]


def test_quiet_tick_does_not_write_the_store(bristol):
    bristol.bot.tick()
    bristol.bot.flush()
    saves = bristol.store.saves
    bristol.bot.tick()                                              # 12:00: nothing due
    bristol.bot.flush()
    assert bristol.store.saves == saves


LEGACY = {"chat_id": 9, "lang": "en", "city": "Bristol", "country": "UK", "lat": None, "lng": None,
          "method": 2, "school": 0, "offsets": {}, "tz": "Europe/London", "tz_fixed": False,
          "paused": False, "blocked": False, "sent_today": [], "sent_date": "2026-09-04"}


def test_paused_legacy_user_still_gets_times():
    e = Env(data={"last_update_id": 0, "users": {"9": {**LEGACY, "paused": True}}})
    assert "Fajr" in e.say("/times", chat=9)
    assert "Rabīʿ al-awwal" in e.say("/fasting", chat=9)


def test_unknown_legacy_city_is_looked_up_once():
    e = Env(data={"last_update_id": 0, "users": {"9": {**LEGACY, "city": "Xyzzy", "country": ""}}})
    e.bot.tick()
    e.when += dt.timedelta(minutes=11)
    e.bot.tick()
    assert e.http.count(GEOCODE) == 1


def test_reminders_sent_by_the_old_bot_are_not_repeated_after_deploy():
    # origin/main called the Friday last-hour reminder "friday_dua".
    e = Env(when=dt.datetime(2026, 9, 4, 18, 52, tzinfo=LONDON),
            data={"last_update_id": 0, "users": {"9": {**LEGACY, "lat": 51.46, "lng": -2.6,
                                                         "sent_today": ["friday_dua"]}}})
    e.bot.tick()
    assert e.tg.sent == []


def test_old_sent_keys_are_pruned(bristol):
    bristol.user()["sent"] = ["2026-08-01:morning"]
    bristol.bot.tick()
    assert bristol.user()["sent"] == []


# --- the loop -----------------------------------------------------------------------

def test_run_once_answers_updates_and_saves(bristol):
    bristol.tg.updates = [{"update_id": 7, "message": {"chat": {"id": 1}, "text": "/tip"}}]
    bristol.bot.run_once()
    assert bristol.store.data["last_update_id"] == 7
    assert bristol.store.data["users"]["1"]["lat"] == 51.46


def test_one_bad_update_does_not_stop_the_rest(bristol):
    bristol.tg.updates = [{"update_id": 7, "message": {"chat": "not-a-dict", "text": "/tip"}},
                          {"update_id": 8, "message": {"chat": {"id": 1}, "text": "/tip"}}]
    bristol.bot.run_once()
    assert bristol.store.data["last_update_id"] == 8 and len(bristol.tg.sent) == 1


# --- configuration --------------------------------------------------------------------

def test_env_beats_config_json():
    assert botmod.load_config({"BOT_TOKEN": "1:A"}, {"bot_token": "2:B"})["token"] == "1:A"
    assert botmod.load_config({}, {"bot_token": "2:B"})["token"] == "2:B"


def test_placeholder_token_counts_as_missing():
    assert botmod.load_config({}, {"bot_token": "PUT_YOUR_BOTFATHER_TOKEN_HERE"})["token"] is None


def test_default_language_from_lang():
    assert botmod.load_config({"LANG": "ar_EG.UTF-8"}, {})["lang"] == "ar"
    assert botmod.load_config({"LANG": "C.UTF-8"}, {})["lang"] == "en"


def test_reminder_times_from_env_and_validated():
    assert botmod.load_config({"MORNING_TIME": "06:30"}, {})["times"]["morning"] == "06:30"
    with pytest.raises(SystemExit, match="MORNING_TIME"):
        botmod.load_config({"MORNING_TIME": "7am"}, {})


def test_dotenv_fills_missing_variables_only(tmp_path):
    p = tmp_path / ".env"
    p.write_text('# secrets\nBOT_TOKEN="9:X"\n\nCITY = Bristol\nLANG=ar\n', encoding="utf-8")
    environ = {"LANG": "en"}
    botmod.load_dotenv(str(p), environ)
    assert environ == {"BOT_TOKEN": "9:X", "CITY": "Bristol", "LANG": "en"}


def test_main_without_token_explains(tmp_path):
    with pytest.raises(SystemExit, match="BOT_TOKEN"):
        botmod.main({}, str(tmp_path))


def test_health_server_answers():
    import urllib.request
    srv = botmod.start_health_server(0)
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{srv.server_address[1]}/") as r:
            assert r.status == 200
    finally:
        srv.shutdown()
