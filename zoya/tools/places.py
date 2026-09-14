"""Nearby places (brief: "nearest pharmacy / what's near me") via Amazon Location Places API v2.

The v2 API is resourceless: no place index, only IAM (geo-places:* on provider/default, policy
be00f12). The Mac has no GPS for Zoya, so "near me" means the area the user names, else the home
address in memory. Calls are bounded by aws.client (2 s). Only the place words and the area leave
the Mac.

APIs (boto3 `geo-places`, verified in the installed botocore model 2026-09-14):
- Geocode(QueryText, MaxResults) → ResultItems[].Position [lon, lat]
  https://docs.aws.amazon.com/location/latest/APIReference/API_geoplaces_Geocode.html
- SearchText(QueryText, BiasPosition [lon, lat], MaxResults) → ResultItems[] {Title, Address.Label,
  Distance (m)} https://docs.aws.amazon.com/location/latest/APIReference/API_geoplaces_SearchText.html
"""

from __future__ import annotations

from strands import tool

from zoya import aws, safety
from zoya.config import PLACES_MAX_RESULTS
from zoya.tools import ToolError
from zoya.tools.memory import home_address

METRES_PER_KM = 1000
NO_AREA = (
    "Which area are you in? You can also say: remember my home address is Indiranagar, Bengaluru."
)


def _client():  # noqa: ANN202 — boto3 client
    client = aws.client("geo-places")
    if client is None:
        raise ToolError("Place search needs AWS, which isn't set up.")
    return client


def spoken_distance(metres: float | None) -> str:
    if metres is None:
        return ""
    if metres < METRES_PER_KM:
        return f", {round(metres / 10) * 10} metres away"
    return f", {metres / METRES_PER_KM:.1f} kilometres away"


def _area_position(area: str) -> list[float]:
    response = _client().geocode(QueryText=area, MaxResults=1)
    items = response.get("ResultItems") or []
    if not items:
        raise ToolError(f"I couldn't find {area} on the map.")
    return items[0]["Position"]


@tool
def nearby_places(what: str, area: str = "") -> str:
    """Find places near the user, e.g. the nearest pharmacy, ATM or restaurant.

    Args:
        what: The kind of place, e.g. "pharmacy".
        area: Where to search, e.g. "Indiranagar, Bengaluru". Empty = the home address in memory.
    """
    if not what.strip():
        raise ToolError("What kind of place should I look for?")
    near = area.strip() or home_address()
    if not near:
        raise ToolError(NO_AREA)
    try:
        position = _area_position(near)
        response = _client().search_text(
            QueryText=what.strip(), BiasPosition=position, MaxResults=PLACES_MAX_RESULTS
        )
    except ToolError:
        raise
    except Exception as error:  # noqa: BLE001 — AWS errors become a polite sentence
        raise ToolError("I couldn't search the map right now.") from error
    items = response.get("ResultItems") or []
    if not items:
        return f"I found no {what} near {near}."
    lines = [
        f"{item.get('Title', '')}{spoken_distance(item.get('Distance'))}: "
        f"{item.get('Address', {}).get('Label', '')}"
        for item in items
    ]
    return f"Near {near} (Amazon Location):\n" + safety.wrap_untrusted("\n".join(lines))


TOOLS = [nearby_places]
