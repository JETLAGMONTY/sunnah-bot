# Sunnah Companion — Telegram bot

Reliable push reminders that reach your phone **even when nothing is open**:
prayer times, morning & evening adhkar, and a daily Sunnah tip.

**Anyone can use it.** Share your bot's link (`t.me/<your_bot_username>`) —
everyone who presses START gets their own location, language, calculation
method and reminders, in their own time zone.

## One-time setup (about 5 minutes)

1. **Create the bot**
   - Open Telegram, search for **@BotFather**, press Start.
   - Send `/newbot`, choose a name and a username (must end in `bot`).
   - BotFather replies with a **token** like `123456:ABC-DEF...`. Copy it.

2. **Add the token**
   - In this `bot` folder, copy `.env.example` to `.env` and put your token after
     `BOT_TOKEN=`. (`.env` is git-ignored. A `config.json` copied from
     `config.example.json` also still works.)

3. **Run it**
   - **Windows:** double-click **`run-bot.bat`** (it installs the requirements and starts the bot).
   - **Or any OS:**
     ```
     pip install -r requirements.txt
     python sunnah_bot.py        (or: python -m sunnah)
     ```

4. **Activate reminders**
   - Open your new bot in Telegram and press **START**.
   - Send `/location` and tap **📍 Send my location** (most accurate), or type your
     city: `/city Cairo, Egypt`
   - Done — you'll now get reminders. Test with `/times`, `/today`, `/dua`.

## Commands

| Command | What it does |
|---|---|
| `/start` | Sign up for reminders |
| `/location` | Share your phone's location: the most accurate prayer times |
| `/city <City, Country>` | Set location by name instead |
| `/times` | Today's prayer times (shows the method used) |
| `/method [n]` | See or choose the calculation method (`/method 0` = automatic) |
| `/asr standard` / `/asr hanafi` | How Asr is calculated |
| `/adjust <prayer> <±min>` | Match your mosque's timetable, e.g. `/adjust maghrib +3` |
| `/azkar` | The full morning or evening adhkar (`/azkar evening`) |
| `/today` | The full Sunnah checklist |
| `/hadith [n]` | A hadith from Nawawi's Forty, or number n (1–42) |
| `/friday` | The Jumu'ah Sunnah acts |
| `/fasting` | Recommended fasting days (incl. today's occasion) |
| `/dua` | A prophetic supplication |
| `/tip` | A random Sunnah tip |
| `/language` | Switch between العربية and English (or `/language ar`) |
| `/stop` / `/resume` | Pause / resume reminders |
| `/forget` | Delete your settings and location, and stop reminders |
| `/help` | List commands |

The bot speaks **Arabic or English** — every reminder, hadith, and command reply is
translated. Switch anytime with `/language`, or set the default with the `LANG` env var
(`en` / `ar`).

### Automatic reminders

- **Every prayer time** + **morning/evening adhkar** + a **daily Sunnah tip**
- **Hadith of the day** (08:00) — cycles through all 42 of Nawawi's Forty
- **Jumu'ah pack** every Friday (09:30) — Al-Kahf, ghusl, salawat, last-hour du'a
- **Last hour before Maghrib on Friday** — du'a reminder
- **Occasions of the Hijri calendar** (08:00) — the White Days, Ashura, the first ten
  days of Dhul Hijjah, Arafah, Eid, the days of Tashreeq (not for fasting), Ramadan
- **Fasting nudges** (evening) — Mon/Thu, the 3 White Days, Ashura, Arafah, the eve of
  Ramadan and of Eid al-Fitr (Zakat al-Fitr). None during Ramadan, on Eid or Tashreeq.
- **Odd nights of the last ten** of Ramadan — a Laylat al-Qadr reminder at Maghrib

A reminder is sent at its time, or up to 10 minutes late if the bot was
restarting; after that it's skipped rather than sent stale.

## Keeping it running 24/7

The bot only sends reminders while the script is running. Options:

- **Your PC** — easiest. Reminders arrive whenever your PC is on. (Add `run-bot.bat`
  to Windows Startup so it launches with your computer:
  press `Win+R`, type `shell:startup`, drop a shortcut to `run-bot.bat` there.)
- **A Raspberry Pi** at home — runs silently 24/7 for ~nothing.
- **A free/cheap cloud host** (Render, Railway, Fly.io, a small VPS) — always on,
  independent of your PC. See [DEPLOY.md](DEPLOY.md).

### Where users are saved

Everyone's settings are saved in `state.json` next to the script (or in
`DATA_DIR`). Many free cloud hosts, including Render, **wipe the disk on every
deploy**, which would sign everyone out. On those hosts set `DATABASE_URL` to a
free Postgres database (e.g. [Supabase](https://supabase.com) or
[Neon](https://neon.tech)) and the bot keeps its data there instead.

## Notes

- `config.json` holds your bot token and `state.json` holds users' settings —
  **don't share or commit them** (both are git-ignored).
- **Privacy:** each person only ever sees their own settings. Shared locations
  are stored rounded to about 1 km, nothing else about users is kept, and
  `/forget` deletes a person's data. Logs never include users' cities, locations
  or messages.
- Reminders use **each person's local time**, detected automatically from the
  prayer-times API — so a cloud host running on UTC still reminds everyone on time.
- **Tests:** `pip install -r requirements-dev.txt`, then `python -m pytest`. They
  run against recorded API replies in `tests/fixtures/` — no network, no token.
- **Try it offline:** `python tests/console.py --now 2026-09-04T12:00+01:00 "/city Bristol" "/times" "@2026-09-04T18:50+01:00"`
  talks to the real bot code with fixture data (`@<time>` moves the clock and runs
  the reminders). Run it without steps for an interactive prompt.
- Prayer times come from the free [Aladhan API](https://aladhan.com/prayer-times-api),
  one monthly calendar per place, shared by everyone there. Typed cities are
  looked up once with the free [Open-Meteo geocoder](https://open-meteo.com/en/docs/geocoding-api).
  **For the most accurate times:**
  1. Share your location with `/location` (exact coordinates beat a city name).
  2. The bot picks the authority your country's mosques follow (e.g. Moonsighting
     Committee for the UK, Umm al-Qura for Saudi Arabia, Egyptian Authority for
     Egypt, Karachi + Hanafi Asr for Pakistan/India). Change it with `/method`.
  3. Choose `/asr hanafi` if you follow the Hanafi madhab.
  4. Compare with your local mosque's timetable and fine-tune with `/adjust`
     (mosques often add a few minutes, e.g. to Maghrib or Dhuhr).
- The reminders are aids to worship — always learn the details of each act of the
  Sunnah from the Qur'an, authentic hadith, and trustworthy scholars.

## Licence

Copyright © 2026 Ayman Ahmed. All rights reserved.

This code is public so it can be **read and evaluated**, not reused. You're
welcome to look through it and to quote it with attribution; copying, modifying,
redistributing or building on it needs written permission. See [LICENSE](LICENSE).

The supplications and hadith are well-known texts of the Islamic tradition and
are not claimed as original work — the selection, arrangement and surrounding
software are.
