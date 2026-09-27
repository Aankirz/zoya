"""D126: the Jev web loop, offline on recorded snapshots (Jev is blocked, D123).

H-C: nothing Jev or the text model returns becomes a selector, coordinates or script. Jev can
only pick an offered index, which maps to a node id the snapshot assigned, and the model's text
is only ever typed.
"""

import json
from pathlib import Path
from typing import Any

import pytest

from zoya import decisions
from zoya.agents import web_loop

FIXTURES = Path(__file__).parent / "fixtures" / "web"
RECORDED = sorted(p for p in FIXTURES.glob("*.json"))
HOSTILE = [
    "#place-order",
    "button[data-testid=buy]",
    "document.querySelector('form').submit()",
    "javascript:alert(1)",
    "e1",
    "0",
    "999999",
]


def recorded(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def answers(operation: str, target: str | None = None, confidence: float = 0.95):
    found = {"operation": {"choice": operation, "confidence": confidence}}
    if target is not None:
        found[f"{operation.lower()}_target"] = {"choice": target, "confidence": confidence}
    return decisions.Answers(found, 1)


@pytest.mark.parametrize("path", RECORDED, ids=lambda p: p.stem)
def test_every_offered_target_is_an_observed_node(path):
    page = recorded(path)
    table = web_loop.element_table(page["actions"])
    observed = {id(a) for a in page["actions"]}
    assert table.targets
    for operation, candidates in table.targets.items():
        for key, action in candidates.items():
            assert id(action) in observed and type(action["node"]) is int
            assert web_loop.OPERATION_OF[action["kind"]] == operation
            assert key.split(":")[0].isdigit()


@pytest.mark.parametrize("path", RECORDED, ids=lambda p: p.stem)
def test_one_request_carries_the_operation_and_every_target_head(path):
    page = recorded(path)
    table = web_loop.element_table(page["actions"])
    asked = web_loop.questions(table, page)
    assert set(asked) == {"operation", *(f"{op.lower()}_target" for op in table.targets)}
    assert set(web_loop.operations_offered(table, page)) == set(asked["operation"].criteria)
    state = web_loop.state_text("goal", page, [], table)
    assert state.count("<untrusted_content>") == 1 and state.count("</untrusted_content>") == 1


@pytest.mark.parametrize("path", RECORDED, ids=lambda p: p.stem)
@pytest.mark.parametrize("hostile", HOSTILE)
def test_a_target_jev_did_not_get_offered_never_acts(path, hostile):
    page = recorded(path)
    table = web_loop.element_table(page["actions"])
    offered = web_loop.operations_offered(table, page)
    if hostile in table.targets.get("CLICK", {}):
        pytest.skip("an offered index")
    assert web_loop.decide(answers("CLICK", hostile), table, offered) is None
    assert web_loop.decide(answers(hostile), table, offered) is None


def test_a_valid_pick_returns_the_observed_action_itself():
    page = recorded(RECORDED[0])
    table = web_loop.element_table(page["actions"])
    key, action = next(iter(table.targets["CLICK"].items()))
    offered = web_loop.operations_offered(table, page)
    decision = web_loop.decide(answers("CLICK", key), table, offered)
    assert decision is not None and decision.action is action


def test_below_the_threshold_nothing_acts():
    page = recorded(RECORDED[0])
    table = web_loop.element_table(page["actions"])
    key = next(iter(table.targets["CLICK"]))
    offered = web_loop.operations_offered(table, page)
    assert web_loop.decide(answers("CLICK", key, confidence=0.5), table, offered) is None


@pytest.mark.parametrize(
    "raw",
    [
        "Goa",
        '```json\n{"text": "Goa"}\n```',
        '{"text": "Goa", "selector": "#where"}',
        '{"text": null}',
        '{"text": ""}',
        '["Goa"]',
        '{"text": "' + "x" * 3000 + '"}',
    ],
)
def test_the_text_model_types_nothing_unless_it_answers_plain_json(raw):
    assert web_loop.parse_field_text(raw) is None


def test_the_text_model_value_is_typed_and_never_evaluated(monkeypatch):
    payload = "document.cookie='x'; #where"
    seen: list[Any] = []

    class Locator:
        def count(self):
            return 1

        def get_attribute(self, _name):
            return ""

        def fill(self, text):
            seen.append(("fill", text))

    class Page:
        def evaluate(self, script, arg=None):
            seen.append(("evaluate", script, arg))
            if "pageKey" in script:
                return [["key"], ["guard"], True]
            return True

        def get_by_test_id(self, tag):
            seen.append(("test_id", tag))
            return Locator()

    monkeypatch.setattr(web_loop.browser, "on_page", lambda work: work(Page()))
    monkeypatch.setattr(web_loop.browser, "use_test_id_attribute", lambda _name: None)
    observed = {"page_key": ["key"], "guards": {"7": ["guard"]}}
    web_loop._type(observed, {"node": 7, "label": "Destination"}, payload)
    assert ("fill", payload) in seen
    reached_page = [str(part) for entry in seen if entry[0] != "fill" for part in entry[1:]]
    assert not any(payload in part for part in reached_page)


def test_a_node_the_snapshot_did_not_assign_is_refused():
    with pytest.raises(web_loop.StalePage):
        web_loop.locate(object(), {"page_key": [], "guards": {}}, {"node": "#where"})


@pytest.mark.parametrize(
    ("now", "why"),
    [
        (None, "changed"),
        ([["other"], ["guard"], True], "changed"),
        ([["key"], ["guard"], False], "covered"),
    ],
)
def test_a_stale_or_covered_target_is_refused(now, why):
    class Page:
        def evaluate(self, _script, _arg=None):
            return now

    observed = {"page_key": ["key"], "guards": {"7": ["guard"]}}
    with pytest.raises(web_loop.StalePage, match=why):
        web_loop.locate(Page(), observed, {"node": 7})


def test_jev_unavailable_hands_back_without_acting(monkeypatch):
    page = recorded(RECORDED[0])
    acted: list[str] = []
    monkeypatch.setattr(web_loop, "observe", lambda: page)
    monkeypatch.setattr(decisions, "ask", lambda *_a, **_k: decisions.unavailable("403"))
    monkeypatch.setattr(web_loop, "execute", lambda *a, **k: acted.append("x"))
    import threading

    outcome = web_loop.run("goal", threading.Event())
    assert not outcome.done and outcome.reason.startswith("Jev unavailable") and acted == []


def test_a_page_still_rendering_is_read_again_before_jev_is_asked(monkeypatch):
    page = recorded(RECORDED[0])
    blank = {**page, "actions": [], "text": ""}
    snapshots = iter([blank, blank, page])
    asked: list[str] = []
    monkeypatch.setattr(web_loop, "observe", lambda: next(snapshots))
    monkeypatch.setattr(web_loop.time, "sleep", lambda _s: None)

    def ask(state: str, questions: Any, *_a: Any, **_k: Any) -> decisions.Answers:
        asked.append(state)
        return decisions.unavailable("stop here")

    monkeypatch.setattr(decisions, "ask", ask)
    web_loop.step("goal", web_loop.Outcome())
    assert len(asked) == 1 and page["text"][:40] in asked[0]


def test_a_page_that_never_renders_is_asked_about_once_the_wait_runs_out(monkeypatch):
    blank = {**recorded(RECORDED[0]), "actions": [], "text": ""}
    clock = iter(range(100))
    monkeypatch.setattr(web_loop, "observe", lambda: blank)
    monkeypatch.setattr(web_loop.time, "sleep", lambda _s: None)
    monkeypatch.setattr(web_loop.time, "monotonic", lambda: next(clock))
    monkeypatch.setattr(decisions, "ask", lambda *_a, **_k: decisions.unavailable("stop here"))
    outcome = web_loop.Outcome()
    assert web_loop.step("goal", outcome) is False and outcome.reason.startswith("Jev unavailable")


@pytest.mark.parametrize("path", RECORDED, ids=lambda p: p.stem)
def test_the_state_lists_every_offered_element_as_untrusted_page_data(path):
    page = recorded(path)
    table = web_loop.element_table(page["actions"])
    state = web_loop.state_text("goal", page, [], table)
    untrusted = state[state.index("<untrusted_content>") :]
    for element in table.elements:
        assert f"[{element['index']}] " in untrusted
