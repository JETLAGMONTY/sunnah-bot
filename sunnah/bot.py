"""Sunnah Companion — Telegram reminder bot.

Prayer times, morning/evening adhkar, a daily hadith and Sunnah tip, and the
fasting days of the Hijri calendar, for anyone who presses START. Each person
has their own location, language, calculation method and reminders.

Run:  python -m sunnah   (or python sunnah_bot.py). Send /help in Telegram.
"""
import datetime as dt
import json
import os
import random
import re
import threading
import time
from zoneinfo import ZoneInfo

from . import content as c
from . import geocode, net, prayer, schedule, store
from .content import md, tr
from .telegram import Telegram

TICK_SECONDS = 30       # how often reminders are checked
SEND_INTERVAL = 0.05    # pause between scheduled sends (Telegram allows ~30/s)
RETRY_SECONDS = 600     # wait after a failed Aladhan/Open-Meteo lookup
MAX_MONTHS = 500        # cached prayer-time months kept in memory (a few tens of kB each)
MAX_CITY_LEN = 80

# Aladhan calculation methods (https://aladhan.com/calculation-methods).
METHODS = {
    1: "University of Islamic Sciences, Karachi", 2: "ISNA (North America)",
    3: "Muslim World League", 4: "Umm al-Qura, Makkah", 5: "Egyptian General Authority of Survey",
    7: "University of Tehran", 8: "Gulf Region", 9: "Kuwait", 10: "Qatar",
    11: "Majlis Ugama Islam Singapura", 12: "Union des Organisations Islamiques de France",
    13: "Diyanet, Turkey", 14: "Spiritual Administration of Muslims of Russia",
    15: "Moonsighting Committee Worldwide", 16: "Dubai", 17: "JAKIM, Malaysia",
    18: "Tunisia", 19: "Algeria", 20: "KEMENAG, Indonesia", 21: "Morocco",
    22: "Comunidade Islamica de Lisboa", 23: "Ministry of Awqaf, Jordan",
}
# The authority most mosques in each country follow. Countries not listed are
# left to Aladhan, which picks the closest authority to the location.
_COUNTRY_METHOD = {
    15: "GB IE", 2: "US CA", 5: "EG SD LY SY LB IQ PS", 4: "SA YE", 16: "AE", 10: "QA", 9: "KW",
    8: "BH OM", 1: "PK IN BD AF", 13: "TR", 7: "IR", 17: "MY", 20: "ID", 11: "SG", 12: "FR",
    14: "RU", 18: "TN", 19: "DZ", 21: "MA", 22: "PT", 23: "JO",
}
METHOD_BY_CC = {cc: m for m, ccs in _COUNTRY_METHOD.items() for cc in ccs.split()}
HANAFI_CC = {"PK", "IN", "BD", "AF", "TR"}   # where the Hanafi Asr is the local norm

DEFAULT_TIMES = {"morning": "07:00", "evening": "17:30", "tip": "09:00",
                 "hadith": "08:00", "friday": "09:30", "fast_eve": "20:00"}
TIME_SETTINGS = {"morning": ("MORNING_TIME", "morning_time"), "evening": ("EVENING_TIME", "evening_time"),
                 "tip": ("DAILY_TIP_TIME", "daily_tip_time"), "hadith": ("HADITH_TIME", "hadith_time"),
                 "friday": ("FRIDAY_TIME", "friday_time"), "fast_eve": ("FAST_REMIND_TIME", "fast_remind_time")}


def calc_settings(u):
    """(method, school): the user's choice, else the local norm for their country."""
    method = u.get("method") or METHOD_BY_CC.get(u.get("cc") or "")
    school = u.get("school")
    return method, (1 if u.get("cc") in HANAFI_CC else 0) if school is None else school


def parse_int(s):
    """int(s) for plain ASCII numbers like '3', '+3', '-2'; None otherwise."""
    return int(s) if re.fullmatch(r"[+-]?[0-9]{1,4}", s or "") else None


