"""Storage. Every user's settings live in one JSON document: state.json by
default, or one Postgres row when DATABASE_URL is set. Use Postgres (e.g. a
free Supabase or Neon database) on hosts like Render whose disk is wiped on
every deploy, or everyone's settings are lost with it."""
import copy
import json
import os
from urllib.parse import urlsplit

USER_DEFAULTS = {
    "chat_id": None,
    "lang": "en",
    "city": "", "country": "", "cc": "",   # city = display label; cc = ISO country code
    "lat": None, "lng": None,               # rounded to ~1 km
    "method": None,                         # Aladhan method id; None = pick by country
    "school": None,                         # 0 = standard Asr, 1 = Hanafi; None = pick by country
    "offsets": {},                          # {"Maghrib": 3, ...} minutes, to match a mosque
    "tz": None,
    "paused": False,
    "blocked": False,                       # blocked the bot; cleared when they write again
    "sent": [],                             # "YYYY-MM-DD:name" keys of delivered reminders
}


class Stale(Exception):
    """Another copy of the bot has written the state since this one last read it."""


def new_user(chat_id, lang):
    return {**copy.deepcopy(USER_DEFAULTS), "chat_id": chat_id, "lang": lang}


def load_db(data, lang):
    """Normalise stored data, upgrading every earlier format."""
    data = data or {}
    if "users" not in data:   # the first, single-user state.json
        old, data = data, {"last_update_id": data.get("last_update_id", 0), "users": {}}
        if old.get("chat_id"):
            data["users"][str(old["chat_id"])] = {k: old[k] for k in USER_DEFAULTS if k in old}
    data.setdefault("last_update_id", 0)
    for cid, u in data["users"].items():
        if "sent_today" in u:   # origin/main kept one day's names plus its date
            u["sent"] = [f"{u.get('sent_date', '')}:{k}" for k in u.pop("sent_today")]
            u.pop("sent_date", None)
        for k, v in new_user(None, lang).items():
            u.setdefault(k, v)
        if u["chat_id"] is None:
            u["chat_id"] = int(cid) if cid.lstrip("-").isdigit() else cid
    return data


class FileStore:
    def __init__(self, path):
        self.path, self.last = path, None   # last = the text this copy last read or wrote

    def _read(self):
        if not os.path.exists(self.path):
            return None
        with open(self.path, encoding="utf-8") as f:
            return f.read()

    def load(self):
        self.last = self._read()
        return None if self.last is None else json.loads(self.last)

    def save(self, text):
        if self._read() != self.last:   # never write an older copy over someone else's changes
            raise Stale
        # Write a temp file and rename, so a crash mid-write never truncates the state.
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, self.path)
        self.last = text


class PostgresStore:
    def __init__(self, url, connect):
        self.url, self.connect, self.conn, self.last = url, connect, None, None
        # Its own schema, not `public`: Supabase publishes `public` tables through its
        # REST API, and this row holds users' locations. RLS with no policies also blocks
        # the API roles if the schema is ever exposed; the bot owns the table, so RLS
        # doesn't restrict it.
        self._run("CREATE SCHEMA IF NOT EXISTS sunnah_bot")
        self._run("CREATE TABLE IF NOT EXISTS sunnah_bot.state (id int PRIMARY KEY, data text NOT NULL)")
        self._run("ALTER TABLE sunnah_bot.state ENABLE ROW LEVEL SECURITY")

    def _run(self, sql, params=None):
        for attempt in (1, 2):   # reconnect once if the connection dropped
            try:
                if self.conn is None or self.conn.closed:
                    self.conn = self.connect(self.url)
                return self.conn.execute(sql, params)
            except Exception:   # the driver's own errors (psycopg.OperationalError) aren't OSError
                self.conn = None
                if attempt == 2:
                    raise

    def load(self):
        row = self._run("SELECT data FROM sunnah_bot.state WHERE id = 1").fetchone()
        self.last = row[0] if row else None
        return json.loads(row[0]) if row else None

    def save(self, text):
        # Only replace the row this copy last saw: a second copy of the bot (a redeploy
        # overlap, or one started by hand) must not write its older data over a /forget.
        cur = (self._run("INSERT INTO sunnah_bot.state (id, data) VALUES (1, %s) ON CONFLICT (id) DO NOTHING", (text,))
               if self.last is None else
               self._run("UPDATE sunnah_bot.state SET data = %s WHERE id = 1 AND data = %s", (text, self.last)))
        if cur.rowcount == 0:
            raise Stale
        self.last = text


def ssl_args(url, environ=os.environ):
    """Refuse an unencrypted database connection unless the operator chose an sslmode.
    `require` encrypts; add sslmode=verify-full to the URL to also check the server's certificate."""
    return {} if "sslmode=" in url or environ.get("PGSSLMODE") else {"sslmode": "require"}


def _psycopg_connect(url):
    import psycopg   # only needed when DATABASE_URL is set
    return psycopg.connect(url, autocommit=True, **ssl_args(url))


def open_store(database_url, path, connect=_psycopg_connect):
    if not database_url:
        return FileStore(path)
    try:
        return PostgresStore(database_url, connect)
    except Exception as e:
        secret = urlsplit(database_url).password or "\0"
        raise SystemExit("Could not connect to the database in DATABASE_URL: "
                         + str(e).replace(secret, "<password>"))
