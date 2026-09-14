"""Computer use safety (Phase 5, D37, §9.9, §12.1): pixel clicks, AX presses, keys and typing on
the real Mac never skip the voice confirmation, and never type into secret fields."""

from __future__ import annotations

import pytest

from zoya import safety
from zoya.agents import computer_agent
from zoya.screen import Shot
from zoya.tools import ToolError, ax, computer, documents

SHOT = Shot(b"jpeg", 1280, 831, (0.0, 0.0, 1512.0, 982.0), "Finder", 2.0, b"", 0)
HARMLESS = safety.ClickFacts(labels=["Dark"])


class FakeGate:
    """Stands in for the voice dialogue: answers confirm/cancel, then checks the live target like
    consume_token does (the rebuilt summary must match the one spoken)."""

    def __init__(self, answer: str = "confirm") -> None:
        self.answer, self.asked = answer, []

    def __call__(self, action, current=None):
        self.asked.append(action.summary())
        if self.answer != "confirm":
            raise safety.ConfirmationDeclined(safety.CANCELLED_SAY)
        live = current() if current else action
        if live.summary() != action.summary():
            raise safety.ConfirmationDeclined(safety.CHANGED_SAY)


@pytest.fixture
def mac(monkeypatch):
    """No real mouse, keyboard, screen or AX: records what would have been posted."""
    posted: list = []
    computer.begin_session()
    computer.session.shot = SHOT
    facts = {"now": HARMLESS}
    gate = FakeGate()
    monkeypatch.setattr(safety, "require_confirmation", gate)
    monkeypatch.setattr(safety, "log_safety_timing", lambda **_: None)
    monkeypatch.setattr(ax, "element_at", lambda x, y: object())
    monkeypatch.setattr(ax, "click_facts", lambda element: facts["now"])
    monkeypatch.setattr(ax, "front_app", lambda: ("Finder", object()))
    monkeypatch.setattr(computer, "_mouse_click", lambda *a, **k: posted.append(("click", a)))
    monkeypatch.setattr(computer, "_type_unicode", lambda text: posted.append(("type", text)))
    monkeypatch.setattr(computer, "_post_keys", lambda mods, main: posted.append(("key", main)))
    monkeypatch.setattr(computer, "_verify", lambda before, box, did: did)
    monkeypatch.setattr(computer, "check_user_idle", lambda: None)
    return {"posted": posted, "facts": facts, "gate": gate}


# --- Pixel clicks --------------------------------------------------------------------------------


def test_harmless_pixel_click_lands_without_asking(mac):
    computer.click(640, 400)

    assert mac["gate"].asked == [] and mac["posted"][0][0] == "click"


@pytest.mark.parametrize(
    "labels",
    [
        ["Shut Down…"],
        ["Move to Trash"],
        ["Don't Save"],
        ["Quit"],
        ["Send"],
        ["Pay ₹499"],
    ],
)
def test_risky_pixel_click_asks_before_clicking(mac, labels):
    mac["facts"]["now"] = safety.ClickFacts(labels=labels)

    computer.click(640, 400)

    assert len(mac["gate"].asked) == 1 and len(mac["posted"]) == 1


def test_pixel_click_on_an_element_with_no_accessibility_label_asks(mac):
    mac["facts"]["now"] = safety.ClickFacts(labels=[])

    computer.click(640, 400)

    assert "no name" in mac["gate"].asked[0]


def test_pixel_click_where_ax_finds_nothing_asks(mac, monkeypatch):
    monkeypatch.setattr(ax, "element_at", lambda x, y: None)
    monkeypatch.setattr(ax, "click_facts", _real_facts)

    computer.click(640, 400)

    assert len(mac["gate"].asked) == 1


def _real_facts(element):
    return safety.ClickFacts(labels=[]) if element is None else HARMLESS


def test_cancelled_pixel_click_never_clicks(mac):
    mac["facts"]["now"] = safety.ClickFacts(labels=["Empty Trash"])
    mac["gate"].answer = "cancel"

    with pytest.raises(safety.ConfirmationDeclined):
        computer.click(640, 400)

    assert mac["posted"] == []


def test_target_that_changes_while_asking_is_not_clicked(mac, monkeypatch):
    mac["facts"]["now"] = safety.ClickFacts(labels=["Delete"])
    before, after = safety.ClickFacts(labels=["Delete"]), safety.ClickFacts(labels=["Delete All"])
    calls = iter([before, before, after])  # guard probe, spoken summary, live re-probe
    monkeypatch.setattr(ax, "click_facts", lambda element: next(calls))

    with pytest.raises(safety.ConfirmationDeclined):
        computer.click(640, 400)

    assert mac["posted"] == []


