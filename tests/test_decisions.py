"""Jev's failure handling (D37, D73): nothing in decisions.py may raise into the voice loop, and
every question a decision point needs must travel in one request."""

from __future__ import annotations

import io
import json
import urllib.error

import pytest
from typesafe_sdk import Choice, Noul

from zoya import decisions

STATE = "The user said: 'that's enough'."
QUESTIONS = {
    "is_stop": Noul(instructions="The speaker is telling the assistant to stop."),
    "want": Choice(instructions="What now?", criteria={"stop": "stop", "go": "carry on"}),
}


@pytest.fixture(autouse=True)
def gateway(monkeypatch):
    monkeypatch.setenv("AI_GATEWAY_BASE_URL", "https://gateway.test/v1")
    monkeypatch.setenv("AI_GATEWAY_API_KEY", "test-key")
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    monkeypatch.setattr(decisions.time, "sleep", lambda _seconds: None)


def reply(payload: dict) -> io.BytesIO:
    body = io.BytesIO(json.dumps(payload).encode())
    body.__enter__ = lambda: body
    body.__exit__ = lambda *_args: False
    return body


def http_error(code: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError(
        "https://gateway.test/v1/evaluate", code, "no", {}, io.BytesIO(b"")
    )


def test_every_question_travels_in_one_request(monkeypatch):
    sent = []

    def urlopen(request, timeout):  # noqa: ANN001, ARG001
        sent.append(json.loads(request.data))
        return reply({"answers": {"is_stop": {"type": "boolean", "probability": 0.9}}})

    monkeypatch.setattr(decisions.urllib.request, "urlopen", urlopen)
    decisions.ask(STATE, QUESTIONS)
    assert len(sent) == 1
    assert set(sent[0]["questions"]) == {"is_stop", "want"}


def test_gateway_boolean_reads_back_as_a_noul(monkeypatch):
    monkeypatch.setattr(
        decisions.urllib.request,
        "urlopen",
        lambda request, timeout: reply(  # noqa: ANN001, ARG005
            {
                "answers": {
                    "is_stop": {"type": "boolean", "probability": 0.97},
                    "want": {
                        "type": "choice",
                        "choice": "stop",
                        "confidence": 0.88,
                        "probabilities": {"stop": 0.88, "go": 0.12},
                    },
                }
            }
        ),
    )
    answers = decisions.ask(STATE, QUESTIONS)
    assert answers
    assert answers.noul("is_stop") == pytest.approx(0.97)
    assert answers.pick("want").name == "stop"
    assert answers.pick("want").confidence == pytest.approx(0.88)


def test_noul_is_sent_as_the_gateway_boolean_dialect(monkeypatch):
    sent = []

    def urlopen(request, timeout):  # noqa: ANN001, ARG001
        sent.append(json.loads(request.data))
        return reply({"answers": {}})

    monkeypatch.setattr(decisions.urllib.request, "urlopen", urlopen)
    decisions.ask(STATE, {"is_stop": QUESTIONS["is_stop"]})
    assert sent[0]["questions"]["is_stop"]["type"] == "boolean"


def test_rate_limit_backs_off_then_degrades_instead_of_raising(monkeypatch):
    attempts = []

    def urlopen(request, timeout):  # noqa: ANN001, ARG001
        attempts.append(1)
        raise http_error(429)

    monkeypatch.setattr(decisions.urllib.request, "urlopen", urlopen)
    answers = decisions.ask(STATE, QUESTIONS)
    assert not answers
    assert len(attempts) > 1
    assert "429" in answers.reason


def test_unreachable_gateway_degrades_instead_of_raising(monkeypatch):
    def urlopen(request, timeout):  # noqa: ANN001, ARG001
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr(decisions.urllib.request, "urlopen", urlopen)
    answers = decisions.ask(STATE, QUESTIONS)
    assert not answers
    assert answers.noul("is_stop", default=0.5) == 0.5
    assert answers.pick("want") is None


def test_unauthorised_is_not_retried(monkeypatch):
    attempts = []

    def urlopen(request, timeout):  # noqa: ANN001, ARG001
        attempts.append(1)
        raise http_error(401)

    monkeypatch.setattr(decisions.urllib.request, "urlopen", urlopen)
    assert not decisions.ask(STATE, QUESTIONS)
    assert len(attempts) == 1


def test_malformed_reply_degrades_instead_of_raising(monkeypatch):
    monkeypatch.setattr(
        decisions.urllib.request,
        "urlopen",
        lambda request, timeout: reply({"oops": True}),  # noqa: ANN001, ARG005
    )
    assert not decisions.ask(STATE, QUESTIONS)


def test_missing_credentials_degrade_instead_of_raising(monkeypatch):
    monkeypatch.delenv("AI_GATEWAY_API_KEY")
    assert not decisions.ask(STATE, QUESTIONS)


def test_no_questions_needs_no_call(monkeypatch):
    def urlopen(request, timeout):  # noqa: ANN001, ARG001
        raise AssertionError("asked Jev with no questions")

    monkeypatch.setattr(decisions.urllib.request, "urlopen", urlopen)
    assert decisions.ask(STATE, {})
