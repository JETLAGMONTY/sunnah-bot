from sunnah import telegram
from sunnah.net import NetError

TOKEN = "123:TEST-not-a-real-token"


class Fake:
    """Telegram's HTTP API, answering with the queued replies in order."""
    def __init__(self, *replies):
        self.replies, self.calls, self.slept, self.logs = list(replies), [], [], []

    def post(self, url, body, timeout):
        self.calls.append((url, body, timeout))
        r = self.replies.pop(0)
        if isinstance(r, Exception):
            raise r
        return r

    def client(self):
        return telegram.Telegram(TOKEN, post=self.post, sleep=self.slept.append, log=self.logs.append)


def test_send_posts_markdown_message():
    f = Fake({"ok": True})
    assert f.client().send(42, "*hi*") == "ok"
    url, body, _ = f.calls[0]
    assert url == f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    assert body == {"chat_id": 42, "text": "*hi*", "parse_mode": "Markdown", "disable_web_page_preview": True}


def test_send_passes_extra_fields():
    f = Fake({"ok": True})
    f.client().send(42, "hi", reply_markup={"remove_keyboard": True})
    assert f.calls[0][1]["reply_markup"] == {"remove_keyboard": True}


def test_markdown_error_resends_as_plain_text():
    f = Fake({"ok": False, "error_code": 400, "description": "Bad Request: can't parse entities"}, {"ok": True})
    assert f.client().send(42, "*broken") == "ok"
    assert "parse_mode" not in f.calls[1][1]


def test_rate_limit_waits_as_told_then_retries():
    f = Fake({"ok": False, "error_code": 429, "parameters": {"retry_after": 3}}, {"ok": True})
    assert f.client().send(42, "hi") == "ok"
    assert f.slept == [3] and len(f.calls) == 2


def test_blocked_by_user():
    f = Fake({"ok": False, "error_code": 403, "description": "Forbidden: bot was blocked by the user"})
    assert f.client().send(42, "hi") == "blocked"


def test_other_failures_are_logged():
    f = Fake({"ok": False, "error_code": 400, "description": "Bad Request: chat not found"})
    assert f.client().send(42, "hi") == "failed"
    assert any("chat not found" in line for line in f.logs)


def test_network_errors_never_log_the_token():
    f = Fake(NetError(f"failed https://api.telegram.org/bot{TOKEN}/sendMessage"))
    assert f.client().send(42, "hi") == "failed"
    assert f.logs and not any(TOKEN in line for line in f.logs)


def test_get_updates_long_polls():
    f = Fake({"ok": True, "result": [{"update_id": 5}]})
    assert f.client().get_updates(offset=5, timeout=25) == [{"update_id": 5}]
    url, body, timeout = f.calls[0]
    assert url.endswith("/getUpdates")
    assert body == {"offset": 5, "timeout": 25, "allowed_updates": ["message", "edited_message"]}
    assert timeout > 25   # the HTTP timeout must outlast the long poll


def test_get_updates_failure_returns_none():
    f = Fake({"ok": False, "error_code": 409, "description": "Conflict: terminated by other getUpdates request"})
    assert f.client().get_updates(offset=0, timeout=0) is None
    assert any("Conflict" in line for line in f.logs)