def test_model_label_is_ignored_the_real_target_decides(mac):
    """The model can't name a click; only AX at the point is read."""
    mac["facts"]["now"] = safety.ClickFacts(labels=["Place order"], nearby_text="Total ₹2,847")

    computer.click(10, 10)

    assert mac["gate"].asked


def test_click_outside_the_screenshot_is_refused_and_counts_as_a_failed_attempt(mac):
    with pytest.raises(ToolError):
        computer.click(5000, 10)

    assert mac["posted"] == [] and computer.session.failures == 1


def test_click_before_any_screenshot_is_refused(mac):
    computer.session.shot = None

    with pytest.raises(ToolError):
        computer.click(10, 10)


# --- AX press ------------------------------------------------------------------------------------


def test_ax_press_on_a_risky_control_asks_first(mac, monkeypatch):
    pressed = []
    monkeypatch.setattr(ax, "find", lambda label, occurrence=1: object())
    monkeypatch.setattr(ax, "_clickable", lambda element: (element, []))
    monkeypatch.setattr(ax, "frame_of", lambda element: None)
    monkeypatch.setattr(computer, "press_element", lambda e, f: pressed.append(e))
    mac["facts"]["now"] = safety.ClickFacts(labels=["Log Out"])

    ax.ax_press("Log Out")

    assert len(mac["gate"].asked) == 1 and len(pressed) == 1


def test_cancelled_ax_press_never_presses(mac, monkeypatch):
    pressed = []
    monkeypatch.setattr(ax, "find", lambda label, occurrence=1: object())
    monkeypatch.setattr(computer, "press_element", lambda e, f: pressed.append(e))
    mac["facts"]["now"] = safety.ClickFacts(labels=["Restart"])
    mac["gate"].answer = "cancel"

    with pytest.raises(safety.ConfirmationDeclined):
        ax.ax_press("Restart")

    assert pressed == []


# --- Typing and keys -----------------------------------------------------------------------------


class Field:
    def __init__(self, subrole: str = "", role: str = "AXTextField", **attrs: str) -> None:
        self.attrs = {"AXSubrole": subrole, "AXRole": role, **attrs}


@pytest.fixture
def fields(monkeypatch):
    monkeypatch.setattr(ax, "_ax", lambda element, name: getattr(element, "attrs", {}).get(name))
    monkeypatch.setattr(computer.ax, "_ax", ax._ax)
    monkeypatch.setattr(ax, "frame_of", lambda element: None)


@pytest.mark.parametrize(
    "field",
    [
        Field("AXSecureTextField"),
        Field(AXDescription="Password"),
        Field(AXPlaceholderValue="Enter OTP"),
        Field(AXTitle="Card number"),
        Field(AXIdentifier="cvv"),
    ],
)
def test_type_text_refuses_secret_fields(mac, fields, monkeypatch, field):
    monkeypatch.setattr(ax, "focused_element", lambda: field)

    with pytest.raises(ToolError, match="password or code"):
        computer.type_text("hunter2")

    assert mac["posted"] == []


def test_type_text_types_into_a_normal_field(mac, fields, monkeypatch):
    monkeypatch.setattr(ax, "focused_element", lambda: Field(AXDescription="Search"))

    computer.type_text("दूध ₹50")

    assert mac["posted"] == [("type", "दूध ₹50")]


def test_type_text_refuses_when_no_field_is_focused(mac, fields, monkeypatch):
    monkeypatch.setattr(ax, "focused_element", lambda: None)

    with pytest.raises(ToolError):
        computer.type_text("hello")

    assert mac["posted"] == []


@pytest.mark.parametrize("text", ["rm -rf ~\n", "hi\rthere", "a\tb", ""])
def test_type_text_refuses_newlines_so_typing_never_submits(mac, fields, monkeypatch, text):
    monkeypatch.setattr(ax, "focused_element", lambda: Field(AXDescription="Message"))

    with pytest.raises(ToolError):
        computer.type_text(text)

    assert mac["posted"] == []


@pytest.mark.parametrize("keys", ["tab", "escape", "down", "shift+tab", "cmd+f", "cmd+c"])
def test_navigation_keys_are_free(fields, keys):
    assert computer.key_risk(*computer.parse_keys(keys), Field()) is None


