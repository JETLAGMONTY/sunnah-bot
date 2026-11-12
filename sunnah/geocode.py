"""City search via Open-Meteo's free geocoder (no key).

A typed city becomes coordinates + timezone once, when it's set, so prayer
times are always looked up by position, never by a fuzzy name."""
import re

URL = "https://geocoding-api.open-meteo.com/v1/search"
ARABIC = re.compile(r"[؀-ۿ]")
# Common names people type that aren't ISO codes. Any 2-letter hint is taken as a code.
ALIASES = {
    "uk": "GB", "united kingdom": "GB", "england": "GB", "scotland": "GB", "wales": "GB",
    "northern ireland": "GB", "britain": "GB", "great britain": "GB",
    "usa": "US", "america": "US", "united states": "US", "united states of america": "US",
    "uae": "AE", "ksa": "SA",
}


def split_query(text):
    """'Cairo, Egypt' -> ('Cairo', 'Egypt')."""
    city, _, country = text.partition(",")
    return city.strip(), country.strip()


def country_code(hint):
    h = hint.strip().casefold()
    return ALIASES.get(h) or (h.upper() if re.fullmatch(r"[a-z]{2}", h) else None)


def search_request(name, lang, country):
    params = {"name": name, "count": 10, "language": "ar" if ARABIC.search(name) else lang, "format": "json"}
    if country_code(country):
        params["countryCode"] = country_code(country)
    return URL, params


def pick(payload, name, country):
    """Best place for `name` (optionally in `country`), or None."""
    results = payload.get("results") or []
    if country:
        code, c = country_code(country), country.casefold()
        results = [r for r in results if r.get("country_code") == code or str(r.get("country", "")).casefold() == c]
    exact = [r for r in results if str(r.get("name", "")).casefold() == name.casefold()]
    if not (exact or results):
        return None
    r = (exact or results)[0]
    label = [r["name"]] + [r[k] for k in ("admin1", "country") if r.get(k) and r[k] != r["name"]]
    return {"name": r["name"], "label": ", ".join(label), "country": r.get("country", ""),
            "cc": r.get("country_code", ""), "lat": round(r["latitude"], 2), "lng": round(r["longitude"], 2),
            "tz": r.get("timezone")}
