"""Live weather via Open-Meteo (no key, stdlib only; coordinator-approved, D50).

Two fixed hosts; only the city name is sent, URL-encoded. Responses are untrusted
(§12.2): only numbers and the matched city/country are read, never raw text.
Open-Meteo's free API is for non-commercial use.

APIs (verified live 2026-09-14):
- https://open-meteo.com/en/docs/geocoding-api
- https://open-meteo.com/en/docs (current, daily, WMO weather codes)
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request

from strands import tool

from zoya.config import WEATHER_TIMEOUT_S
from zoya.tools import ToolError

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
GEOCODING_CANDIDATES = 5
MAX_CITY_CHARS = 80
MAX_RESPONSE_BYTES = 200_000

# Open-Meteo's geocoder only knows current names: "Bangalore" alone matches a Karachi suburb.
# ponytail: a handful of renamed Indian cities; add more when a user hits one.
CITY_ALIASES = {
    "bangalore": "Bengaluru",
    "bombay": "Mumbai",
    "madras": "Chennai",
    "calcutta": "Kolkata",
    "gurgaon": "Gurugram",
    "poona": "Pune",
}

WMO_CODES = {
    0: "clear skies",
    1: "mainly clear",
    2: "partly cloudy",
    3: "overcast",
    45: "fog",
    48: "fog",
    51: "light drizzle",
    53: "drizzle",
    55: "heavy drizzle",
    61: "light rain",
    63: "rain",
    65: "heavy rain",
    80: "rain showers",
    81: "rain showers",
    82: "heavy rain showers",
    95: "thunderstorms",
    96: "thunderstorms with hail",
    99: "thunderstorms with hail",
}


class CityNotFound(Exception):
    pass


def _get_json(url: str, params: dict[str, str | int | float]) -> dict:
    request = urllib.request.Request(f"{url}?{urllib.parse.urlencode(params)}")
    with urllib.request.urlopen(request, timeout=WEATHER_TIMEOUT_S) as response:  # noqa: S310
        return json.loads(response.read(MAX_RESPONSE_BYTES))


def _number(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError("not a number")
    return float(value)


def _find_city(city: str) -> tuple[str, str, float, float]:
    name = CITY_ALIASES.get(city.lower(), city)
    results = (
        _get_json(
            GEOCODING_URL, {"name": name, "count": GEOCODING_CANDIDATES, "language": "en"}
        ).get("results")
        or []
    )
    if not results:
        raise CityNotFound(city)
    best = max(results, key=lambda r: r.get("population") or 0)
    return (
        str(best.get("name", name))[:MAX_CITY_CHARS],
        str(best.get("country", ""))[:MAX_CITY_CHARS],
        _number(best["latitude"]),
        _number(best["longitude"]),
    )


@tool
def get_weather(city: str) -> str:
    """Get today's live weather for a city: current temperature, conditions, high/low, rain chance.

    Args:
        city: City name, e.g. "Bengaluru" or "Delhi".
    """
    city = " ".join(city.split())[:MAX_CITY_CHARS]
    if not city:
        raise ToolError("Which city should I check the weather for?")
    try:
        name, country, latitude, longitude = _find_city(city)
        data = _get_json(
            FORECAST_URL,
            {
                "latitude": latitude,
                "longitude": longitude,
                "current": "temperature_2m,weather_code",
                "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max",
                "timezone": "auto",
                "forecast_days": 1,
            },
        )
        now = _number(data["current"]["temperature_2m"])
        code = int(_number(data["current"]["weather_code"]))
        high = _number(data["daily"]["temperature_2m_max"][0])
        low = _number(data["daily"]["temperature_2m_min"][0])
        rain = _number(data["daily"]["precipitation_probability_max"][0])
    except CityNotFound as error:
        raise ToolError(f"I couldn't find a city called {city}.") from error
    except (urllib.error.URLError, TimeoutError, ValueError, KeyError, IndexError, TypeError) as e:
        raise ToolError(f"I couldn't get the weather for {city} right now.") from e
    conditions = WMO_CODES.get(code, "mixed weather")
    place = f"{name}, {country}" if country else name
    return (
        f"{place}: {round(now)} degrees and {conditions} now. Today's high is {round(high)}, "
        f"low {round(low)}, with a {round(rain)} percent chance of rain."
    )


TOOLS = [get_weather]