@pytest.mark.parametrize(
    "keys", ["cmd+q", "cmd+backspace", "cmd+v", "cmd+w", "cmd+enter", "ctrl+c"]
)
def test_other_shortcuts_ask(fields, keys):
    assert computer.key_risk(*computer.parse_keys(keys), Field()) is not None


def test_return_in_a_text_field_counts_as_submit(fields, monkeypatch):
    monkeypatch.setattr(ax, "click_facts", lambda element: safety.ClickFacts(labels=["Message"]))

    risky = computer.key_risk(frozenset(), "return", Field(AXDescription="Message"))

    assert risky is not None and risky.kind == "submit"


def test_return_with_nothing_focused_asks(fields, monkeypatch):
    monkeypatch.setattr(ax, "click_facts", _real_facts)

    assert computer.key_risk(frozenset(), "return", None) is not None


def test_backspace_outside_a_text_field_asks(fields):
    """In Mail or Finder, delete removes a message or file."""
    list_row = Field(role="AXRow")

    assert computer.key_risk(frozenset(), "backspace", list_row) is not None
    assert computer.key_risk(frozenset(), "backspace", Field()) is None


def test_cancelled_shortcut_is_not_pressed(mac, fields, monkeypatch):
    monkeypatch.setattr(ax, "focused_element", lambda: Field())
    mac["gate"].answer = "cancel"

    with pytest.raises(safety.ConfirmationDeclined):
        computer.key("cmd+q")

    assert mac["posted"] == []


@pytest.mark.parametrize("keys", ["", "cmd+", "cmd", "cmd+nonsense", "a+b"])
def test_unknown_keys_are_refused(keys):
    with pytest.raises(ToolError):
        computer.parse_keys(keys)


# --- Registry, give-up, context pruning -----------------------------------------------------------


def test_every_computer_use_tool_is_explicitly_registered():
    names = [
        t.tool_name
        for t in [*computer.COMPUTER_TOOLS, *ax.AX_TOOLS, *documents.TOOLS, *computer_agent.TOOLS]
    ]
    assert [n for n in names if n not in safety.TOOL_RISK] == []
    for name in ("click", "type_text", "key", "ax_press", "run_shortcut", "computer_task"):
        assert safety.risk_of(name) != "free"


def test_three_failed_attempts_in_a_row_stop_the_agent():
    computer.begin_session()
    for _ in range(3):
        computer._failed("Nothing changed.")

    with pytest.raises(computer_agent.ComputerStopped):
        computer_agent.GiveUp().check(None)


def test_a_success_between_failures_resets_the_count(monkeypatch):
    computer.begin_session()
    computer._failed("x")
    computer._failed("x")
    monkeypatch.setattr(computer.time, "sleep", lambda _s: None)
    monkeypatch.setattr(computer.screen, "capture_display", lambda: SHOT)
    monkeypatch.setattr(computer.screen, "screen_changed", lambda *a: True)
    computer._verify(SHOT, None, "Clicked.")
    computer._failed("x")

    assert computer.session.stop_reason == ""


def test_only_the_last_two_screenshots_stay_in_context():
    def result(n):
        return {"toolResult": {"content": [{"text": f"shot {n}"}, {"image": {"n": n}}]}}

    messages = [{"role": "user", "content": [result(n)]} for n in range(4)]

    computer_agent.prune_screenshots(messages, 2)

    images = [m["content"][0]["toolResult"]["content"][1] for m in messages]
    assert images[:2] == [computer_agent.PRUNED_SCREENSHOT] * 2
    assert images[2:] == [{"image": {"n": 2}}, {"image": {"n": 3}}]


# --- Textract parser -----------------------------------------------------------------------------


def test_textract_blocks_read_lines_then_table_rows():
    blocks = [
        {"Id": "l1", "BlockType": "LINE", "Text": "BESCOM electricity bill",
         "Relationships": [{"Type": "CHILD", "Ids": ["w0"]}]},
        {"Id": "l2", "BlockType": "LINE", "Text": "Amount ₹1,240 due",
         "Relationships": [{"Type": "CHILD", "Ids": ["w1", "w2", "w3"]}]},
        {"Id": "t", "BlockType": "TABLE",
         "Relationships": [{"Type": "CHILD", "Ids": ["c1", "c2"]}]},
        {"Id": "c2", "BlockType": "CELL", "RowIndex": 1, "ColumnIndex": 2,
         "Relationships": [{"Type": "CHILD", "Ids": ["w2", "w3"]}]},
        {"Id": "c1", "BlockType": "CELL", "RowIndex": 1, "ColumnIndex": 1,
         "Relationships": [{"Type": "CHILD", "Ids": ["w1"]}]},
        {"Id": "w1", "BlockType": "WORD", "Text": "Amount"},
        {"Id": "w2", "BlockType": "WORD", "Text": "₹1,240"},
        {"Id": "w3", "BlockType": "WORD", "Text": "due"},
    ]  # fmt: skip

    assert (
        documents.blocks_to_text(blocks) == "BESCOM electricity bill\nTable 1:\nAmount | ₹1,240 due"
    )