class Bot:
    def __init__(self, store_, telegram, http_get=net.get_json, now=lambda: dt.datetime.now(dt.timezone.utc),
                 lang="en", times=None, log=print, sleep=time.sleep):
        self.store, self.tg, self.http_get, self.now, self.lang = store_, telegram, http_get, now, lang
        self.times, self.log, self.sleep = times or DEFAULT_TIMES, log, sleep
        self.db = store.load_db(store_.load(), lang)
        self.dirty, self.next_tick = False, 0.0
        self.months, self.failed = {}, {}   # Aladhan month cache, and when lookups last failed
        self.rng = random.Random()

    # ---------------------------------------------------------------- users
    def user(self, chat_id):
        """The stored user, or a fresh unsaved one for a chat we haven't met."""
        return self.db["users"].get(str(chat_id)) or store.new_user(chat_id, self.lang)

    def register(self, u):
        if self.db["users"].get(str(u["chat_id"])) is not u:
            self.db["users"][str(u["chat_id"])] = u
            self.log(f"New user registered ({len(self.db['users'])} total).")
        self.save()
        return u

    def registered(self, u):
        return self.db["users"].get(str(u["chat_id"])) is u

    def save(self):
        self.dirty = True   # flush() writes once per loop turn

    def flush(self):
        if self.dirty:
            try:
                self.store.save(json.dumps(self.db, ensure_ascii=False, indent=1))
                self.dirty = False
            except store.Stale:   # another copy saved first: take its state, never overwrite it
                self.log("Another copy of the bot changed the saved state; reloading it.")
                self.db, self.dirty = store.load_db(self.store.load(), self.lang), False
            except Exception as e:
                self.log(f"Couldn't save state: {type(e).__name__}")

    def reply(self, u, text, **extra):
        if self.tg.send(u["chat_id"], text, **extra) == "blocked" and self.registered(u):
            u["blocked"] = True
            self.save()

    # ---------------------------------------------------------------- time and place
    def wall(self):
        return self.now().timestamp()

    def local_now(self, u):
        return self.now().astimezone(ZoneInfo(u.get("tz") or "UTC"))

    def day(self, u, date):
        """Aladhan's prayer.Day at the user's location, or None. Months are cached
        and shared by everyone at the same place with the same settings."""
        if u.get("lat") is None:
            return None
        method, school = calc_settings(u)
        key = (u["lat"], u["lng"], method, school, date.year, date.month)
        if key not in self.months:
            if self.wall() - self.failed.get(key, -RETRY_SECONDS) < RETRY_SECONDS:
                return None
            try:
                url, params = prayer.calendar_request(u["lat"], u["lng"], date.year, date.month, method, school)
                self.months[key] = prayer.parse_calendar(self.http_get(url, params))
            except (net.NetError, prayer.AladhanError) as e:
                # Not the URL: it holds the user's coordinates.
                self.log(f"Prayer times lookup failed: {type(e).__name__}")
                self.failed[key] = self.wall()
                return None
            old = (date.year * 12 + date.month) - 2          # keep last month onwards
            for k in [k for k in self.months if k[4] * 12 + k[5] < old]:
                del self.months[k]
            while len(self.months) > MAX_MONTHS:             # oldest first; a dropped month is fetched again
                del self.months[next(iter(self.months))]
        return self.months[key].get(date)

    def ensure_place(self, u):
        """Coordinates for a city typed into the old bot, and the location's timezone."""
        if u.get("lat") is None and u.get("city"):
            key = ("geo", u["city"], u.get("country"))
            if self.wall() - self.failed.get(key, -RETRY_SECONDS) >= RETRY_SECONDS:
                found = self.set_city(u, u["city"], u.get("country") or "")
                if not found:   # not found: don't ask again this run; search failed: retry later
                    self.failed[key] = float("inf") if found is None else self.wall()
        d = self.day(u, self.now().astimezone(dt.timezone.utc).date())
        if d and d.tz != u.get("tz"):
            u["tz"] = d.tz
            self.save()

    def set_city(self, u, name, country):
        """Look the city up and move the user there. The place, None if not found,
        or False if the search failed."""
        try:
            url, params = geocode.search_request(name, u["lang"], country)
            place = geocode.pick(self.http_get(url, params), name, country)
        except net.NetError:
            self.log("City search failed")
            return False
        if place:
            u.update(city=place["label"], country=place["country"], cc=place["cc"],
                     lat=place["lat"], lng=place["lng"], tz=place["tz"])
            self.save()
        return place

    # ---------------------------------------------------------------- prayer times message
    def times_message(self, u):
        lang = u["lang"]
        self.ensure_place(u)
        if u.get("lat") is None:
            return tr(lang, "Set your location first: /location (most accurate) or `/city Cairo, Egypt`",
                      "حدد موقعك أولًا: /location (الأدق) أو `/city Cairo, Egypt`")
        now = self.local_now(u)
        d = self.day(u, now.date())
        if not d:
            return tr(lang, "Couldn't load prayer times right now. Try again in a few minutes.",
                      "تعذّر تحميل أوقات الصلاة الآن. حاول بعد دقائق.")
        times = prayer.prayer_times(d, u.get("offsets"))
        upcoming = [n for n in prayer.PRAYERS if times[n].astimezone(dt.timezone.utc) > self.now()]
        lines = []
        for name, t in times.items():
            local = t.astimezone(now.tzinfo)
            line = f"  *{tr(lang, name, c.PRAYER_AR[name])}* — {c.clock(local.strftime('%H:%M'), lang)}"
            if local.date() > d.date:
                line += tr(lang, " (+1)", " (+١)")
            if upcoming and name == upcoming[0]:
                line += tr(lang, " ← next", " ← التالية")
            lines.append(line)
        place = md(u["city"]) if u.get("city") else tr(lang, "your location", "موقعك")
        _, school = calc_settings(u)
        msg = (tr(lang, f"🕌 *Prayer times — {place}*", f"🕌 *أوقات الصلاة — {place}*")
               + f"\n_{c.hijri_label(d.hijri, lang)}_\n\n" + "\n".join(lines)
               + tr(lang, f"\n\n_Method: {md(d.method)} · Asr: {'Hanafi' if school else 'standard'}_",
                    f"\n\n_طريقة الحساب: {md(d.method)} · العصر: {'حنفي' if school else 'الجمهور'}_"))
        if u.get("offsets"):
            msg += tr(lang, "\n_Adjusted to your mosque (/adjust)_", "\n_معدّلة حسب مسجدك (/adjust)_")
        return msg

    def times_reply(self, u, header):
        self.save()
        self.reply(u, header + "\n\n" + self.times_message(u), reply_markup={"remove_keyboard": True})

    # ---------------------------------------------------------------- commands
    def cmd_start(self, u, arg):
        self.reply(u, tr(u["lang"],
                         "Assalamu alaikum 🤍\n\nYou're registered for Sunnah reminders. For the most accurate "
                         "prayer times, share your location with /location (or type your city, e.g. "
                         "`/city Cairo, Egypt`).\n\n",
                         "السلام عليكم 🤍\n\nتم تسجيلك لتذكيرات السنة. لأدق أوقات الصلاة شارك موقعك عبر "
                         "/location (أو اكتب مدينتك، مثال: `/city Cairo, Egypt`).\n\n") + self.help_text(u))

    def help_text(self, u):
        rows = [("/location", "share your location (most accurate times)", "مشاركة موقعك (أدق الأوقات)"),
                ("/city <City, Country>", "set location by name", "تحديد المدينة بالاسم"),
                ("/times", "today's prayer times", "أوقات الصلاة اليوم"),
                ("/method", "calculation method", "طريقة الحساب"),
                ("/asr", "standard or Hanafi Asr", "العصر: الجمهور أو الحنفية"),
                ("/adjust", "match your mosque's timetable", "مطابقة جدول مسجدك"),
                ("/azkar", "morning or evening adhkar", "أذكار الصباح أو المساء"),
                ("/today", "Sunnah checklist", "قائمة السنن"),
                ("/hadith", "a hadith from Nawawi's Forty (`/hadith 16`)", "حديث من الأربعين النووية"),
                ("/friday", "the Jumu'ah Sunnah acts", "سنن يوم الجمعة"),
                ("/fasting", "recommended fasting days now", "أيام الصيام المستحبة الآن"),
                ("/dua", "a prophetic supplication", "دعاء نبوي"),
                ("/tip", "a Sunnah tip", "سنّة مختصرة"),
                ("/language", "العربية / English", "العربية / English"),
                ("/stop", "pause reminders", "إيقاف التذكيرات"),
                ("/resume", "resume reminders", "استئناف التذكيرات"),
                ("/forget", "delete your data", "حذف بياناتك"),
                ("/help", "this message", "هذه القائمة")]
        return tr(u["lang"], "*Sunnah Companion* 🤍\n\n", "*رفيق السنة* 🤍\n\n") + "\n".join(
            f"{cmd} — {tr(u['lang'], en, ar)}" for cmd, en, ar in rows)

    def cmd_help(self, u, arg):
        self.reply(u, self.help_text(u))

    def cmd_language(self, u, arg, cmd=""):
        if "ar" in arg or "عرب" in arg or cmd in ("/arabic", "/عربي", "/العربية"):
            u["lang"] = "ar"
        elif "en" in arg or cmd == "/english":
            u["lang"] = "en"
        else:
            u["lang"] = "ar" if u["lang"] == "en" else "en"
        self.save()
        self.reply(u, tr(u["lang"], "✅ Language set to English.", "✅ تم ضبط اللغة على العربية.")
                   + "\n\n" + self.help_text(u))

    def cmd_city(self, u, arg):
        lang = u["lang"]
        if not arg or len(arg) > MAX_CITY_LEN:
            return self.reply(u, tr(lang, "Send it like: `/city Cairo, Egypt`", "أرسلها هكذا: `/city Cairo, Egypt`"))
        name, country = geocode.split_query(arg)
        place = self.set_city(u, name, country)
        if place is False:
            return self.reply(u, tr(lang, "Couldn't search for cities right now. Try again in a few minutes.",
                                    "تعذّر البحث عن المدن الآن. حاول بعد دقائق."))
        if not place:
            return self.reply(u, tr(lang, f"Couldn't find *{md(arg)}*. Check the spelling or add the country, "
                                          "e.g. `/city Bristol, UK`.",
                                    f"لم أجد *{md(arg)}*. تحقق من الكتابة أو أضف الدولة، مثال: `/city Bristol, UK`."))
        hint = "" if country else tr(lang, f"\n\n_Not the right {md(name)}? Add the country, e.g. `/city {md(name)}, US`_",
                                     f"\n\n_ليست المدينة المقصودة؟ أضف الدولة، مثال: `/city {md(name)}, US`_")
        self.times_reply(u, tr(lang, f"📍 Location set to *{md(place['label'])}*.",
                               f"📍 تم تحديد الموقع: *{md(place['label'])}*.") + hint)

    def cmd_location(self, u, arg):
        self.reply(u, tr(u["lang"],
                         "📍 Tap the button below to share your location. Prayer times will be calculated for your "
                         "exact position — more accurate than a city name.\n\n_Share it again whenever you travel._",
                         "📍 اضغط الزر بالأسفل لمشاركة موقعك، لتُحسب أوقات الصلاة لموقعك بالضبط — وهذا أدق من "
                         "اسم المدينة.\n\n_أعد المشاركة كلما سافرت._"),
                   reply_markup={"keyboard": [[{"text": tr(u["lang"], "📍 Send my location", "📍 أرسل موقعي"),
                                                "request_location": True}]],
                                 "one_time_keyboard": True, "resize_keyboard": True})

    def handle_location(self, loc, chat_id):
        """A location shared from the phone: the most accurate way to set it."""
        u = self.register(self.user(chat_id))
        u["blocked"] = False
        # ~1 km precision: plenty for prayer times, and no exact address is kept.
        u.update(lat=round(float(loc["latitude"]), 2), lng=round(float(loc["longitude"]), 2),
                 city="", country="", cc="", tz=None)
        self.times_reply(u, tr(u["lang"], "📍 Got your location.", "📍 تم استلام موقعك."))

    def cmd_method(self, u, arg):
        lang, n = u["lang"], parse_int(arg)
        if n is not None and (n == 0 or n in METHODS):
            u["method"] = n or None
            name = METHODS.get(calc_settings(u)[0], tr(lang, "closest authority to you", "أقرب هيئة لموقعك"))
            return self.times_reply(u, tr(lang, f"✅ Calculation method: *{name}*", f"✅ طريقة الحساب: *{name}*"))
        current = METHODS.get(calc_settings(u)[0], tr(lang, "auto (closest authority)", "تلقائي (أقرب هيئة)"))
        listing = "\n".join(f"`{k}` — {v}" for k, v in METHODS.items())
        self.reply(u, tr(lang, f"🧭 *Calculation method* — now: *{current}*\n\nPick the one your local mosque uses, "
                               f"e.g. `/method 15`. `/method 0` = automatic for your country.\n\n{listing}",
                         f"🧭 *طريقة الحساب* — الحالية: *{current}*\n\nاختر ما يعتمده مسجدك، مثال: `/method 15`. "
                         f"`/method 0` = تلقائي حسب بلدك.\n\n{listing}"))

    def cmd_asr(self, u, arg):
        if "hanaf" in arg or "حنف" in arg:
            u["school"] = 1
        elif any(w in arg for w in ("shaf", "standard", "شاف", "جمهور")):
            u["school"] = 0
        else:
            return self.reply(u, tr(u["lang"],
                                    "Choose how Asr is calculated:\n`/asr standard` — Shafi'i, Maliki, Hanbali "
                                    "(shadow = object)\n`/asr hanafi` — Hanafi (shadow = 2× object, later)",
                                    "اختر طريقة حساب العصر:\n`/asr standard` — الجمهور (ظل الشيء مثله)\n"
                                    "`/asr hanafi` — الحنفية (ظل الشيء مثليه، وقت متأخر)"))
        self.times_reply(u, tr(u["lang"], "✅ Asr updated.", "✅ تم تحديث وقت العصر."))

    def cmd_adjust(self, u, arg):
        parts = arg.split()
        if parts == ["reset"]:
            u["offsets"] = {}
            return self.times_reply(u, tr(u["lang"], "✅ Adjustments cleared.", "✅ تم حذف التعديلات."))
        names = {p.lower(): p for p in prayer.PRAYERS}
        n = parse_int(parts[1]) if len(parts) == 2 else None
        if n is not None and parts[0] in names and abs(n) <= 60:
            offsets = {**u.get("offsets", {}), names[parts[0]]: n}
            u["offsets"] = {k: v for k, v in offsets.items() if v}
            return self.times_reply(u, tr(u["lang"], "✅ Adjusted.", "✅ تم التعديل."))
        self.reply(u, tr(u["lang"], "Match your mosque's timetable by shifting a prayer (±60 min):\n"
                                    "`/adjust maghrib +3`\n`/adjust fajr -2`\n`/adjust reset`",
                         "طابق جدول مسجدك بتعديل صلاة (±٦٠ دقيقة):\n"
                         "`/adjust maghrib +3`\n`/adjust fajr -2`\n`/adjust reset`"))

    def cmd_times(self, u, arg):
        self.reply(u, self.times_message(u))

    def cmd_today(self, u, arg):
        self.reply(u, c.checklist(u["lang"]))

    def cmd_hadith(self, u, arg):
        n = parse_int(arg)
        self.reply(u, c.hadith_message(n if n and 1 <= n <= len(c.HADITHS) else self.rng.randint(1, len(c.HADITHS)),
                                       u["lang"]))

    def cmd_azkar(self, u, arg):
        if any(w in arg for w in ("morn", "صباح")):
            kind = "morning"
        elif any(w in arg for w in ("even", "مساء")):
            kind = "evening"
        else:   # morning adhkar until Asr, evening after it
            now, d = self.local_now(u), self.day(u, self.local_now(u).date())
            kind = "evening" if (prayer.prayer_times(d)["Asr"] <= now if d else now.hour >= 15) else "morning"
        for msg in c.azkar_messages(kind, u["lang"]):
            self.reply(u, msg)

    def cmd_friday(self, u, arg):
        self.reply(u, c.friday(u["lang"]))

    def cmd_fasting(self, u, arg):
        lang = u["lang"]
        lines = [tr(lang, "🍽️ *Recommended fasting*\n", "🍽️ *الصيام المستحب*\n"),
                 tr(lang, "• *Mondays & Thursdays* — the Prophet ﷺ fasted them. (Tirmidhi)",
                    "• *الإثنين والخميس* — كان النبي ﷺ يصومهما. (الترمذي)"),
                 tr(lang, "• The *3 White Days* — 13th, 14th, 15th of each Hijri month. (Bukhari)",
                    "• *الأيام البيض* — ١٣ و١٤ و١٥ من كل شهر هجري. (البخاري)")]
        self.ensure_place(u)
        d = self.day(u, self.local_now(u).date())
        if d:
            lines.append(tr(lang, "\n_Today is ", "\n_اليوم ") + c.hijri_label(d.hijri, lang) + "._")
            occ = c.occasion_message(c.occasion_keys(d.hijri["day"], d.hijri["month"]), d.hijri, lang)
            if occ:
                lines.append("\n" + occ.split("\n\n", 1)[1])
        self.reply(u, "\n".join(lines))

    def cmd_dua(self, u, arg):
        self.reply(u, c.dua(self.rng.randrange(len(c.DUAS)), u["lang"]))

    def cmd_tip(self, u, arg):
        self.reply(u, "🌿 " + c.tip(self.rng.randrange(len(c.TIPS)), u["lang"]))

    def cmd_stop(self, u, arg):
        if not self.registered(u):
            return self.reply(u, tr(u["lang"], "You're not signed up for reminders. Send /start to begin.",
                                    "لست مشتركًا في التذكيرات. أرسل /start للبدء."))
        u["paused"] = True
        self.save()
        self.reply(u, tr(u["lang"], "Reminders paused. Send /resume anytime.",
                         "تم إيقاف التذكيرات. أرسل /resume في أي وقت."))

    def cmd_resume(self, u, arg):
        u["paused"] = False
        self.save()
        self.reply(u, tr(u["lang"], "Reminders resumed. 🤍", "تم استئناف التذكيرات. 🤍"))

    def cmd_forget(self, u, arg):
        self.db["users"].pop(str(u["chat_id"]), None)
        self.save()
        self.reply(u, tr(u["lang"], "🗑️ Done — your settings and location are deleted and reminders stopped. "
                                    "Send /start if you ever want them back.",
                         "🗑️ تم — حُذفت إعداداتك وموقعك وتوقفت التذكيرات. أرسل /start متى أردت العودة."))

    # command -> (handler, registers). Commands that change settings sign the chat up.
    COMMANDS = {
        "/start": ("cmd_start", True), "/help": ("cmd_help", False),
        "/language": ("cmd_language", True), "/lang": ("cmd_language", True), "/arabic": ("cmd_language", True),
        "/english": ("cmd_language", True), "/عربي": ("cmd_language", True), "/العربية": ("cmd_language", True),
        "/city": ("cmd_city", True), "/location": ("cmd_location", True), "/method": ("cmd_method", True),
        "/asr": ("cmd_asr", True), "/madhab": ("cmd_asr", True), "/adjust": ("cmd_adjust", True),
        "/times": ("cmd_times", False), "/today": ("cmd_today", False), "/hadith": ("cmd_hadith", False),
        "/azkar": ("cmd_azkar", False), "/adhkar": ("cmd_azkar", False), "/friday": ("cmd_friday", False),
        "/jumuah": ("cmd_friday", False), "/fasting": ("cmd_fasting", False), "/fast": ("cmd_fasting", False),
        "/dua": ("cmd_dua", False), "/tip": ("cmd_tip", False), "/stop": ("cmd_stop", False),
        "/resume": ("cmd_resume", True), "/forget": ("cmd_forget", False), "/delete": ("cmd_forget", False),
    }

    def handle(self, text, chat_id):
        text = (text or "").strip()
        if not text:
            return   # stickers, photos, etc.
        u = self.user(chat_id)
        if u.get("blocked"):
            u["blocked"] = False   # they're talking to us again
            self.save()
        head, _, arg = text.partition(" ")
        cmd = head.split("@", 1)[0].lower()   # groups send "/times@SunnahCompanionBot"
        name, registers = self.COMMANDS.get(cmd, (None, False))
        if not name:
            return self.reply(u, tr(u["lang"], "I didn't recognise that. Send /help for commands.",
                                    "لم أفهم ذلك. أرسل /help لعرض الأوامر."))
        if registers:
            self.register(u)
        arg = arg.strip()
        if name == "cmd_language":
            return self.cmd_language(u, arg.lower(), cmd)
        getattr(self, name)(u, arg if name == "cmd_city" else arg.lower())

    def process_update(self, upd):
        msg = upd.get("message") or upd.get("edited_message")
        if not msg:
            return
        chat_id = msg["chat"]["id"]
        if msg.get("location"):
            self.handle_location(msg["location"], chat_id)
        else:
            self.handle(msg.get("text", ""), chat_id)

    # ---------------------------------------------------------------- reminders
    def tick(self):
        """Send every reminder that's due, for every active user."""
        now = self.now()
        for u in list(self.db["users"].values()):
            if u.get("paused") or u.get("blocked"):
                continue
            try:
                self.ensure_place(u)
                before = list(u["sent"])
                for key, text in schedule.due(u, now, lambda d: self.day(u, d), self.times):
                    status = self.tg.send(u["chat_id"], text)
                    if status == "blocked":
                        u["blocked"] = True
                        self.save()
                        break
                    if status == "ok":   # a failed send stays unmarked and is retried next tick
                        u["sent"].append(key)
                    self.sleep(SEND_INTERVAL)
                u["sent"] = schedule.prune(u["sent"], self.local_now(u).date())
                if u["sent"] != before:
                    self.save()
            except Exception as e:
                self.log(f"Scheduler error: {type(e).__name__}: {e}")

    # ---------------------------------------------------------------- main loop
    def maybe_tick(self):
        if time.monotonic() >= self.next_tick:
            self.tick()
            self.next_tick = time.monotonic() + TICK_SECONDS

    def run_once(self):
        """Check reminders if it's time, then long-poll Telegram until the next check."""
        try:
            self.maybe_tick()
            wait = max(0, min(25, int(self.next_tick - time.monotonic())))
            updates = self.tg.get_updates(offset=self.db["last_update_id"] + 1, timeout=wait)
            if updates is None:
                self.sleep(10)   # network down or a second copy polling: back off, don't spin
                return
            for upd in updates:
                self.maybe_tick()   # a long batch of commands must not hold up everyone's reminders
                self.db["last_update_id"] = upd["update_id"]
                self.save()
                try:
                    self.process_update(upd)
                except Exception as e:   # one bad message must not stop the rest
                    self.log(f"Error handling a message: {type(e).__name__}: {e}")
        finally:
            self.flush()

    def run_forever(self):
        self.log("Listening for Telegram commands and sending reminders…")
        while True:
            try:
                self.run_once()
            except Exception as e:
                self.log(f"Loop error: {type(e).__name__}: {e}")
                self.sleep(5)


