"""The only module that talks to Jev (D74, D81, D82).

One function: state plus a batch of questions in, typed answers out. Questions are
written in TypeSafe's native shape (`Noul` / `Choice` / `Score` from typesafe_sdk);
the Vercel AI Gateway's `boolean` / `probability` dialect is adapted behind this
interface, so callers never learn which provider answered.

Batching is the whole point. Phase A measured one question at 592 ms and ten at
593 ms from this Mac, against a ~430 ms round-trip floor that no state-size or
question-count tuning recovers. One call carrying every question a decision point
needs; never one call per question.

Nothing here raises into the voice loop. A timeout, a 429, an unreachable gateway
or a malformed reply all come back as an unavailable `Answers`, which is falsey,
so the caller falls back rather than hanging (D73).

APIs:
- https://docs.typesafe.ai/introduction/quickstart (native `state` + `questions`,
  answers carrying `noul` / `choice` / `score`)
- https://vercel.com/docs/ai-gateway (gateway `/v1/evaluate`; `boolean` questions
  answer with `probability`)
"""

from __future__ import annotations

import json
import logging
import os
import time
import urllib.error
import urllib.request
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from typesafe_sdk import Choice, Noul, Score

from zoya.config import JEV_BACKOFF_S, JEV_DEADLINE_S, JEV_RETRY_STATUS, JEV_TIMEOUT_S

log = logging.getLogger(__name__)

MS_PER_S = 1000
Question = Noul | Choice | Score
GATEWAY_TYPES = {"noul": "boolean"}
GATEWAY_PROBABILITY_FIELD = {"boolean": "probability"}


@dataclass(frozen=True)
class Pick:
    name: str
    confidence: float
    probabilities: dict[str, float]


@dataclass(frozen=True)
class Answers:
    answers: dict[str, dict[str, Any]] = field(default_factory=dict)
    latency_ms: int = 0
    reason: str = ""

    def __bool__(self) -> bool:
        return not self.reason

    def noul(self, key: str, default: float = 0.0) -> float:
        answer = self.answers.get(key)
        return float(answer["noul"]) if answer and "noul" in answer else default

    def score(self, key: str, default: float = 0.0) -> float:
        answer = self.answers.get(key)
        return float(answer["score"]) if answer and "score" in answer else default

    def pick(self, key: str) -> Pick | None:
        answer = self.answers.get(key)
        if not answer or "choice" not in answer:
            return None
        probabilities = {str(k): float(v) for k, v in answer.get("probabilities", {}).items()}
        confidence = float(answer.get("confidence", probabilities.get(answer["choice"], 0.0)))
        return Pick(str(answer["choice"]), confidence, probabilities)


def unavailable(reason: str, latency_ms: int = 0) -> Answers:
    return Answers({}, latency_ms, reason or "jev unavailable")


def ask(
    state: str,
    questions: Mapping[str, Question],
    deadline_s: float = JEV_DEADLINE_S,
) -> Answers:
    """One batched Jev call. Never raises: an unavailable answer is falsey."""
    if not questions:
        return Answers()
    started = time.monotonic()
    deadline = started + deadline_s
    attempt = 0
    while True:
        try:
            raw = _evaluate(state, questions, min(JEV_TIMEOUT_S, deadline - time.monotonic()))
            return Answers(_normalise(raw), _ms(started))
        except _Retryable as error:
            delay = JEV_BACKOFF_S * 2**attempt
            attempt += 1
            if time.monotonic() + delay >= deadline:
                log.warning("jev gave up after %d attempts: %s", attempt, error)
                return unavailable(str(error), _ms(started))
            time.sleep(delay)
        except _Fatal as error:
            log.warning("jev unavailable: %s", error)
            return unavailable(str(error), _ms(started))


class _Retryable(Exception):
    pass


class _Fatal(Exception):
    pass


def _ms(started: float) -> int:
    return round((time.monotonic() - started) * MS_PER_S)


def _evaluate(state: str, questions: Mapping[str, Question], timeout_s: float) -> dict[str, Any]:
    if timeout_s <= 0:
        raise _Retryable("no time left")
    if os.environ.get("TYPESAFE_API_KEY"):
        return _native(state, questions, timeout_s)
    return _gateway(state, questions, timeout_s)


def _native(state: str, questions: Mapping[str, Question], timeout_s: float) -> dict[str, Any]:
    from typesafe_sdk import TypeSafeAPIError, TypeSafeClient, TypeSafeRateLimitError

    client = TypeSafeClient(timeout=timeout_s)
    try:
        response = client.system_one(
            state=state, questions=dict(questions), model=os.environ.get("JEV_MODEL") or None
        )
    except TypeSafeRateLimitError as error:
        raise _Retryable(f"rate limited: {error}") from error
    except TypeSafeAPIError as error:
        if getattr(error, "status_code", 0) in JEV_RETRY_STATUS:
            raise _Retryable(str(error)) from error
        raise _Fatal(str(error)) from error
    except Exception as error:  # noqa: BLE001 — every failure degrades, none reaches the loop
        raise _Fatal(f"{type(error).__name__}: {error}") from error
    return {name: answer.model_dump() for name, answer in response.answers.items()}


def _gateway(state: str, questions: Mapping[str, Question], timeout_s: float) -> dict[str, Any]:
    base = os.environ.get("AI_GATEWAY_BASE_URL", "").rstrip("/")
    key = os.environ.get("AI_GATEWAY_API_KEY", "")
    if not base or not key:
        raise _Fatal("AI_GATEWAY_BASE_URL or AI_GATEWAY_API_KEY is not set")
    body = json.dumps(
        {
            "model": os.environ.get("JEV_MODEL") or "typesafe-ai/jev",
            "state": state,
            "questions": {name: _to_gateway(q) for name, q in questions.items()},
        }
    ).encode()
    request = urllib.request.Request(
        f"{base}/evaluate",
        data=body,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_s) as response:
            payload = json.loads(response.read())
    except urllib.error.HTTPError as error:
        detail = error.read()[:200].decode(errors="replace")
        if error.code in JEV_RETRY_STATUS:
            raise _Retryable(f"HTTP {error.code}: {detail}") from error
        raise _Fatal(f"HTTP {error.code}: {detail}") from error
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        raise _Retryable(f"{type(error).__name__}: {error}") from error
    except json.JSONDecodeError as error:
        raise _Fatal(f"unreadable reply: {error}") from error
    answers = payload.get("answers")
    if not isinstance(answers, dict):
        raise _Fatal(f"no answers in reply: {str(payload)[:160]}")
    return answers


def _to_gateway(question: Question) -> dict[str, Any]:
    sent = question.model_dump(exclude_none=True)
    sent["type"] = GATEWAY_TYPES.get(sent.get("type", ""), sent.get("type", ""))
    return sent


def _normalise(answers: dict[str, Any]) -> dict[str, dict[str, Any]]:
    normalised = {}
    for name, answer in answers.items():
        if not isinstance(answer, dict):
            continue
        sent = GATEWAY_PROBABILITY_FIELD.get(answer.get("type", ""))
        if sent:
            answer = {**answer, "type": "noul", "noul": answer.get(sent)}
            answer.pop(sent, None)
        normalised[name] = answer
    return normalised
