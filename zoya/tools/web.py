"""Web research (Flow 3, brief "Deep web research"): search → fetch the best pages → answer.

TinyFish Search and Fetch APIs, stdlib `urllib`, fixed hosts, key in the `X-API-Key` header. Only
the query or the URL leaves the Mac. Results and page text are untrusted (§12.2): they reach the
model inside <untrusted_content>, with the site name outside so Zoya can say "according to …".

APIs (verified live 2026-09-14 with the owner's key):
- https://docs.tinyfish.ai/search-api/reference — GET ?query=&intent=&location=&language=;
  results[] {position, site_name, title, snippet, url}. Free tier: 30 searches/min.
- https://docs.tinyfish.ai/fetch-api/reference — POST {urls[], intent, format, per_url_timeout_ms};
  results[] {url, title, text}, errors[]. 150 fetches/min.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any
from urllib.parse import urlparse

from strands import tool

from zoya import cache, safety
from zoya.config import (
    TINYFISH_FETCH_URL,
    TINYFISH_SEARCH_URL,
    WEB_CACHE_TTL_S,
    WEB_FETCH_MAX_CHARS,
    WEB_FETCH_TIMEOUT_S,
    WEB_RESULTS_MAX,
    WEB_SEARCH_TIMEOUT_S,
)
from zoya.tools import ToolError
from zoya.tools.fast import normalise_url

MAX_RESPONSE_BYTES = 2_000_000
MAX_QUERY_CHARS = 300
MAX_FETCH_URLS = 3
MS_PER_S = 1000
API_SLACK_S = 5.0  # the API's per-URL budget ends before our socket timeout
NO_KEY = "Web search isn't set up: the TinyFish key is missing."


def _key() -> str:
    key = os.environ.get("TINYFISH_API_KEY", "")
    if not key:
        raise ToolError(NO_KEY)
    return key


def _call(request: urllib.request.Request, timeout: float) -> dict[str, Any]:
    request.add_header("X-API-Key", _key())
    try:
        with urllib.request.urlopen(
            request, timeout=timeout
        ) as response:  # noqa: S310 — fixed host
            return json.loads(response.read(MAX_RESPONSE_BYTES))
    except urllib.error.HTTPError as error:
        busy = error.code == 429
        raise ToolError(
            "Web search is busy, try again in a minute." if busy else "Web search failed."
        ) from error
    except (urllib.error.URLError, TimeoutError, ValueError) as error:
        raise ToolError("I couldn't reach the web search service.") from error


def format_results(results: list[dict[str, Any]]) -> str:
    """Numbered results: source name, title, snippet, url. Parser for the search response."""
    lines = []
    for number, item in enumerate(results[:WEB_RESULTS_MAX], start=1):
        site = str(item.get("site_name") or urlparse(str(item.get("url", ""))).netloc)
        title = str(item.get("title", "")).strip()
        snippet = str(item.get("snippet", "")).strip()
        lines.append(f"{number}. [{site}] {title} — {snippet} ({item.get('url', '')})")
    return "\n".join(lines)


@tool
def web_search(query: str, intent: str = "") -> str:
    """Search the web. Use it for facts, news, prices and comparisons instead of guessing.

    Then call web_fetch on the 2–3 best results and answer, naming the source ("according to …").

    Args:
        query: Search keywords, e.g. "Bengaluru population 2026".
        intent: Why you are searching, in one sentence (improves results).
    """
    query = " ".join(query.split())[:MAX_QUERY_CHARS]
    if not query:
        raise ToolError("What should I search for?")
    args = {"query": query, "intent": intent}
    if (hit := cache.get("web_search", args)) is not None:
        return hit
    params = {"query": query, "language": "en"}
    if intent.strip():
        params["intent"] = intent.strip()[:MAX_QUERY_CHARS]
    url = f"{TINYFISH_SEARCH_URL}?{urllib.parse.urlencode(params)}"
    data = _call(urllib.request.Request(url), WEB_SEARCH_TIMEOUT_S)
    results = data.get("results") or []
    if not results:
        return f"No web results for {query}."
    answer = safety.wrap_untrusted(format_results(results))
    cache.put("web_search", args, answer, WEB_CACHE_TTL_S)
    return answer


@tool
def web_fetch(urls: list[str], intent: str = "") -> str:
    """Read up to three web pages as text (from web_search results).

    Args:
        urls: http(s) addresses, at most three.
        intent: What you want from the pages, in one sentence.
    """
    addresses = [normalise_url(url) for url in urls[:MAX_FETCH_URLS] if url.strip()]
    if not addresses:
        raise ToolError("Which page should I read?")
    args = {"urls": " ".join(addresses), "intent": intent}
    if (hit := cache.get("web_fetch", args)) is not None:
        return hit
    body: dict[str, Any] = {
        "urls": addresses,
        "format": "markdown",
        "per_url_timeout_ms": int((WEB_FETCH_TIMEOUT_S - API_SLACK_S) * MS_PER_S),
    }
    if intent.strip():
        body["intent"] = intent.strip()[:MAX_QUERY_CHARS]
    request = urllib.request.Request(
        TINYFISH_FETCH_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    data = _call(request, WEB_FETCH_TIMEOUT_S)
    pages = [
        f"Source: {urlparse(str(page.get('url', ''))).netloc}\n"
        + safety.wrap_untrusted(
            f"{page.get('title', '')}\n{page.get('text', '')}"[:WEB_FETCH_MAX_CHARS]
        )
        for page in data.get("results") or []
    ]
    if not pages:
        raise ToolError("I couldn't read those pages.")
    answer = "\n\n".join(pages)
    cache.put("web_fetch", args, answer, WEB_CACHE_TTL_S)
    return answer


TOOLS = [web_search, web_fetch]
