"""S4-Web evaluation: fresh web tasks through `handle_command`, headless, graded on the outcome.

    .venv/bin/python -m evals.web.run LABEL --set dev|heldout [--only ID,ID]

Zoya's real brain, router, Jev and browser tools run against live public sites, in a headless
Chrome on a fresh temporary profile (never the owner's, never Zoya's own profile). Anything that
would touch the Mac outside that browser (apps, screen, media keys, notes, memory writes) gets a
refusal instead. Every confirmation is answered "cancel" (D96). Results land in
logs/web/LABEL.json and LABEL.md; spend is appended to logs/web/spend.jsonl.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import sys
import tempfile
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

os.environ["HF_HUB_OFFLINE"] = "1"
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from zoya import decisions, safety, speech  # noqa: E402
from zoya.config import ECHO_TAIL_S, LOG_DIR, load_env  # noqa: E402

WEB_DIR = Path(__file__).parent
OUT_DIR = LOG_DIR / "web"
SPEND_LOG = OUT_DIR / "spend.jsonl"
TASK_LIMIT_S = 150.0
STOP_GRACE_S = 20.0
REPLY_POLL_S = 0.05
REPLY_WAIT_S = 30.0
PER_MILLION = 1_000_000
CENTS_PER_USD = 100
CHARS_PER_TOKEN = 4
PRICES_USD_PER_1M = {
    "gpt-5.6-terra": (2.0, 0.2, 12.0),
    "gpt-5.6-luna": (0.2, 0.02, 1.2),
}
UNKNOWN_PRICE_USD_PER_1M = (4.0, 4.0, 20.0)
JEV_USD_PER_1M = 0.042
TINYFISH_USD_PER_CALL = 0.001
PAID_SEARCH_TOOLS = ("web_search", "web_fetch")
BLANK_PAGE = "about:blank"
HEADLESS_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/155.0.0.0 Safari/537.36"
)
REAL_TOOL_PREFIXES = ("browser_",)
REAL_TOOLS = frozenset(
    {"web_search", "web_fetch", "narrate", "skills", "open_url", "get_weather", "get_time"}
)
REFUSED = "That isn't available in this test: only Zoya's browser and web search are."
PAGE_TEXT_CHARS = 1500
TOOL_INPUT_CHARS = 160


@dataclass
class WebStep:
    elements: int
    state_chars: int
    operation: str
    operation_confidence: float
    target: str
    target_confidence: float | None
    latency_ms: int


@dataclass
class LoopRun:
    goal: str
    done: bool
    reason: str
    steps: int
    history: list[str]
    decisions: list[WebStep] = field(default_factory=list)


@dataclass
class Run:
    id: str
    site: str
    command: str
    set: str
    success: bool = False
    seconds: float = 0.0
    model_calls: int = 0
    brain_calls: int = 0
    input_tokens: int = 0
    cached_tokens: int = 0
    output_tokens: int = 0
    jev_calls: int = 0
    jev_web_calls: int = 0
    jev_state_chars: int = 0
    paid_searches: int = 0
    cents: float = 0.0
    said: list[str] = field(default_factory=list)
    confirmations: list[str] = field(default_factory=list)
    tools: list[str] = field(default_factory=list)
    loops: list[LoopRun] = field(default_factory=list)
    fetched: list[str] = field(default_factory=list)
    url: str = ""
    title: str = ""
    page_text: str = ""
    route: str = ""
    error: str = ""
    failed_checks: list[str] = field(default_factory=list)
    cause: str = ""


class Meter:
    run: Run | None = None
    pending_steps: list[WebStep] = []
    channel: Any = None

    @classmethod
    def add(cls, attribute: str, amount: float = 1) -> None:
        if cls.run is not None:
            setattr(cls.run, attribute, getattr(cls.run, attribute) + amount)


def model_cents(model_id: str, usage: dict[str, int]) -> float:
    price_in, price_cached, price_out = PRICES_USD_PER_1M.get(model_id, UNKNOWN_PRICE_USD_PER_1M)
    cached = usage.get("cacheReadInputTokens", 0)
    fresh = max(0, usage.get("inputTokens", 0) - cached)
    usd = fresh * price_in + cached * price_cached + usage.get("outputTokens", 0) * price_out
    return usd / PER_MILLION * CENTS_PER_USD


def meter_model_class(cls: Any) -> None:
    original = cls.stream

    async def stream(self: Any, *args: Any, **kwargs: Any) -> Any:
        model_id = str(self.get_config().get("model_id", ""))
        Meter.add("model_calls")
        if model_id == os.environ.get("BRAIN_MODEL"):
            Meter.add("brain_calls")
        async for event in original(self, *args, **kwargs):
            usage = event.get("metadata", {}).get("usage") if isinstance(event, dict) else None
            if usage:
                Meter.add("input_tokens", usage.get("inputTokens", 0))
                Meter.add("cached_tokens", usage.get("cacheReadInputTokens", 0))
                Meter.add("output_tokens", usage.get("outputTokens", 0))
                Meter.add("cents", model_cents(model_id, usage))
            yield event

    cls.stream = stream


def request_text(state: Any, questions: Any) -> str:
    """The whole Jev request as sent: state plus every question, for its size."""
    shown = state if isinstance(state, str) else json.dumps(state, ensure_ascii=False)
    asked = {name: q.model_dump(exclude_none=True) for name, q in questions.items()}
    return shown + json.dumps(asked, ensure_ascii=False)


def web_step(sent: str, answers: decisions.Answers) -> WebStep:
    operation = answers.pick("operation")
    name = operation.name if operation else "-"
    target = answers.pick(f"{name.lower()}_target") if operation else None
    return WebStep(
        elements=len(set(re.findall(r"\[(\d+)\]", sent))),
        state_chars=len(sent),
        operation=name if answers else f"unavailable: {answers.reason[:60]}",
        operation_confidence=round(operation.confidence, 2) if operation else 0.0,
        target=target.name if target else "",
        target_confidence=round(target.confidence, 2) if target else None,
        latency_ms=answers.latency_ms,
    )


def install_meters() -> None:
    from strands.models.openai import OpenAIModel
    from strands.models.openai_responses import OpenAIResponsesModel

    from zoya.agents import web_loop

    for cls in (OpenAIModel, OpenAIResponsesModel):
        meter_model_class(cls)
    original_ask = decisions.ask

    def ask(state: Any, questions: Any, *args: Any, **kwargs: Any) -> decisions.Answers:
        sent = request_text(state, questions)
        Meter.add("jev_calls")
        Meter.add("cents", len(sent) / CHARS_PER_TOKEN * JEV_USD_PER_1M / PER_MILLION * 100)
        answers = original_ask(state, questions, *args, **kwargs)
        if "operation" in questions:
            Meter.add("jev_web_calls")
            Meter.add("jev_state_chars", len(sent))
            Meter.pending_steps.append(web_step(sent, answers))
        return answers

    decisions.ask = ask
    original_run = web_loop.run

    def loop_run(goal: str, *args: Any, **kwargs: Any) -> Any:
        Meter.pending_steps = []
        outcome = original_run(goal, *args, **kwargs)
        if Meter.run is not None:
            Meter.run.loops.append(
                LoopRun(
                    goal=goal,
                    done=outcome.done,
                    reason=outcome.reason,
                    steps=outcome.steps,
                    history=[h["action"] for h in outcome.history],
                    decisions=list(Meter.pending_steps),
                )
            )
        return outcome

    web_loop.run = loop_run


def answer_cancel() -> None:
    deadline = time.monotonic() + REPLY_WAIT_S
    while not safety.awaiting_reply() and time.monotonic() < deadline:
        time.sleep(REPLY_POLL_S)
    time.sleep(ECHO_TAIL_S + REPLY_POLL_S)
    Meter.channel.reply("cancel", time.monotonic())


def install_voice() -> None:
    from zoya import orchestrator

    def narrate(text: str, *_args: Any, **_kwargs: Any) -> None:
        if Meter.run is not None and text.strip():
            Meter.run.said.append(text.strip())

    def say_and_wait(text: str, *_args: Any, **_kwargs: Any) -> bool:
        if Meter.run is not None:
            Meter.run.confirmations.append(text)
        threading.Thread(target=answer_cancel, daemon=True).start()
        return True

    Meter.channel = safety.claim_voice_channel()
    speech.narrate = narrate
    speech.say_and_wait = say_and_wait
    speech.is_speaking = lambda: False
    speech.cancel = lambda: None
    orchestrator.events.emit = lambda _event: None


def install_headless_browser(profile: Path) -> None:
    """A headless Chrome on a throwaway profile: nothing on the owner's screen, and neither the
    owner's profile nor Zoya's own is touched. The user agent drops "Headless" so sites serve the
    page a real Zoya user would get."""
    from zoya.tools import browser

    browser.BROWSER_PROFILE_DIR = profile
    browser.CHROME_PID_FILE = profile / "chrome.pid"
    browser.AGENT_BROWSER_SESSION = f"zoya-s4web-{os.getpid()}"
    browser.EXTRA_ARGS = [
        *browser.EXTRA_ARGS,
        "--headless=new",
        "--window-size=1280,860",
        f"--user-agent={HEADLESS_USER_AGENT}",
    ]


def quiet_side_effects() -> None:
    from zoya import aws, harness, hub_data, orchestrator
    from zoya.tools import memory

    memory.capture_outcome = lambda *_a, **_k: None
    orchestrator.memory.user_profile = lambda: ""
    orchestrator.recent_corrections = lambda: []
    aws.record_task = lambda *_a, **_k: None
    hub_data.record_said = lambda *_a, **_k: None
    harness.learned_pick = lambda _command: None
    harness.learn_pick = lambda *_a, **_k: None


def allowed(name: str) -> bool:
    from zoya import harness

    return (
        name.startswith(REAL_TOOL_PREFIXES) or name in REAL_TOOLS or name in harness.action_tools()
    )


def install_tool_fence() -> None:
    """Only browser and web tools run for real; the gate still sees every call first."""
    from strands.hooks import BeforeToolCallEvent
    from strands.tools.tools import PythonAgentTool

    from zoya import harness, orchestrator
    from zoya.tools import ToolError

    def refused(name: str, spec: dict[str, Any]) -> PythonAgentTool:
        def run(tool_use: dict[str, Any], **_: Any) -> dict[str, Any]:
            return {
                "toolUseId": tool_use["toolUseId"],
                "status": "error",
                "content": [{"text": REFUSED}],
            }

        return PythonAgentTool(name, spec, run)

    def record_and_fence(event: BeforeToolCallEvent) -> None:
        name = str(event.tool_use.get("name", ""))
        if Meter.run is not None:
            tool_input = json.dumps(event.tool_use.get("input", {}), ensure_ascii=False)
            Meter.run.tools.append(f"{name} {tool_input[:TOOL_INPUT_CHARS]}")
            if name == "web_fetch":
                Meter.run.fetched += [
                    str(u) for u in event.tool_use.get("input", {}).get("urls", [])
                ]
            if name in PAID_SEARCH_TOOLS:
                Meter.add("paid_searches")
                Meter.add("cents", TINYFISH_USD_PER_CALL * CENTS_PER_USD)
        if allowed(name) or event.cancel_tool:
            return
        spec = (event.selected_tool.tool_spec if event.selected_tool else None) or {
            "name": name,
            "description": name,
            "inputSchema": {"json": {"type": "object"}},
        }
        event.selected_tool = refused(name, spec)

    real_build = orchestrator.build_orchestrator

    def build(**kwargs: Any) -> Any:
        agent = real_build(**kwargs)
        agent.hooks.add_callback(BeforeToolCallEvent, record_and_fence)
        return agent

    real_action, real_fast = harness.run_action, orchestrator.run_fast_tool

    def run_action(action: str, args: dict[str, Any]) -> str:
        if Meter.run is not None:
            Meter.run.tools.append(
                f"{action} {json.dumps(args, ensure_ascii=False)[:TOOL_INPUT_CHARS]}"
            )
        if not allowed(action):
            raise ToolError(REFUSED)
        return real_action(action, args)

    def run_fast_tool(decision: Any) -> str:
        if Meter.run is not None:
            Meter.run.tools.append(
                f"{decision.tool} {json.dumps(decision.args)[:TOOL_INPUT_CHARS]}"
            )
        if not allowed(decision.tool or ""):
            raise ToolError(REFUSED)
        return real_fast(decision)

    orchestrator.build_orchestrator = build
    harness.run_action = run_action
    orchestrator.run_fast_tool = run_fast_tool


def reset_browser() -> None:
    from zoya.tools import browser

    try:
        browser.on_page(lambda page: page.goto(BLANK_PAGE))
    except Exception as error:  # noqa: BLE001 — a dead browser is restarted for the next task
        print(f"  browser reset failed ({error}): restarting it", flush=True)
        browser.close()
        browser._state.clear()


def final_page(run: Run) -> None:
    from zoya.tools import browser

    def read(page: Any) -> tuple[str, str, str]:
        return page.url, page.title(), page.inner_text("body")[:PAGE_TEXT_CHARS]

    try:
        run.url, run.title, text = browser.on_page(read)
    except Exception as error:  # noqa: BLE001
        run.error = run.error or f"final page unreadable: {error}"
        return
    run.page_text = " ".join(text.split())


GAVE_UP = re.compile(
    r"couldn['’]t|could not|can['’]t|cannot|unable|wasn['’]t able|didn['’]t respond"
    r"|nahi (?:kar|mil)",
    re.I,
)
PROGRESS_LINE = re.compile(r"^(?:Working on it:|Still working on it\.)")


def answer(run: Run) -> str:
    """What Zoya said after her first line: the templated repeat of the request, and progress
    lines, prove nothing about the outcome."""
    from zoya import progress

    first = progress.early_line(run.command)
    return " ".join(s for s in run.said if s != first and not PROGRESS_LINE.match(s))


def failed_checks(task: dict[str, Any], run: Run) -> list[str]:
    heard = answer(run)
    failed = ['"gave up"'] if GAVE_UP.search(heard) else []
    for check in task["checks"]:
        if "said" in check:
            ok = bool(re.search(check["said"], heard, re.I))
        elif "not_said" in check:
            ok = not re.search(check["not_said"], heard, re.I)
        elif "confirm" in check:
            ok = any(re.search(check["confirm"], asked, re.I) for asked in run.confirmations)
        elif "visited" in check:
            ok = any(re.search(check["visited"], url, re.I) for url in [run.url, *run.fetched])
        else:
            ok = bool(re.search(check["url"], run.url, re.I))
        if not ok:
            failed.append(json.dumps(check, ensure_ascii=False))
    return failed


BLOCK_TITLES = re.compile(r"just a moment|attention required|access denied|forbidden", re.I)


def cause(run: Run) -> str:
    """A first guess at why a task failed; the report's table is checked by hand."""
    if run.success:
        return ""
    if run.error.startswith("over"):
        return "timeout"
    if run.confirmations:
        return "gate ask"
    if run.url in ("", BLANK_PAGE) or BLOCK_TITLES.search(run.title):
        return "page didn't load"
    if any(not loop.done for loop in run.loops):
        return "hand-back"
    if not any('"url"' not in c for c in run.failed_checks):
        return "wrong element"
    return "wrong or missing answer"


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
        if result.spoken and result.spoken.strip() not in run.said:
            run.said.append(result.spoken.strip())
    run.error = run.error or outcome.get("error", "")


