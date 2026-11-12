#!/usr/bin/env python3
"""Talk to the bot offline: no token, no network, no Telegram.

Replies come from the real bot code; prayer times and city searches come from
tests/fixtures (Bristol Sep/Dec 2026 and Feb/Mar/May/Jun 2027, Aberdeen and
Reykjavik Jun 2026, New York Sep 2026). Settings live in memory only.

  python tests/console.py --now 2026-09-04T12:00+01:00 "/city Bristol" "/times" "@2026-09-04T18:50+01:00"
  python tests/console.py --now 2027-02-27T17:00+00:00          (interactive)

Each step is a message, "loc:<lat>,<lng>" to share a location, or "@<ISO time>"
to move the clock there and run the reminder scheduler. Ctrl+C/EOF quits.
"""
import argparse
import datetime as dt
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from fakes import FakeTelegram, FixtureHTTP, MemoryStore  # noqa: E402
from sunnah.bot import Bot  # noqa: E402


class PrintingTelegram(FakeTelegram):
    def send(self, chat_id, text, **extra):
        print(f"\n[bot → {chat_id}]\n{text}")
        return super().send(chat_id, text, **extra)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--now", required=True, type=dt.datetime.fromisoformat, help="ISO time with offset")
    ap.add_argument("--chat", type=int, default=1)
    ap.add_argument("steps", nargs="*")
    args = ap.parse_args(argv)
    clock = {"now": args.now}
    bot = Bot(MemoryStore(), PrintingTelegram(), http_get=FixtureHTTP().get_json, now=lambda: clock["now"],
              log=lambda m: print(f"  (log) {m}"), sleep=lambda s: None)

    def step(s):
        print(f"\n[you] {s}")
        if s.startswith("@"):
            clock["now"] = dt.datetime.fromisoformat(s[1:])
            bot.tick()
        elif s.startswith("loc:"):
            lat, lng = map(float, s[4:].split(","))
            bot.process_update({"update_id": 0, "message": {"chat": {"id": args.chat},
                                                            "location": {"latitude": lat, "longitude": lng}}})
        else:
            bot.process_update({"update_id": 0, "message": {"chat": {"id": args.chat}, "text": s}})

    for s in args.steps:
        step(s)
    if not args.steps:
        try:
            while True:
                step(input("\n> "))
        except (EOFError, KeyboardInterrupt):
            pass


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
