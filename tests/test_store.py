import json

import pytest

from sunnah import store


def test_empty_store_gives_empty_db():
    assert store.load_db(None, "en") == {"last_update_id": 0, "users": {}}


def test_deployed_format_is_upgraded_and_keeps_todays_sent_reminders():
    # Shape written by the bot on origin/main (25 Sep 2026).
    old = {"last_update_id": 41, "users": {"7": {
        "chat_id": 7, "lang": "ar", "city": "", "country": "", "lat": 51.45, "lng": -2.59,
        "method": 2, "school": 0, "offsets": {"Maghrib": 3}, "tz": "Europe/London", "tz_fixed": False,
        "paused": False, "blocked": False, "sent_today": ["salah_Fajr", "morning"], "sent_date": "2026-09-01"}}}
    u = store.load_db(old, "en")["users"]["7"]
    assert u["sent"] == ["2026-09-01:salah_Fajr", "2026-09-01:morning"]
    assert "sent_today" not in u and "sent_date" not in u
    assert (u["lang"], u["lat"], u["method"], u["offsets"]) == ("ar", 51.45, 2, {"Maghrib": 3})
    assert u["cc"] == ""


def test_first_single_user_format_is_upgraded():
    db = store.load_db({"chat_id": 5, "city": "Bristol", "last_update_id": 9}, "en")
    assert db["last_update_id"] == 9
    assert db["users"]["5"]["city"] == "Bristol" and db["users"]["5"]["chat_id"] == 5
    assert db["users"]["5"]["lang"] == "en"


def test_new_users_get_the_default_language():
    assert store.new_user(3, "ar")["lang"] == "ar"


def test_file_store_round_trip(tmp_path):
    s = store.FileStore(str(tmp_path / "state.json"))
    assert s.load() is None
    s.save(json.dumps({"users": {"1": {"city": "القاهرة"}}}))
    assert s.load() == {"users": {"1": {"city": "القاهرة"}}}
    assert not (tmp_path / "state.json.tmp").exists()


class FakeConn:
    """Just enough of a psycopg connection for one-row JSON storage."""
    def __init__(self):
        self.sql, self.row, self.closed = [], None, False

    def execute(self, sql, params=None):
        self.sql.append(sql)
        if sql.startswith("INSERT"):
            self.row = params[0]
        return self

    def fetchone(self):
        return (self.row,) if self.row else None


def test_postgres_store_keeps_data_out_of_the_public_schema():
    conn = FakeConn()
    s = store.PostgresStore("postgresql://x", connect=lambda url: conn)
    assert s.load() is None
    s.save('{"users": {}}')
    assert s.load() == {"users": {}}
    assert any("CREATE SCHEMA IF NOT EXISTS sunnah_bot" in q for q in conn.sql)
    assert any("ENABLE ROW LEVEL SECURITY" in q for q in conn.sql)


def test_postgres_store_reconnects_once_after_a_dropped_connection():
    class DriverError(Exception):   # psycopg.OperationalError is not an OSError
        pass

    class Dropped(FakeConn):
        def execute(self, sql, params=None):
            raise DriverError("server closed the connection unexpectedly")

    conns = [FakeConn(), FakeConn()]
    s = store.PostgresStore("postgresql://x", connect=lambda url: conns.pop(0))
    s.conn = Dropped()
    s.save('{"users": {}}')
    assert s.load() == {"users": {}}


def test_database_errors_never_show_the_password():
    def refuse(url):
        raise OSError("connection to postgresql://postgres:s3cret@db.example.com failed")
    with pytest.raises(SystemExit) as e:
        store.open_store("postgresql://postgres:s3cret@db.example.com/postgres", "unused.json", connect=refuse)
    assert "s3cret" not in str(e.value) and "<password>" in str(e.value)


def test_without_database_url_users_live_in_a_file(tmp_path):
    assert isinstance(store.open_store("", str(tmp_path / "s.json")), store.FileStore)