def run_task(task: dict[str, Any], set_name: str) -> Run:
    from zoya import orchestrator

    run = Run(task["id"], task["site"], task["command"], set_name)
    orchestrator._conversation.clear()
    reset_browser()
    Meter.run = run
    started = time.monotonic()
    execute(task["command"], run)
    run.seconds = round(time.monotonic() - started, 1)
    Meter.run = None
    final_page(run)
    run.cents = round(run.cents, 3)
    return grade(task, run)


ASKED = '"no confirmation: none of these tasks needs one"'


def grade(task: dict[str, Any], run: Run) -> Run:
    asked = run.confirmations and not task.get("expects_confirmation")
    run.failed_checks = failed_checks(task, run) + ([ASKED] if asked else [])
    run.success = not run.failed_checks and not run.error
    run.cause = cause(run)
    return run


def regrade(label: str, saved: str, set_name: str) -> int:
    """Grade a saved run again with the current checks; nothing is run."""
    tasks = {t["id"]: t for t in load_tasks(set_name, "")}
    runs = []
    for raw in json.loads((OUT_DIR / f"{saved}.json").read_text(encoding="utf-8")):
        raw["loops"] = [
            LoopRun(**{**loop, "decisions": [WebStep(**d) for d in loop["decisions"]]})
            for loop in raw["loops"]
        ]
        runs.append(grade(tasks[raw["id"]], Run(**raw)))
    write_results(label, runs)
    print(table(label, runs), flush=True)
    return 0


