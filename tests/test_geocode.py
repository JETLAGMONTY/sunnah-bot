from conftest import fixture
from sunnah import geocode

URL = "https://geocoding-api.open-meteo.com/v1/search"


def test_split_query_separates_city_and_country():
    assert geocode.split_query("  Cairo ,  Egypt ") == ("Cairo", "Egypt")
    assert geocode.split_query("Bristol") == ("Bristol", "")


def test_search_request_plain_name():
    assert geocode.search_request("Bristol", "en", "") == (
        URL, {"name": "Bristol", "count": 10, "language": "en", "format": "json"})


def test_search_request_maps_country_aliases_to_iso_codes():
    assert geocode.search_request("Bristol", "en", "UK")[1]["countryCode"] == "GB"
    assert geocode.search_request("Bristol", "en", "usa")[1]["countryCode"] == "US"
    assert geocode.search_request("Paris", "en", "fr")[1]["countryCode"] == "FR"


def test_search_request_leaves_full_country_names_to_filtering():
    assert "countryCode" not in geocode.search_request("Cairo", "en", "Egypt")[1]


def test_arabic_query_searches_in_arabic():
    assert geocode.search_request("القاهرة", "en", "")[1]["language"] == "ar"


def test_pick_takes_the_top_match_and_rounds_coordinates():
    assert geocode.pick(fixture("openmeteo/bristol"), "Bristol", "") == {
        "name": "Bristol", "label": "Bristol, England, United Kingdom", "country": "United Kingdom",
        "cc": "GB", "lat": 51.46, "lng": -2.6, "tz": "Europe/London"}


def test_pick_prefers_exact_name_within_a_country():
    # 'Independence, Missouri' is the first US result for "Bristol"; it must not win.
    place = geocode.pick(fixture("openmeteo/bristol"), "Bristol", "USA")
    assert (place["label"], place["tz"]) == ("Bristol, Virginia, United States", "America/New_York")


def test_pick_matches_country_alias_against_country_code():
    assert geocode.pick(fixture("openmeteo/bristol_uk"), "Bristol", "UK")["lat"] == 51.46


def test_pick_arabic_results():
    place = geocode.pick(fixture("openmeteo/cairo_ar"), "القاهرة", "")
    assert (place["label"], place["cc"], place["tz"]) == ("القاهرة, مصر", "EG", "Africa/Cairo")


def test_pick_filters_by_country_name():
    assert geocode.pick(fixture("openmeteo/cairo_ar"), "القاهرة", "اليمن")["cc"] == "YE"


def test_pick_returns_none_without_results():
    assert geocode.pick(fixture("openmeteo/nomatch"), "Xyzzy", "") is None
    assert geocode.pick(fixture("openmeteo/bristol"), "Bristol", "Narnia") is None
