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

import http.client
import json
import logging
import os
import threading
import time
import urllib.parse
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from typesafe_sdk import Choice, Noul, Score

from zoya.config import (
    JEV_BACKOFF_S,
    JEV_DEADLINE_S,
    JEV_RETRY_STATUS,
    JEV_TIMEOUT_S,
    license_key,
    relay_url,
)

log = logging.getLogger(__name__)

MS_PER_S = 1000
Question = Noul | Choice | Score
GATEWAY_TYPES = {"noul": "boolean"}
HTTP_ERROR = 400
POOL_MAX = 4
LOOPBACK_HOSTS = ("localhost", "127.0.0.1")
_pool: list[http.client.HTTPConnection] = []
_pool_lock = threading.Lock()
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
    if os.environ.get("TYPESAFE_API_KEY") and not license_key():
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


def _endpoint() -> tuple[str, str, str]:
    """(host, path, key) of the evaluate endpoint: the relay with a license, else the gateway."""
    license = license_key()
    base = f"{relay_url()}/v1" if license else os.environ.get("AI_GATEWAY_BASE_URL", "").rstrip("/")
    key = license or os.environ.get("AI_GATEWAY_API_KEY", "")
    if not base or not key:
        raise _Fatal("AI_GATEWAY_BASE_URL or AI_GATEWAY_API_KEY is not set")
    parsed = urllib.parse.urlparse(base)
    secure = parsed.scheme == "https" or (
        parsed.scheme == "http" and parsed.hostname in LOOPBACK_HOSTS
    )
    if not secure or not parsed.hostname:
        raise _Fatal(f"the Jev endpoint must be an https URL, got {base!r}")
    port = f":{parsed.port}" if parsed.port else ""
    return f"{parsed.hostname}{port}", f"{parsed.path}/evaluate", key


def _connect(host: str, timeout_s: float) -> http.client.HTTPConnection:
    if host.split(":")[0] in LOOPBACK_HOSTS:
        return http.client.HTTPConnection(host, timeout=timeout_s)
    return http.client.HTTPSConnection(host, timeout=timeout_s)


def _take(host: str, timeout_s: float) -> tuple[http.client.HTTPConnection, bool]:
    """An idle kept-alive connection to `host`, or a new one. True = it was already open."""
    with _pool_lock:
        while _pool:
            connection = _pool.pop()
            if connection.host == host:
                connection.timeout = timeout_s
                return connection, True
            connection.close()
    return _connect(host, timeout_s), False


def _give_back(connection: http.client.HTTPConnection) -> None:
    with _pool_lock:
        if len(_pool) < POOL_MAX:
            _pool.append(connection)
            return
    connection.close()


def warm() -> None:
    """Open a connection before the first question, so no answer pays the handshake.

    Measured on this Mac: the first call of a process took 948 ms against 485 ms for the calls
    after it, and a connection kept open took 68 ms off every call as well as removing that
    first-call penalty. Safe to call from any thread and safe to fail.
    """
    try:
        host, _path, _key = _endpoint()
        connection, _reused = _take(host, JEV_TIMEOUT_S)
        connection.connect()
    except (_Fatal, OSError) as error:
        log.info("jev pre-warm skipped (%s)", error)
        return
    _give_back(connection)


def _send(host: str, path: str, key: str, body: bytes, timeout_s: float) -> dict[str, Any]:
    """One POST over a kept-alive connection, retried once if the pooled one was already dead."""
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    for attempt in (1, 2):
        connection, reused = _take(host, timeout_s)
        try:
            connection.request("POST", path, body=body, headers=headers)
            response = connection.getresponse()
            status, payload = response.status, response.read()
        except (http.client.HTTPException, TimeoutError, OSError) as error:
            connection.close()
            if reused and attempt == 1:
                continue
            raise _Retryable(f"{type(error).__name__}: {error}") from error
        _give_back(connection)
        return _reply(status, payload)
    raise _Retryable("no usable connection")


def _reply(status: int, payload: bytes) -> dict[str, Any]:
    if status >= HTTP_ERROR:
        detail = payload[:200].decode(errors="replace")
        if status in JEV_RETRY_STATUS:
            raise _Retryable(f"HTTP {status}: {detail}")
        raise _Fatal(f"HTTP {status}: {detail}")
    try:
        body = json.loads(payload)
    except json.JSONDecodeError as error:
        raise _Fatal(f"unreadable reply: {error}") from error
    answers = body.get("answers")
    if not isinstance(answers, dict):
        raise _Fatal(f"no answers in reply: {str(body)[:160]}")
    return answers


def _gateway(state: str, questions: Mapping[str, Question], timeout_s: float) -> dict[str, Any]:
    host, path, key = _endpoint()
    body = json.dumps(
        {
            "model": os.environ.get("JEV_MODEL") or "typesafe-ai/jev",
            "state": state,
            "questions": {name: _to_gateway(q) for name, q in questions.items()},
        }
    ).encode()
    return _send(host, path, key, body, timeout_s)


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
