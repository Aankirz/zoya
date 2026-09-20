"""Jev's failure handling (D37, D73): nothing in decisions.py may raise into the voice loop, and
every question a decision point needs must travel in one request.

The transport is a pooled keep-alive connection, so these fakes stand in for one: a dead pooled
connection must be retried on a fresh one, and a connection that answered must go back to the
pool rather than being thrown away.
"""

from __future__ import annotations

import http.client
import json

import pytest
from typesafe_sdk import Choice, Noul

from zoya import decisions

STATE = "The user said: 'that's enough'."
QUESTIONS = {
    "is_stop": Noul(instructions="The speaker is telling the assistant to stop."),
    "want": Choice(instructions="What now?", criteria={"stop": "stop", "go": "carry on"}),
}
OK = {"answers": {"is_stop": {"type": "boolean", "probability": 0.9}}}


class FakeResponse:
    def __init__(self, status: int, payload: bytes) -> None:
        self.status = status
        self._payload = payload

    def read(self) -> bytes:
        return self._payload


class FakeConnection:
    """One connection. `answer` is a callable taking the decoded body and returning a response."""

    def __init__(self, host: str, timeout: float = 0.0) -> None:
        self.host = host
        self.timeout = timeout
        self.closed = False
        self.connects = 0

    def connect(self) -> None:
        self.connects += 1

    def request(self, method: str, path: str, body: bytes, headers: dict) -> None:
        self.sent = json.loads(body)
        self.method, self.path, self.headers = method, path, headers

    def getresponse(self) -> FakeResponse:
        return _behaviour["answer"](self.sent)

    def close(self) -> None:
        self.closed = True


_behaviour: dict = {}


@pytest.fixture(autouse=True)
def gateway(monkeypatch):
    monkeypatch.setenv("AI_GATEWAY_BASE_URL", "https://gateway.test/v1")
    monkeypatch.setenv("AI_GATEWAY_API_KEY", "test-key")
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    monkeypatch.setattr(decisions.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(decisions, "_pool", [])
    made: list[FakeConnection] = []

    def build(host, timeout=0.0):  # noqa: ANN001, ANN202
        made.append(FakeConnection(host, timeout))
        return made[-1]

    monkeypatch.setattr(decisions.http.client, "HTTPSConnection", build)
    _behaviour["answer"] = lambda _body: FakeResponse(200, json.dumps(OK).encode())
    return made


def answers_with(payload: dict, status: int = 200) -> None:
    _behaviour["answer"] = lambda _body: FakeResponse(status, json.dumps(payload).encode())


def raises(error: Exception) -> None:
    def boom(_body):  # noqa: ANN001, ANN202
        raise error

    _behaviour["answer"] = boom


def test_every_question_travels_in_one_request(gateway):
    decisions.ask(STATE, QUESTIONS)

    assert len(gateway) == 1
    assert set(gateway[0].sent["questions"]) == {"is_stop", "want"}


def test_the_request_goes_to_the_evaluate_path_with_the_key(gateway):
    decisions.ask(STATE, QUESTIONS)

    assert (gateway[0].host, gateway[0].path) == ("gateway.test", "/v1/evaluate")
    assert gateway[0].headers["Authorization"] == "Bearer test-key"


def test_gateway_boolean_reads_back_as_a_noul():
    answers_with(
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
    )

    answers = decisions.ask(STATE, QUESTIONS)

    assert answers
    assert answers.noul("is_stop") == pytest.approx(0.97)
    assert answers.pick("want").name == "stop"
    assert answers.pick("want").confidence == pytest.approx(0.88)


def test_noul_is_sent_as_the_gateway_boolean_dialect(gateway):
    decisions.ask(STATE, {"is_stop": QUESTIONS["is_stop"]})

    assert gateway[0].sent["questions"]["is_stop"]["type"] == "boolean"


def test_rate_limit_backs_off_then_degrades_instead_of_raising():
    tries = []
    _behaviour["answer"] = lambda _body: (
        tries.append(1),
        FakeResponse(429, b"{}"),
    )[1]

    answers = decisions.ask(STATE, QUESTIONS)

    assert not answers
    assert len(tries) > 1, "a 429 is backed off and retried"
    assert "429" in answers.reason


def test_unreachable_gateway_degrades_instead_of_raising():
    raises(OSError("connection refused"))

    answers = decisions.ask(STATE, QUESTIONS)

    assert not answers
    assert answers.noul("is_stop", default=0.5) == 0.5
    assert answers.pick("want") is None


def test_unauthorised_is_not_retried(gateway):
    answers_with({}, status=401)

    assert not decisions.ask(STATE, QUESTIONS)
    assert len(gateway) == 1


def test_malformed_reply_degrades_instead_of_raising():
    answers_with({"oops": True})

    assert not decisions.ask(STATE, QUESTIONS)


def test_missing_credentials_degrade_instead_of_raising(monkeypatch):
    monkeypatch.delenv("AI_GATEWAY_API_KEY")

    assert not decisions.ask(STATE, QUESTIONS)


def test_no_questions_needs_no_call(gateway):
    assert decisions.ask(STATE, {})
    assert gateway == []


# --- The pooled connection ----------------------------------------------------------------------


def test_a_connection_that_answered_is_kept_for_the_next_question(gateway):
    decisions.ask(STATE, QUESTIONS)
    decisions.ask(STATE, QUESTIONS)

    assert len(gateway) == 1, "the second question must reuse the first connection"
    assert not gateway[0].closed


def test_a_dead_pooled_connection_is_retried_once_on_a_fresh_one(gateway):
    decisions.ask(STATE, QUESTIONS)
    calls = {"n": 0}

    def once_dead(_body):  # noqa: ANN001, ANN202
        calls["n"] += 1
        if calls["n"] == 1:
            raise http.client.RemoteDisconnected("server closed it")
        return FakeResponse(200, json.dumps(OK).encode())

    _behaviour["answer"] = once_dead

    assert decisions.ask(STATE, QUESTIONS)
    assert len(gateway) == 2, "a stale kept-alive connection is replaced, not reported as failure"
    assert gateway[0].closed


def test_a_fresh_connection_that_fails_is_not_retried_on_another_fresh_one(gateway):
    """Only a connection that came back from the pool may be stale; a new one failing is real."""
    raises(http.client.RemoteDisconnected("server closed it"))

    assert not decisions.ask(STATE, QUESTIONS, deadline_s=0.1)
    assert len(gateway) == 1


def test_warm_opens_a_connection_the_first_question_then_reuses(gateway):
    decisions.warm()

    assert len(gateway) == 1
    assert gateway[0].connects == 1

    decisions.ask(STATE, QUESTIONS)

    assert len(gateway) == 1, "the warmed connection is the one the first question travels on"


def test_warm_never_raises_when_the_gateway_is_not_configured(monkeypatch):
    monkeypatch.delenv("AI_GATEWAY_API_KEY")

    decisions.warm()


def test_the_pool_never_grows_without_bound(gateway):
    for _ in range(decisions.POOL_MAX + 3):
        decisions._give_back(FakeConnection("gateway.test"))

    assert len(decisions._pool) == decisions.POOL_MAX
