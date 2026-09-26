"""Production P1 — the relay hop: Jev p50 and brain time-to-first-token, direct vs relay.

Needs OPENAI_API_KEY and AI_GATEWAY_API_KEY in .env (direct) and a license key (relay):
    python scripts/spikes/relay_latency.py --license-file key.txt [--relay-url URL] [--calls 20]
"""

from __future__ import annotations

import argparse
import os
import statistics
import time

import openai
from typesafe_sdk import Noul

from zoya import decisions
from zoya.config import LICENSE_KEY_ENV, RELAY_URL_ENV, load_env, relay_url

MS_PER_S = 1000
PACE_S = 1.0
STATE = "App: Mail. Window: New Message. Button: Send | Button: Cancel | TextField: Subject"
QUESTIONS = {
    "worked": Noul(instructions="Did the last action work?"),
    "done": Noul(instructions="Is the task finished?"),
}
PROMPT = "In one sentence, why is the sky blue?"


def _mode(license: str, via_relay: bool) -> None:
    if via_relay:
        os.environ[LICENSE_KEY_ENV] = license
    else:
        os.environ.pop(LICENSE_KEY_ENV, None)


def jev_ms(calls: int) -> list[int]:
    decisions.warm()
    decisions.ask(STATE, QUESTIONS)
    timings = []
    for _ in range(calls):
        answers = decisions.ask(STATE, QUESTIONS)
        if answers:
            timings.append(answers.latency_ms)
        time.sleep(PACE_S)
    return timings


def brain_ttft_ms(client: openai.OpenAI, calls: int) -> list[int]:
    timings = []
    for _ in range(calls):
        started = time.monotonic()
        stream = client.responses.create(
            model=os.environ["BRAIN_MODEL"], input=PROMPT, store=False, stream=True
        )
        for event in stream:
            if event.type == "response.output_text.delta":
                timings.append(round((time.monotonic() - started) * MS_PER_S))
                break
        stream.close()
    return timings


def _report(name: str, timings: list[int]) -> None:
    if not timings:
        print(f"{name}: no successful calls")
        return
    p50 = statistics.median(timings)
    print(f"{name}: n={len(timings)} p50={p50:.0f} ms min={min(timings)} max={max(timings)}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--license-file", required=True)
    parser.add_argument("--relay-url", default="")
    parser.add_argument("--calls", type=int, default=20)
    parser.add_argument("--brain-calls", type=int, default=5)
    args = parser.parse_args()
    load_env()
    if args.relay_url:
        os.environ[RELAY_URL_ENV] = args.relay_url
    with open(args.license_file) as key_file:
        license = key_file.read().split()[-1]
    clients = {
        False: openai.OpenAI(api_key=os.environ["OPENAI_API_KEY"]),
        True: openai.OpenAI(api_key=license, base_url=f"{relay_url()}/v1"),
    }
    for via_relay in (False, True):
        label = f"relay {relay_url()}" if via_relay else "direct"
        _mode(license, via_relay)
        _report(f"jev [{label}]", jev_ms(args.calls))
        _report(f"brain ttft [{label}]", brain_ttft_ms(clients[via_relay], args.brain_calls))


if __name__ == "__main__":
    main()