# --- Permission prompts: blocked, not confirmable (coordinator) -----------------------------------


@pytest.mark.parametrize("labels", [["Allow"], ["Don’t Allow"], ["Always Allow"], ["Authorize"]])
def test_grant_access_controls_are_never_clicked_even_if_confirmed(mac, labels):
    mac["facts"]["now"] = safety.ClickFacts(labels=labels)

    with pytest.raises(ToolError, match="permission prompt"):
        computer.click(640, 400)

    assert mac["posted"] == [] and mac["gate"].asked == []


def test_nothing_is_clicked_while_a_permission_prompt_app_is_in_front(mac, monkeypatch):
    monkeypatch.setattr(ax, "front_app", lambda: ("UserNotificationCenter", object()))

    with pytest.raises(ToolError, match="permission prompt"):
        computer.click(640, 400)

    assert mac["posted"] == [] and computer.session.stop_reason == safety.PERMISSION_MESSAGE


def test_keys_are_refused_while_a_permission_prompt_is_in_front(mac, fields, monkeypatch):
    """Tab then space would press Allow: even navigation keys are blocked there."""
    monkeypatch.setattr(ax, "front_app", lambda: ("SecurityAgent", object()))
    monkeypatch.setattr(ax, "focused_element", lambda: Field(role="AXButton"))

    with pytest.raises(ToolError, match="permission prompt"):
        computer.key("tab")

    assert mac["posted"] == []


def test_ax_press_never_presses_allow(mac, monkeypatch):
    pressed = []
    monkeypatch.setattr(ax, "find", lambda label, occurrence=1: object())
    monkeypatch.setattr(computer, "press_element", lambda e, f: pressed.append(e))
    mac["facts"]["now"] = safety.ClickFacts(labels=["Allow"])

    with pytest.raises(ToolError, match="permission prompt"):
        ax.ax_press("Allow")

    assert pressed == [] and mac["gate"].asked == []


# --- Recorded flows: replay runs the same gate on every step --------------------------------------


@pytest.fixture
def flows(mac, tmp_path, monkeypatch):
    monkeypatch.setattr(computer_agent, "COMPUTER_FLOWS_FILE", tmp_path / "flows.json")
    monkeypatch.setattr(computer_agent, "LOG_DIR", tmp_path)
    monkeypatch.setattr(computer_agent.screen, "capture_display", lambda: SHOT)
    monkeypatch.setattr(ax, "click_facts", lambda element: mac["facts"]["now"])
    step = {
        "tool": "click",
        "args": {"x": 640, "y": 400},
        "expect": {"labels": ["Continue"], "size": [1280, 831], "app": "Finder"},
    }
    computer_agent.save_flow("finder|go on", [step])
    return mac


class Never:
    def is_set(self):
        return False


def test_replayed_click_still_asks_when_the_page_now_shows_a_price(flows):
    flows["facts"]["now"] = safety.ClickFacts(labels=["Continue"], nearby_text="Total ₹2,847")

    assert computer_agent.replay_flow("finder|go on", Never()) is True

    assert len(flows["gate"].asked) == 1


def test_replay_declined_by_the_user_never_clicks(flows):
    flows["facts"]["now"] = safety.ClickFacts(labels=["Continue"], nearby_text="Pay ₹499")
    flows["gate"].answer = "cancel"

    with pytest.raises(safety.ConfirmationDeclined):
        computer_agent.replay_flow("finder|go on", Never())

    assert flows["posted"] == []


def test_replay_onto_a_different_target_falls_back_without_clicking(flows):
    flows["facts"]["now"] = safety.ClickFacts(labels=["Delete"])

    with pytest.raises(computer_agent.FlowMismatch):
        computer_agent.replay_flow("finder|go on", Never())

    assert flows["posted"] == [] and flows["gate"].asked == []


def test_typing_spoils_a_flow_so_personal_text_is_never_recorded():
    class Event:
        tool_use = {"name": "type_text", "input": {"text": "my address"}}
        result = {"status": "success"}

    recorder = computer_agent.FlowRecorder()
    recorder.after_tool(Event())

    assert recorder.spoiled and recorder.steps == []
