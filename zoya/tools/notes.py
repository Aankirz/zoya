"""Notes.app tools (§6 Flow 4, §9.4 T0): create, search, append via AppleScript.

User text is passed as osascript argv and HTML-escaped for the note body, so
dictated text can never become AppleScript code or markup. First use triggers
macOS's Automation prompt for Notes (AUDIT B12, error -1743) — the owner must allow it.
"""

from __future__ import annotations

from html import escape

from strands import tool

from zoya.tools import ToolError
from zoya.tools.fast import osascript

TITLE_MAX_CHARS = 40
MAX_SEARCH_RESULTS = 3
NAME_SEPARATOR = "\n"

CREATE_SCRIPT = """on run argv
tell application "Notes" to make new note with properties {name:item 1 of argv, body:item 2 of argv}
end run"""

SEARCH_SCRIPT = """on run argv
set AppleScript's text item delimiters to linefeed
set term to item 1 of argv
tell application "Notes"
set found to name of every note whose name contains term or plaintext contains term
end tell
return found as text
end run"""

APPEND_SCRIPT = """on run argv
tell application "Notes"
set matches to every note whose name contains (item 1 of argv)
if (count of matches) is 0 then return ""
set target to item 1 of matches
set body of target to (body of target) & (item 2 of argv)
return name of target
end tell
end run"""


def _title_from(text: str) -> str:
    first_line = text.strip().splitlines()[0] if text.strip() else ""
    return first_line[:TITLE_MAX_CHARS].rstrip()


def _html(title: str, body: str) -> str:
    """Notes shows the body's first line as the title, so only add a heading when it differs."""
    if body.startswith(title):
        return f"<div>{escape(body)}</div>"
    return f"<div><b>{escape(title)}</b></div><div>{escape(body)}</div>"


@tool
def notes_create(body: str, title: str = "") -> str:
    """Create a new note in Notes. `body` is the note text; `title` is optional."""
    text = body.strip()
    if not text:
        raise ToolError("What should the note say?")
    heading = title.strip() or _title_from(text)
    osascript(CREATE_SCRIPT, heading, _html(heading, text))
    return f"Saved to Notes: {text}"


@tool
def notes_search(query: str) -> str:
    """Find notes whose title or text contains `query`; returns up to three note titles."""
    term = query.strip()
    if not term:
        raise ToolError("What should I search your notes for?")
    names = [name for name in osascript(SEARCH_SCRIPT, term).split(NAME_SEPARATOR) if name]
    if not names:
        return f"I found no notes about {term}."
    top = names[:MAX_SEARCH_RESULTS]
    return f"I found {len(names)} notes. " + "; ".join(top) + "."


@tool
def notes_append(note_name: str, text: str) -> str:
    """Append `text` to the first note whose title contains `note_name`."""
    addition = text.strip()
    if not note_name.strip() or not addition:
        raise ToolError("Which note, and what should I add?")
    matched = osascript(APPEND_SCRIPT, note_name.strip(), f"<div>{escape(addition)}</div>")
    if not matched:
        raise ToolError(f"I couldn't find a note called {note_name}.")
    return f"Added to {matched}: {addition}"


TOOLS = [notes_create, notes_search, notes_append]