# ---------------------------------------------------------------- configuration
def load_dotenv(path, environ):
    """KEY=value lines from a local .env (git-ignored) fill variables not already set."""
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            key, sep, value = line.strip().partition("=")
            if sep and not key.lstrip().startswith("#"):
                environ.setdefault(key.strip(), value.strip().strip("'\""))


def load_config(environ, config_json):
    """Settings from environment variables first (a host's secrets), then config.json."""
    def get(env_key, json_key, default=None):
        v = environ.get(env_key) or config_json.get(json_key)
        return default if v in (None, "") else v

    token = get("BOT_TOKEN", "bot_token")
    times = {}
    for name, (env_key, json_key) in TIME_SETTINGS.items():
        times[name] = str(get(env_key, json_key, DEFAULT_TIMES[name]))
        if not re.fullmatch(r"([01][0-9]|2[0-3]):[0-5][0-9]", times[name]):
            raise SystemExit(f"{env_key} must be HH:MM (24-hour), not {times[name]!r}.")
    return {"token": None if not token or "PUT_" in token else token,
            "database_url": get("DATABASE_URL", "database_url"),
            "data_dir": get("DATA_DIR", "data_dir"),
            "lang": "ar" if str(get("LANG", "lang", "en")).lower().startswith("ar") else "en",
            "times": times}


