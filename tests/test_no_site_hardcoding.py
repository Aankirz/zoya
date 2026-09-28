"""Phase H guard: nothing under zoya/ names a website or reaches into one site's markup.

Every task must work on a site nobody wrote code for. A hostname or a site's own CSS selector in
zoya/ is how per-site code creeps back, so this fails on the first one outside ALLOWED_HOSTS.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

ZOYA = Path(__file__).resolve().parents[1] / "zoya"
TEXT_SUFFIXES = {".py", ".md", ".json", ".js", ".html", ".css", ".txt", ".yaml", ".yml", ".toml"}
HOSTNAME = re.compile(
    r"\b(?:[a-z0-9-]+\.)+(?:com|in|org|net|io|ai|dev|co|tv|fm|me|so|xyz|uk|us|de|fr|jp)\b",
    re.IGNORECASE,
)
SITE_SELECTOR = re.compile(
    r"(?:^|[\s,>+~(])[a-z]*"
    r"(?:#[A-Za-z][\w-]{2,}|\.[a-z][\w]*-[\w-]+|\[(?:data-[\w-]+|id|class|aria-label|href)[\^$~|]?=)"
)
ALLOWED_HOSTS = {
    "api.openai.com": "the model provider's endpoint",
    "zoya-relay.zoya-relay.workers.dev": "Zoya's own relay (D133)",
    "api.fireworks.ai": "the model provider's endpoint",
    "api.search.tinyfish.ai": "the web search provider's endpoint",
    "api.fetch.tinyfish.ai": "the web fetch provider's endpoint",
    "github.com": "the pinned Supermemory server release",
    "geocoding-api.open-meteo.com": "the weather provider's endpoint",
    "api.open-meteo.com": "the weather provider's endpoint",
    "booking.com": "the safety gate's payment refusal (§9.9), out of this phase's reach",
    "open.spotify.com": "D58: the owner's open-in-the-browser list for named apps",
    "youtube.com": "D58: the owner's open-in-the-browser list for named apps",
    "music.youtube.com": "D58: the owner's open-in-the-browser list for named apps",
    "web.whatsapp.com": "D58: the owner's open-in-the-browser list for named apps",
    "mail.google.com": "D58: the owner's open-in-the-browser list for named apps",
}


OWN_UI = {"hub": "Zoya's own bundled Hub pages: their anchors and ids are hers, not a site's"}
SCRIPT_SUFFIXES = {".js", ".html", ".css"}
QUOTED = re.compile(r"'[^'\n]*'|\"[^\"\n]*\"|`[^`\n]*`")
KEPT_SKILLS = {
    "shopping": "round 1: 2/3 without it; buy asks the cable type instead of picking one",
    "hotels_web": "round 1: 0/2; a text click on an FAQ about check-out times asks, as it should",
    "youtube": "round 1: 2/3; subscribe names the host, not the channel, until Jev (D101, D123)",
    "x_web": "round 1: 0/1; the composer is not reachable by the browser tools",
    "spotify_web": "round 1: 0/1; Spotify's search did not respond to the browser tools",
}


def docstrings(tree: ast.AST) -> set[int]:
    holders = (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, holders) and node.body and isinstance(node.body[0], ast.Expr):
            value = node.body[0].value
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                found.add(id(value))
    return found


def literals(path: Path) -> list[tuple[int, str]]:
    text = path.read_text(encoding="utf-8")
    if path.suffix in SCRIPT_SUFFIXES:
        return [
            (line, quoted.group(0)[1:-1])
            for line, source in enumerate(text.splitlines(), 1)
            for quoted in QUOTED.finditer(source)
        ]
    if path.suffix != ".py":
        return list(enumerate(text.splitlines(), 1))
    tree = ast.parse(text)
    skip = docstrings(tree)
    return [
        (node.lineno, node.value)
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in skip
    ]


def kept_skill(relative: Path) -> bool:
    parts = relative.parts
    return len(parts) > 1 and parts[0] == "skills" and parts[1] in KEPT_SKILLS


def offences(root: Path) -> list[str]:
    found = []
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        own_ui = relative.parts[0] in OWN_UI
        if path.suffix not in TEXT_SUFFIXES or kept_skill(relative) or own_ui:
            continue
        for line, value in literals(path):
            for host in HOSTNAME.findall(value):
                if host.casefold().removeprefix("www.") not in ALLOWED_HOSTS:
                    found.append(f"{relative}:{line}: host {host}")
            if SITE_SELECTOR.search(value):
                found.append(f"{relative}:{line}: selector {value[:60]!r}")
    return found


def test_zoya_names_no_site_and_no_site_selector() -> None:
    assert offences(ZOYA) == []


@pytest.mark.parametrize(
    "planted",
    [
        'SHOP = "https://www.flipkart.com/search"\n',
        'PRICE = "span.a-price-whole"\n',
        'BUTTON = "button[data-testid=tweetButton]"\n',
        "Open Amazon.in and search.\n",
        "const buy = document.querySelector('#buy-now-button');\n",
    ],
)
def test_a_planted_site_literal_fails_the_guard(tmp_path: Path, planted: str) -> None:
    suffix = {"O": ".md", "c": ".js"}.get(planted[0], ".py")
    (tmp_path / f"planted{suffix}").write_text(planted, encoding="utf-8")
    assert offences(tmp_path)


def test_generic_selectors_and_endpoints_pass(tmp_path: Path) -> None:
    (tmp_path / "generic.py").write_text(
        'EDITOR = "div[role=textbox]"\nCAPTCHA = "iframe[src*=captcha]"\n'
        'API = "https://api.openai.com/v1"\n',
        encoding="utf-8",
    )
    assert offences(tmp_path) == []
