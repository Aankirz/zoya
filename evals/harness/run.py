"""The harness evaluation (Phase H): every task in tasks.json through `handle_command`, graded.

    .venv/bin/python evals/harness/run.py LABEL [--only ID,ID] [--group "mac app"]

Speech is captured, every confirmation is answered "cancel" (D96), and the table lands in
logs/harness/LABEL.md with the raw runs in logs/harness/LABEL.json.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import subprocess
import sys
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

os.environ["HF_HUB_OFFLINE"] = "1"
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from zoya import decisions, safety, speech  # noqa: E402
from zoya.config import ECHO_TAIL_S, LOG_DIR, load_env  # noqa: E402

TASKS_FILE = Path(__file__).with_name("tasks.json")
OUT_DIR = LOG_DIR / "harness"
TASK_LIMIT_S = 300.0
STOP_GRACE_S = 30.0
SHELL_TIMEOUT_S = 30.0
REPLY_POLL_S = 0.05
REPLY_WAIT_S = 30.0
TOKENS_PER_PRICE_UNIT = 1_000_000
CENTS_PER_USD = 100
CHARS_PER_TOKEN = 4
PRICES_USD_PER_1M = {
    "gpt-5.6-terra": (2.0, 0.2, 12.0),
    "gpt-5.6-luna": (0.2, 0.02, 1.2),
}
JEV_USD_PER_1M = 0.042
BLANK_PAGE = "about:blank"
MARKER = "zoyaeval"
RUN_ID = f"{secrets.randbelow(9000) + 1000}"
NOTHING_LEFT = ("", "0")


@dataclass
class Run:
    id: str
    group: str
    command: str
    success: bool = False
    steps: int = 0
    model_calls: int = 0
    jev_calls: int = 0
    seconds: float = 0.0
    cents: float = 0.0
    said: list[str] = field(default_factory=list)
    confirmations: list[str] = field(default_factory=list)
    url: str = ""
    failed_checks: list[str] = field(default_factory=list)
    route: str = ""
    error: str = ""
    leftover: str = ""


class Meter:
    def __init__(self) -> None:
        self.run: Run | None = None
        self.channel = safety.claim_voice_channel()

    def count(self, attribute: str, amount: float = 1) -> None:
        if self.run is not None:
            setattr(self.run, attribute, getattr(self.run, attribute) + amount)


meter: Meter


def model_cents(model_id: str, usage: dict[str, int]) -> float:
    price_in, price_cached, price_out = PRICES_USD_PER_1M.get(model_id, (4.0, 4.0, 20.0))
    cached = usage.get("cacheReadInputTokens", 0)
    fresh = max(0, usage.get("inputTokens", 0) - cached)
    usd = fresh * price_in + cached * price_cached + usage.get("outputTokens", 0) * price_out
    return usd / TOKENS_PER_PRICE_UNIT * CENTS_PER_USD


def meter_model_class(cls: Any) -> None:
    original = cls.stream

    async def stream(self: Any, *args: Any, **kwargs: Any) -> Any:
        meter.count("model_calls")
        model_id = str(self.get_config().get("model_id", ""))
        async for event in original(self, *args, **kwargs):
            usage = event.get("metadata", {}).get("usage") if isinstance(event, dict) else None
            if usage:
                meter.count("cents", model_cents(model_id, usage))
            yield event

    cls.stream = stream


def install_meters() -> None:
    from strands.models.openai import OpenAIModel
    from strands.models.openai_responses import OpenAIResponsesModel

    from zoya.agents import step_loop

    for cls in (OpenAIModel, OpenAIResponsesModel):
        meter_model_class(cls)
    original_ask = decisions.ask

    def ask(state: str, questions: Any, *args: Any, **kwargs: Any) -> decisions.Answers:
        meter.count("jev_calls")
        tokens = len(state) / CHARS_PER_TOKEN
        meter.count("cents", tokens * JEV_USD_PER_1M / TOKENS_PER_PRICE_UNIT * CENTS_PER_USD)
        return original_ask(state, questions, *args, **kwargs)

    decisions.ask = ask
    original_before_tool = safety.ConfirmationGate.before_tool

    def before_tool(self: Any, event: Any) -> None:
        meter.count("steps")
        original_before_tool(self, event)

    safety.ConfirmationGate.before_tool = before_tool
    original_step_run = step_loop.run

    def step_run(*args: Any, **kwargs: Any) -> Any:
        outcome = original_step_run(*args, **kwargs)
        meter.count("steps", outcome.steps)
        return outcome

    step_loop.run = step_run


def answer_cancel() -> None:
    deadline = time.monotonic() + REPLY_WAIT_S
    while not safety.awaiting_reply() and time.monotonic() < deadline:
        time.sleep(REPLY_POLL_S)
    time.sleep(ECHO_TAIL_S + REPLY_POLL_S)
    meter.channel.reply("cancel", time.monotonic())


def install_voice() -> None:
    def narrate(text: str) -> None:
        if meter.run is not None and text.strip():
            meter.run.said.append(text)

    def say_and_wait(text: str, _timeout_s: float) -> bool:
        if meter.run is not None:
            meter.run.confirmations.append(text)
        threading.Thread(target=answer_cancel, daemon=True).start()
        return True

    speech.narrate = narrate
    speech.say_and_wait = say_and_wait
    speech.is_speaking = lambda: False


def shell(command: str) -> str:
    try:
        done = subprocess.run(
            command, shell=True, capture_output=True, text=True, timeout=SHELL_TIMEOUT_S
        )
    except subprocess.TimeoutExpired:
        return ""
    return done.stdout.strip()


def browser_url() -> str:
    from zoya.tools import browser

    return browser.ref_page_state()[0]


def reset_browser() -> None:
    from zoya.tools import browser

    try:
        browser.on_page(lambda page: page.goto(BLANK_PAGE))
    except Exception as error:  # noqa: BLE001
        print(f"  browser reset failed: {error}", flush=True)


def failed_checks(task: dict[str, Any], run: Run, token: str) -> list[str]:
    heard = " ".join(run.said)
    asked = " ".join(run.confirmations)
    failed = []
    for check in task["checks"]:
        pattern = {k: v.replace("{token}", token) for k, v in check.items() if isinstance(v, str)}
        if "said" in check:
            ok = len(re.findall(pattern["said"], heard, re.I)) >= check.get("min", 1)
        elif "not_said" in check:
            ok = not re.search(pattern["not_said"], heard, re.I)
        elif "confirm" in check:
            ok = bool(re.search(pattern["confirm"], asked, re.I))
        elif "url" in check:
            ok = bool(re.search(pattern["url"], run.url, re.I))
        else:
            ok = bool(re.search(pattern["match"], shell(pattern["shell"]), re.I))
        if not ok:
            failed.append(json.dumps(check, ensure_ascii=False))
    return failed


def execute(command: str, run: Run) -> None:
    from zoya import orchestrator

    outcome: dict[str, Any] = {}

    def work() -> None:
        try:
            outcome["result"] = orchestrator.handle_command(command)
        except Exception as error:  # noqa: BLE001
            outcome["error"] = f"{type(error).__name__}: {error}"

    worker = threading.Thread(target=work, daemon=True)
    worker.start()
    worker.join(TASK_LIMIT_S)
    if worker.is_alive():
        orchestrator.stop_task()
        worker.join(STOP_GRACE_S)
        run.error = f"over {TASK_LIMIT_S:.0f} s, stopped"
    if result := outcome.get("result"):
        run.route = f"{result.decision.route}/{result.decision.source}/{result.decision.skill}"
        if result.spoken and result.spoken not in run.said:
            run.said.append(result.spoken)
    run.error = run.error or outcome.get("error", "")


def run_task(task: dict[str, Any], index: int) -> Run:
    from zoya import orchestrator

    token = f"{MARKER}{RUN_ID}{index:02d}"
    command = task["command"].replace("{token}", token)
    run = Run(task["id"], task["group"], command)
    orchestrator._conversation.clear()
    web = any("url" in check for check in task["checks"]) or task["group"] != "mac app"
    if web:
        reset_browser()
    for step in task.get("setup", []):
        shell(step.replace("{token}", token))
    meter.run = run
    started = time.monotonic()
    execute(command, run)
    run.seconds = round(time.monotonic() - started, 1)
    meter.run = None
    if any("url" in check for check in task["checks"]):
        run.url = browser_url()
    run.failed_checks = failed_checks(task, run, token)
    run.success = not run.failed_checks and not run.error
    run.cents = round(run.cents, 3)
    for step in task.get("teardown", []):
        shell(step.replace("{token}", token))
    if probe := task.get("leftover"):
        left = shell(probe.replace("{token}", token))
        run.leftover = "" if left in NOTHING_LEFT else f"{token}: {left}"
    return run


def rate(runs: list[Run]) -> str:
    return f"{sum(r.success for r in runs)}/{len(runs)}"


def table(label: str, runs: list[Run]) -> str:
    lines = [
        f"# Harness evaluation: {label}",
        "",
        "| task | group | success | steps | LM calls | Jev calls | seconds | cents |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for r in runs:
        mark = "yes" if r.success else "no"
        lines.append(
            f"| {r.id} | {r.group} | {mark} | {r.steps} | {r.model_calls} | {r.jev_calls} "
            f"| {r.seconds} | {r.cents} |"
        )
    lines += ["", f"**All: {rate(runs)}**", ""]
    for group in dict.fromkeys(r.group for r in runs):
        members = [r for r in runs if r.group == group]
        lines.append(f"- {group}: {rate(members)}")
    lines += [
        "",
        f"Totals: {sum(r.model_calls for r in runs)} LM calls, "
        f"{sum(r.jev_calls for r in runs)} Jev calls, "
        f"{round(sum(r.seconds for r in runs))} s, {round(sum(r.cents for r in runs), 2)} cents",
    ]
    leftovers = [r.leftover for r in runs if r.leftover]
    lines += ["", f"Leftovers not removed: {'; '.join(leftovers) or 'none'}"]
    return "\n".join(lines) + "\n"


def select(tasks: list[dict[str, Any]], only: str, group: str) -> list[dict[str, Any]]:
    wanted = {name.strip() for name in only.split(",") if name.strip()}
    return [
        task
        for task in tasks
        if (not wanted or task["id"] in wanted) and (not group or task["group"] == group)
    ]


def main() -> int:
    global meter
    parser = argparse.ArgumentParser()
    parser.add_argument("label")
    parser.add_argument("--only", default="")
    parser.add_argument("--group", default="")
    args = parser.parse_args()
    load_env()
    from zoya import aws

    aws.load_provider_secrets()
    meter = Meter()
    install_meters()
    install_voice()
    decisions.warm()
    tasks = select(json.loads(TASKS_FILE.read_text(encoding="utf-8")), args.only, args.group)
    runs = []
    for index, task in enumerate(tasks):
        runs.append(run_task(task, index))
        last = runs[-1]
        print(f"> {last.id}: {last.command}", flush=True)
        print(f"  {'PASS' if last.success else 'FAIL'} {last.seconds}s {last.route}", flush=True)
        print(f"  said: {' | '.join(last.said)[:400]}", flush=True)
        if last.leftover:
            print(f"  LEFTOVER, not removed: {last.leftover}", flush=True)
        if last.confirmations or last.failed_checks or last.error:
            print(f"  asked: {last.confirmations} failed: {last.failed_checks} {last.error}")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / f"{args.label}.json").write_text(
        json.dumps([asdict(r) for r in runs], indent=1, ensure_ascii=False), encoding="utf-8"
    )
    report = table(args.label, runs)
    (OUT_DIR / f"{args.label}.md").write_text(report, encoding="utf-8")
    print(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