def start_health_server(port):
    """Cloud hosts (Render, Koyeb…) set $PORT and expect HTTP answers; an uptime
    pinger hitting "/" every few minutes also stops a free instance sleeping."""
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    class Health(BaseHTTPRequestHandler):
        server_version, sys_version = "SunnahBot", ""
        timeout = 10   # drop a connection that sends nothing, so idle ones can't pile up

        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write("Sunnah Companion bot is alive 🤍".encode())

        def do_HEAD(self):   # some uptime pingers use HEAD
            self.send_response(200)
            self.end_headers()

        def log_message(self, *a):
            pass

    srv = ThreadingHTTPServer(("0.0.0.0", int(port)), Health)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def main(environ=os.environ, here=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))):
    load_dotenv(os.path.join(here, ".env"), environ)
    path = os.path.join(here, "config.json")
    config_json = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            config_json = json.load(f)
    cfg = load_config(environ, config_json)
    if not cfg["token"]:
        raise SystemExit("\n  Missing bot token.\n"
                         "  Local:  put BOT_TOKEN=<your @BotFather token> in .env (git-ignored).\n"
                         "  Cloud:  set the BOT_TOKEN environment variable / secret.\n")
    if environ.get("PORT"):
        start_health_server(environ["PORT"])
        print(f"Health server listening on :{environ['PORT']}")
        if not cfg["database_url"] and not cfg["data_dir"]:
            print("Warning: users are saved to local disk, which many cloud hosts wipe on every deploy. "
                  "Set DATABASE_URL (free Postgres, e.g. Supabase/Neon) to keep them.")
    st = store.open_store(cfg["database_url"], os.path.join(cfg["data_dir"] or here, "state.json"))
    tg = Telegram(cfg["token"])
    delay = 5
    while True:
        me = tg.get_me()
        if me.get("ok"):
            break
        if me.get("error_code") in (401, 404):
            raise SystemExit("Telegram rejected the bot token — check BOT_TOKEN.")
        print(f"Could not reach Telegram — retrying in {delay}s…")
        time.sleep(delay)
        delay = min(delay * 2, 300)
    bot = Bot(st, tg, lang=cfg["lang"], times=cfg["times"])
    print(f"Bot @{me['result']['username']} is live with {len(bot.db['users'])} user(s). Press Ctrl+C to stop.")
    bot.run_forever()
