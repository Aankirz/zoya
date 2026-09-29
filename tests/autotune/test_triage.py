"""Failure causes and the redacted triage record a cloud session reads."""

from __future__ import annotations

import json

import pytest

from evals.autotune import triage


def run(success: bool = False, **fields: object) -> dict:
    return {"id": "t", "group": "no-code site", "success": success, **fields}


@pytest.mark.parametrize(
    ("task", "failed", "expected"),
    [
        ({}, {"error": "over 300 s, stopped"}, triage.TIMEOUT),
        ({}, {"error": "RuntimeError: boom"}, triage.CRASH),
        ({}, {"confirmations": ["Submit search?"]}, triage.FALSE_ASK),
        ({"stakes": "money"}, {"said": ["I couldn't find it"]}, triage.NEVER_REACHED_GATE),
        (
            {"stakes": "submit"},
            {"confirmations": ["Shall I enter the email?"], "failed_checks": ['{"confirm": "x"}']},
            triage.ASK_WORDING,
        ),
        ({}, {"said": ["Goodreads is showing its sign-in page."]}, triage.WALL),
        ({}, {"failed_checks": ['{"url": "wikipedia"}']}, triage.WRONG_PAGE),
        ({}, {"failed_checks": ['{"said": "Dune"}']}, triage.WRONG_ANSWER),
    ],
)
def test_cause_reads_only_what_the_harness_recorded(task: dict, failed: dict, expected: str):
    assert triage.cause(task, run(**failed)) == expected


def test_a_passing_run_has_no_cause() -> None:
    assert triage.cause({}, run(True)) == triage.PASSED


PRIVATE = {
    "said": [
        "Hi Priya, write to owner@private.example or call 919876543210.",
        "The harness@example.com address is signed up.",
    ],
    "confirmations": ["Subscribe owner@private.example? Order 12345678901234."],
    "url": "https://user:pw@www.shop.example:8443/account/orders?id=98765&mail=a@b.co#frag",
    "failed_checks": ['{"confirm": "subscribe|sign ?up"}'],
    "error": "ValueError: card 4242424242424242 for owner@private.example",
    "tools": [
        'browser_type {"text": "owner@private.example", "ref": "e12"}',
        'browser_click {"ref": "e1"}',
        'browser_type {"text": "hunter2"}',
        "browser_task {}",
        'browser_snapshot {"q": "secret"}',
        'browser_press {"key": "Enter"}',
    ],
}


def test_a_record_never_carries_tool_inputs_queries_private_emails_or_long_digit_runs() -> None:
    record = triage.record({"stakes": "submit"}, run(**PRIVATE), "FAIL", [False, True, False])
    text = json.dumps(record, ensure_ascii=False)
    for secret in ("private.example", "919876543210", "12345678901234", "4242424242424242"):
        assert secret not in text
    for tool_input in ("hunter2", "e12", '"ref"', "Enter", "secret"):
        assert tool_input not in text
    for query in ("98765", "mail=", "frag", "user", "pw@"):
        assert query not in text
    assert record["tools"] == [
        "browser_click",
        "browser_type",
        "browser_task",
        "browser_snapshot",
        "browser_press",
    ]
    assert record["url"] == "https://www.shop.example:8443/account/orders"
    assert "harness@example.com" in record["said"]
    assert record["history"] == "FPF" and record["class"] == "FAIL"
    assert "?" not in record["url"]
    assert record["cause"] == triage.CRASH


def test_long_text_is_cut_to_its_tail_after_redaction() -> None:
    said = ["x" * 400 + " mail owner@private.example"]
    record = triage.record({}, run(said=said, error="E" * 500), "FAIL", [])
    assert len(record["said"]) == triage.TEXT_CHARS and record["said"].endswith("[email]")
    assert len(record["error"]) == triage.TEXT_CHARS
    assert "private" not in record["said"]


def test_a_missing_or_odd_url_is_kept_safe() -> None:
    assert triage.strip_query("") == ""
    assert triage.strip_query("about:blank") == "about:blank"
    assert triage.strip_query("https://example.com:bad/p?q=1") == "https://example.com/p"


def test_a_held_out_task_shows_pass_or_fail_only() -> None:
    assert triage.held_out_record("boat-price", False) == {
        "task": "boat-price",
        "held_out": True,
        "result": "fail",
    }
    assert triage.held_out_record("boat-price", True)["result"] == "pass"
