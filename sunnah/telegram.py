"""Thin client for the Telegram Bot API (long polling, no webhook)."""
import time

from . import net

API = "https://api.telegram.org/bot{token}/{method}"


class Telegram:
    def __init__(self, token, post=net.post_json, sleep=time.sleep, log=print):
        self.token, self.post, self.sleep, self.log = token, post, sleep, log

    def call(self, method, params, http_timeout=30):
        """Telegram's JSON reply, or {} if it couldn't be reached."""
        try:
            return self.post(API.format(token=self.token, method=method), params, http_timeout)
        except Exception as e:
            # The request URL contains the token; keep it out of the logs.
            self.log(f"Telegram {method} error: " + str(e).replace(self.token, "<token>"))
            return {}

    def send(self, chat_id, text, **extra):
        """'ok', 'blocked' (the user blocked the bot or left the group) or 'failed'."""
        params = dict(chat_id=chat_id, text=text, parse_mode="Markdown", disable_web_page_preview=True, **extra)
        res = self.call("sendMessage", params)
        if res.get("error_code") == 429:   # too many requests: wait as told, once
            self.sleep(min(int((res.get("parameters") or {}).get("retry_after", 1)), 30))
            res = self.call("sendMessage", params)
        # Telegram rejects the whole message if its Markdown doesn't parse; send it plain instead.
        if res.get("error_code") == 400 and "parse" in str(res.get("description", "")).lower():
            params.pop("parse_mode")
            res = self.call("sendMessage", params)
        if res.get("ok"):
            return "ok"
        if res.get("error_code") == 403:
            return "blocked"
        if res:
            self.log(f"Send failed: {res.get('description')}")
        return "failed"

    def get_updates(self, offset, timeout):
        """New updates (long-polling up to `timeout` s), or None on failure."""
        res = self.call("getUpdates", {"offset": offset, "timeout": timeout,
                                       "allowed_updates": ["message", "edited_message"]},
                        http_timeout=timeout + 30)   # must outlast the long poll
        if not res.get("ok"):
            # Network down, or 409: another copy of the bot is polling with the same token.
            self.log(f"getUpdates failed: {res.get('description', 'no response')}")
            return None
        return res.get("result", [])

    def get_me(self):
        return self.call("getMe", {})