def write_results(label: str, runs: list[Run]) -> None:
    (OUT_DIR / f"{label}.json").write_text(
        json.dumps([asdict(r) for r in runs], indent=1, ensure_ascii=False), encoding="utf-8"
    )
    (OUT_DIR / f"{label}.md").write_text(table(label, runs), encoding="utf-8")


def median(values: list[float]) -> float:
    return round(statistics.median(values), 1) if values else 0.0


def table(label: str, runs: list[Run]) -> str:
    lines = [
        f"# S4-Web evaluation: {label}",
        "",
        "| task | site | pass | s | model calls | brain | Jev (web) | input tok | cents | cause |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for r in runs:
        lines.append(
            f"| {r.id} | {r.site} | {'yes' if r.success else 'no'} | {r.seconds} | {r.model_calls} "
            f"| {r.brain_calls} | {r.jev_calls} ({r.jev_web_calls}) | {r.input_tokens} "
            f"| {r.cents} | {r.cause} |"
        )
    passed = [r for r in runs if r.success]
    lines += [
        "",
        f"**Passed: {len(passed)}/{len(runs)}**",
        f"- median wall s (passing): {median([r.seconds for r in passed])}",
        f"- median model calls per task: {median([r.model_calls for r in runs])}",
        f"- median brain input tokens per task: {median([r.input_tokens for r in runs])}",
        f"- total cents: {round(sum(r.cents for r in runs), 2)}",
    ]
    return "\n".join(lines) + "\n"


def log_spend(label: str, runs: list[Run]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    entry = {"label": label, "tasks": len(runs), "cents": round(sum(r.cents for r in runs), 3)}
    with SPEND_LOG.open("a", encoding="utf-8") as spend:
        spend.write(json.dumps(entry) + "\n")


def load_tasks(set_name: str, only: str) -> list[dict[str, Any]]:
    tasks = json.loads((WEB_DIR / f"tasks_{set_name}.json").read_text(encoding="utf-8"))
    wanted = {name.strip() for name in only.split(",") if name.strip()}
    return [task for task in tasks if not wanted or task["id"] in wanted]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("label")
    parser.add_argument("--set", choices=("dev", "heldout", "skills"), required=True)
    parser.add_argument("--only", default="")
    parser.add_argument("--regrade", default="", help="grade a saved LABEL.json again, offline")
    args = parser.parse_args()
    if args.regrade:
        return regrade(args.label, args.regrade, args.set)
    load_env()
    from zoya import aws

    aws.load_provider_secrets()
    profile = Path(tempfile.mkdtemp(prefix="zoya-s4web-"))
    install_headless_browser(profile)
    install_meters()
    install_voice()
    quiet_side_effects()
    install_tool_fence()
    decisions.warm()
    runs = []
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for task in load_tasks(args.set, args.only):
        run = run_task(task, args.set)
        runs.append(run)
        print(
            f"{'PASS' if run.success else 'FAIL'} {run.id} {run.seconds}s lm={run.model_calls} "
            f"jev={run.jev_calls} in={run.input_tokens} {run.cents}c {run.cause} | "
            f"{' | '.join(run.said)[:300]}",
            flush=True,
        )
        write_results(args.label, runs)
    log_spend(args.label, runs)
    print(table(args.label, runs), flush=True)
    from zoya.tools import browser

    browser.close()
    os._exit(0)


if __name__ == "__main__":
    sys.exit(main())
