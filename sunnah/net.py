"""JSON over HTTP with the standard library only (no third-party client)."""
import http.client
import json
import urllib.error
import urllib.parse
import urllib.request

HEADERS = {"User-Agent": "SunnahCompanionBot/2", "Accept": "application/json"}


class NetError(Exception):
    pass


def _open(req, timeout):
    """Parsed JSON of any response that has a JSON body, whatever its status:
    Telegram and Aladhan explain their 4xx errors in JSON."""
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read()
    except urllib.error.HTTPError as e:
        body = e.read()
    except (OSError, ValueError, http.client.HTTPException) as e:
        raise NetError(type(e).__name__) from None   # not str(e): URLs may carry a token
    try:
        return json.loads(body)
    except ValueError:
        raise NetError("response was not JSON") from None


def get_json(url, params, timeout=30):
    query = urllib.parse.urlencode(params)
    return _open(urllib.request.Request(url + ("?" + query if query else ""), headers=HEADERS), timeout)


def post_json(url, body, timeout=30):
    data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, headers={**HEADERS, "Content-Type": "application/json"})
    return _open(req, timeout)
