import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

import pytest

from sunnah import net


class Echo(BaseHTTPRequestHandler):
    def _reply(self, status, body):
        data = body.encode() if isinstance(body, str) else json.dumps(body, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = urlsplit(self.path)
        if path.path == "/bad":
            return self._reply(400, {"code": 400, "data": "invalid coordinates"})
        if path.path == "/html":
            return self._reply(502, "<html>Bad gateway</html>")
        if path.path == "/short":   # connection drops mid-body
            self.send_response(200)
            self.send_header("Content-Length", "100")
            self.end_headers()
            self.wfile.write(b'{"partial":')
            self.close_connection = True
            return
        self._reply(200, {k: v[0] for k, v in parse_qs(path.query).items()})

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        self._reply(403 if body.get("forbid") else 200, {"got": body, "type": self.headers["Content-Type"]})

    def log_message(self, *a):
        pass


@pytest.fixture(scope="module")
def base():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), Echo)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def test_get_json_encodes_params(base):
    assert net.get_json(base + "/s", {"name": "القاهرة", "count": 10}) == {"name": "القاهرة", "count": "10"}


def test_error_status_with_json_body_returns_the_body(base):
    assert net.get_json(base + "/bad", {}) == {"code": 400, "data": "invalid coordinates"}


def test_error_status_without_json_raises(base):
    with pytest.raises(net.NetError):
        net.get_json(base + "/html", {})


def test_truncated_response_raises_net_error(base):
    with pytest.raises(net.NetError):
        net.get_json(base + "/short", {})


def test_post_json_sends_json(base):
    assert net.post_json(base + "/p", {"text": "سلام"}) == {"got": {"text": "سلام"}, "type": "application/json"}
    assert net.post_json(base + "/p", {"forbid": True})["got"] == {"forbid": True}


def test_unreachable_host_raises():
    with pytest.raises(net.NetError):
        net.get_json("http://127.0.0.1:9/", {}, timeout=2)
