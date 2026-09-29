"""The autotune night: measure every task on main, verify pinned candidates, publish the triage.

    python -m evals.autotune sync             reset ../zoya-autotune to origin/main, make check
    python -m evals.autotune census           run every task once; FLAKY tasks twice more
    python -m evals.autotune queue BRANCH     guard a candidate branch and pin its SHA
    python -m evals.autotune verify           judge up to 3 pinned candidates
    python -m evals.autotune triage           write logs/autotune/nights/<night>.json and .md
    python -m evals.autotune publish          push them to the autotune-data branch
    python -m evals.autotune report           write logs/autotune/report-<night>.md

Every eval runs in the worktree ../zoya-autotune, never in the main checkout. The keep rule
(pertask), the failure causes (triage), the branch guard (guard) and the spend (ledger) are the
sibling modules. Standard library only, and it never imports `zoya`, so it runs and tests on Linux.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import statistics
import subprocess
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from evals.autotune import guard, ledger, pertask, score, triage

WORKTREE_NAME = "zoya-autotune"  # detached, so no local branch shadows autotune/fix-* names
REMOTE = "origin"
MAIN = "main"
BASE_REF = f"{REMOTE}/{MAIN}"
DATA_BRANCH = "autotune-data"
DATA_REF = f"{REMOTE}/{DATA_BRANCH}"
DATA_DIR = "nights"
TARGETS_TRAILER = "Autotune-Targets"
TASKS_PATH = "evals/harness/tasks.json"
HARNESS_FILES = ("evals/harness/run.py", "evals/harness/grade.py")
EVAL_CMD_ENV = "AUTOTUNE_EVAL_CMD"
DEFAULT_EVAL_CMD = ".venv/bin/python evals/harness/run.py"
CHECK_CMD_ENV = "AUTOTUNE_CHECK_CMD"
DEFAULT_CHECK_CMD = "make check"
BUDGET_ENV = "AUTOTUNE_BUDGET_CENTS"
DEFAULT_BUDGET_CENTS = 1000.0  # per night
NIGHT_ENV = "AUTOTUNE_NIGHT"
DEADLINE_ENV = "AUTOTUNE_DEADLINE"  # epoch seconds; no eval starts after it
MAX_CANDIDATES = 3
FLAKY_EXTRA_RUNS = 2
TASK_META_KEYS = ("held_out",)  # a change to these is not a change to the task
LOG_SUBDIR = Path("logs") / "autotune"
HARNESS_OUT = Path("logs") / "harness"  # run.py writes logs/harness/LABEL.json under its repo
ENV_FILE = ".env"
SHA_CHARS = 12
CHECK_TAIL_LINES = 40
QUEUE_COLUMNS = ("utc", "branch", "ref", "sha", "targets")
VERDICT_COLUMNS = ("utc", "night", "branch", "sha", "status", "fixed", "broken", "reason")
TRIAGED = (pertask.NEW_FAIL, pertask.FAIL, pertask.FLAKY)  # in the order the report lists them
HISTORY_SHOWN = 18  # census runs of a task a triage record shows
SKIPPED = "skipped"


class AutotuneError(Exception):
    """A refusal or failure the CLI reports in one line with a non-zero exit."""


class Paths:
    """Where everything lives, anchored at the main checkout."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.worktree = self.root.parent / WORKTREE_NAME
        self.logs = self.root / LOG_SUBDIR
        self.history = self.logs / "history.tsv"
        self.candidates = self.logs / "candidates.tsv"
        self.queue = self.logs / "queue.tsv"
        self.verdicts = self.logs / "verdicts.tsv"
        self.nights = self.logs / DATA_DIR

    def state(self, night: str) -> Path:
        return self.logs / f"state-{night}.json"

    def night_file(self, night: str, suffix: str) -> Path:
        return self.nights / f"{night}{suffix}"

    def report(self, night: str) -> Path:
        return self.logs / f"report-{night}.md"


# --- git and the clock ----------------------------------------------------------------------------


def _git(cwd: Path, *args: str, env: dict[str, str] | None = None) -> str:
    proc = subprocess.run(
        ["git", "-C", str(cwd), *args],
        capture_output=True,
        text=True,
        env={**os.environ, **env} if env else None,
    )
    if proc.returncode != 0:
        raise AutotuneError(f"git {' '.join(args)}: {proc.stderr.strip()}")
    return proc.stdout.strip()


def _git_ok(cwd: Path, *args: str) -> bool:
    return subprocess.run(["git", "-C", str(cwd), *args], capture_output=True).returncode == 0


def main_checkout(start: Path) -> Path:
    """The main checkout, even when called from inside a linked worktree."""
    common = _git(start, "rev-parse", "--path-format=absolute", "--git-common-dir")
    return Path(common).parent


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def tonight() -> str:
    return os.environ.get(NIGHT_ENV) or datetime.now().astimezone().strftime("%Y-%m-%d")


def _check_clock() -> None:
    deadline = os.environ.get(DEADLINE_ENV)
    if deadline and time.time() >= float(deadline):
        raise AutotuneError(f"past the night's deadline ({DEADLINE_ENV})")


def _show(rev: str, path: str, cwd: Path) -> str | None:
    """A file's text at a revision, or None when it is not there."""
    proc = subprocess.run(
        ["git", "-C", str(cwd), "show", f"{rev}:{path}"], capture_output=True, text=True
    )
    return proc.stdout if proc.returncode == 0 else None


def _fetch(paths: Paths, branch: str) -> None:
    _git(paths.root, "fetch", "-q", REMOTE, f"+refs/heads/{branch}:refs/remotes/{REMOTE}/{branch}")


# --- the night's state ----------------------------------------------------------------------------


def load_state(paths: Paths, night: str) -> dict[str, Any]:
    path = paths.state(night)
    if not path.exists():
        return {"night": night}
    return json.loads(path.read_text(encoding="utf-8"))


def save_state(paths: Paths, night: str, key: str, value: Any) -> None:
    state = load_state(paths, night)
    state[key] = value
    paths.logs.mkdir(parents=True, exist_ok=True)
    paths.state(night).write_text(json.dumps(state, indent=1), encoding="utf-8")


def _require_sync(paths: Paths, night: str) -> str:
    sync_state = load_state(paths, night).get("sync", {})
    if not sync_state.get("ok"):
        raise AutotuneError(f"tonight's sync did not pass: {sync_state.get('reason', 'not run')}")
    return sync_state["sha"]


# --- sync -----------------------------------------------------------------------------------------


def sync(paths: Paths, night: str) -> str:
    """Reset the worktree to origin/main, detached, then run the check there. Returns the SHA."""
    _fetch(paths, MAIN)
    if paths.worktree.exists():
        check_worktree(paths)
        _git(paths.worktree, "checkout", "-q", "-f", "--detach", BASE_REF)
    else:
        _git(paths.root, "worktree", "prune")
        _git(paths.root, "worktree", "add", "-q", "--detach", str(paths.worktree), BASE_REF)
    _git(paths.worktree, "clean", "-q", "-f", "-d")
    env = paths.root / ENV_FILE
    if env.exists() and not (paths.worktree / ENV_FILE).exists():
        (paths.worktree / ENV_FILE).symlink_to(env)
    sha = _git(paths.worktree, "rev-parse", "HEAD")
    code = run_check(paths)
    if code != 0:
        reason = f"{shlex.join(check_command())} failed with exit {code} on {sha[:SHA_CHARS]}"
        save_state(paths, night, "sync", {"ok": False, "sha": sha, "reason": reason})
        raise AutotuneError(reason)
    save_state(paths, night, "sync", {"ok": True, "sha": sha, "reason": ""})
    print(f"sync: {paths.worktree} at {BASE_REF} {sha[:SHA_CHARS]}, check passed")
    return sha


def check_worktree(paths: Paths) -> None:
    """Refuse unless ../zoya-autotune is a linked worktree of this repo."""
    if not paths.worktree.is_dir():
        raise AutotuneError(f"no worktree at {paths.worktree}: run `python -m evals.autotune sync`")
    top = Path(_git(paths.worktree, "rev-parse", "--show-toplevel")).resolve()
    if top != paths.worktree.resolve() or top == paths.root:
        raise AutotuneError(f"{paths.worktree} is not its own worktree (top level {top})")
    if main_checkout(paths.worktree).resolve() != paths.root:
        raise AutotuneError(f"{paths.worktree} belongs to another repository")


def check_command() -> list[str]:
    return shlex.split(os.environ.get(CHECK_CMD_ENV, DEFAULT_CHECK_CMD))


def run_check(paths: Paths) -> int:
    proc = subprocess.run(
        check_command(), cwd=paths.worktree, capture_output=True, text=True, check=False
    )
    tail = (proc.stdout + proc.stderr).splitlines()[-CHECK_TAIL_LINES:]
    print("\n".join(tail), flush=True)
    return proc.returncode


# --- running the eval -----------------------------------------------------------------------------


def eval_command(paths: Paths) -> list[str]:
    """AUTOTUNE_EVAL_CMD split like a shell would; a relative program missing from the worktree
    (the gitignored .venv) resolves against the main checkout."""
    tokens = shlex.split(os.environ.get(EVAL_CMD_ENV, DEFAULT_EVAL_CMD))
    if not tokens:
        raise AutotuneError(f"{EVAL_CMD_ENV} is empty")
    program = Path(tokens[0])
    if (
        len(program.parts) > 1
        and not program.is_absolute()
        and not (paths.worktree / program).exists()
        and (paths.root / program).exists()
    ):
        tokens[0] = str(paths.root / program)
    return tokens


def run_eval(paths: Paths, label: str, only: list[str]) -> list[dict]:
    command = eval_command(paths) + [label] + (["--only", ",".join(only)] if only else [])
    print(f"eval: {shlex.join(command)} (in {paths.worktree})", flush=True)
    proc = subprocess.run(command, cwd=paths.worktree)
    out = paths.worktree / HARNESS_OUT / f"{label}.json"
    if proc.returncode != 0:
        raise AutotuneError(f"eval {label} exited {proc.returncode}")
    if not out.exists():
        raise AutotuneError(f"eval {label} wrote no {out}")
    return score.load(out)


def budget_cents() -> float:
    return float(os.environ.get(BUDGET_ENV, DEFAULT_BUDGET_CENTS))


def spent_tonight(paths: Paths, night: str) -> float:
    books = (ledger.Ledger(paths.history), ledger.Ledger(paths.candidates))
    return sum(book.spent_cents(night) for book in books)


def estimate_cents(paths: Paths, tasks: list[str]) -> float:
    """What running these tasks once is expected to cost, from the census history."""
    rows = ledger.Ledger(paths.history).rows()
    every = [float(row["cents"]) for row in rows]
    fallback = statistics.fmean(every) if every else 0.0
    total = 0.0
    for task in tasks:
        mine = [float(row["cents"]) for row in rows if row["task"] == task]
        total += statistics.fmean(mine) if mine else fallback
    return total


def check_budget(paths: Paths, night: str, planned_cents: float) -> None:
    spent = spent_tonight(paths, night)
    budget = budget_cents()
    if spent + planned_cents > budget:
        raise AutotuneError(
            f"budget: spent {spent:.1f}¢ tonight + estimate {planned_cents:.1f}¢ > {budget:.1f}¢ "
            f"({BUDGET_ENV}, per night)"
        )


def run_and_record(
    paths: Paths, book: ledger.Ledger, night: str, label: str, only: list[str], tasks: dict
) -> list[dict]:
    """One eval run of `only` (every task when empty), each task's result appended to `book`."""
    _check_clock()
    check_budget(paths, night, estimate_cents(paths, only or list(tasks)))
    sha = _git(paths.worktree, "rev-parse", "HEAD")
    runs = run_eval(paths, label, only)
    for run in runs:
        book.append(
            {
                "night": night,
                "sha": sha,
                "task": run["id"],
                "group": run["group"],
                "success": int(run["success"] is True),
                "cents": run.get("cents", 0.0),
                "seconds": run.get("seconds", 0.0),
                "cause": triage.cause(tasks.get(run["id"], {}), run),
            }
        )
    return runs


# --- tasks and their history ----------------------------------------------------------------------


def load_tasks(text: str | None) -> dict[str, dict]:
    return {task["id"]: task for task in json.loads(text or "[]")}


def worktree_tasks(paths: Paths) -> dict[str, dict]:
    return load_tasks((paths.worktree / TASKS_PATH).read_text(encoding="utf-8"))


def held_out(tasks: dict[str, dict]) -> set[str]:
    return {task_id for task_id, task in tasks.items() if task.get("held_out") is True}


def _entry(task: dict | None) -> dict | None:
    if task is None:
        return None
    return {key: value for key, value in task.items() if key not in TASK_META_KEYS}


def history(paths: Paths, tasks: dict[str, dict]) -> dict[str, list[dict]]:
    """Each task's census rows, oldest first, from the commits where its tasks.json entry was
    what it is in `tasks`: a task's history resets when its entry changes."""
    at_sha: dict[str, dict[str, dict]] = {}
    kept: dict[str, list[dict]] = {task_id: [] for task_id in tasks}
    for row in ledger.Ledger(paths.history).rows():
        if row["task"] not in tasks:
            continue
        if row["sha"] not in at_sha:
            at_sha[row["sha"]] = load_tasks(_show(row["sha"], TASKS_PATH, paths.root) or "[]")
        if _entry(at_sha[row["sha"]].get(row["task"])) == _entry(tasks[row["task"]]):
            kept[row["task"]].append(row)
    return kept


def outcomes(rows: list[dict]) -> list[pertask.Outcome]:
    return [pertask.Outcome(row["success"] == "1", float(row["cents"])) for row in rows]


def _split(rows: list[dict], night: str) -> tuple[list[dict], list[dict]]:
    return [r for r in rows if r["night"] != night], [r for r in rows if r["night"] == night]


def labels(paths: Paths, tasks: dict[str, dict], night: str) -> dict[str, str]:
    """Each task's class after tonight's census, NEW-FAIL included."""
    found = {}
    for task_id, rows in history(paths, tasks).items():
        before, now = _split(rows, night)
        found[task_id] = pertask.label(outcomes(before), outcomes(now))
    return found


# --- census ---------------------------------------------------------------------------------------


def census(paths: Paths, night: str) -> dict[str, str]:
    """Every task once on main, then two more runs of each FLAKY task."""
    _require_sync(paths, night)
    tasks = worktree_tasks(paths)
    book = ledger.Ledger(paths.history)
    runs = [f"census-{night}-1"]
    run_and_record(paths, book, night, runs[0], [], tasks)
    flaky = sorted(t for t, state in labels(paths, tasks, night).items() if state == pertask.FLAKY)
    for index in range(FLAKY_EXTRA_RUNS):
        if flaky:
            runs.append(f"census-{night}-{index + 2}")
            run_and_record(paths, book, night, runs[-1], flaky, tasks)
    found = labels(paths, tasks, night)
    save_state(paths, night, "census", {"runs": runs, "labels": found})
    print(f"census: {sum(state == pertask.PASS for state in found.values())}/{len(found)} PASS")
    return found


# --- queue ----------------------------------------------------------------------------------------


def _resolve(paths: Paths, branch: str) -> tuple[str, str]:
    """(ref, sha) of a candidate: the remote's branch when it has one, else the local branch."""
    if _git_ok(paths.root, "ls-remote", "--exit-code", "--heads", REMOTE, branch):
        _fetch(paths, branch)
        ref = f"refs/remotes/{REMOTE}/{branch}"
    else:
        ref = f"refs/heads/{branch}"
    if not _git_ok(paths.root, "rev-parse", "--verify", "--quiet", ref):
        raise AutotuneError(f"no branch {branch} on {REMOTE} or here")
    return ref, _git(paths.root, "rev-parse", ref)


def targets_of(paths: Paths, sha: str) -> list[str]:
    """The task ids in the branch's Autotune-Targets trailers, in order, once each."""
    text = _git(
        paths.root,
        "log",
        f"--format=%(trailers:key={TARGETS_TRAILER},valueonly)",
        f"{BASE_REF}..{sha}",
    )
    return list(dict.fromkeys(t for t in re.split(r"[\s,]+", text) if t))


def inspect(paths: Paths, sha: str) -> tuple[guard.Result, list[str]]:
    """The guard's result and the declared targets of a candidate SHA."""
    base = _git(paths.root, "merge-base", BASE_REF, sha)
    diff = _git(
        paths.root, "diff", "--no-ext-diff", "--no-textconv", "--no-renames", f"{BASE_REF}...{sha}"
    )
    before, after = _show(base, TASKS_PATH, paths.root), _show(sha, TASKS_PATH, paths.root)
    result = guard.check(diff, before, after)
    main_tasks = load_tasks(_show(BASE_REF, TASKS_PATH, paths.root))
    targets = targets_of(paths, sha)
    result.violations += guard.check_targets(targets, set(main_tasks), held_out(main_tasks))
    return result, targets


def queue(paths: Paths, branch: str) -> str:
    """Guard a branch and pin its current SHA; prints the flags first, then the diffstat."""
    _fetch(paths, MAIN)
    ref, sha = _resolve(paths, branch)
    result, targets = inspect(paths, sha)
    for flag in result.flags:
        print(f"FLAG {flag}")
    for violation in result.violations:
        print(f"REFUSED {violation}")
    print(_git(paths.root, "diff", "--stat", f"{BASE_REF}...{sha}"))
    print(f"targets: {', '.join(targets) or 'none'}")
    if result.violations:
        raise AutotuneError(f"{branch} is refused by the guard")
    ledger.Ledger(paths.queue, QUEUE_COLUMNS).append(
        {"branch": branch, "ref": ref, "sha": sha, "targets": ",".join(targets)}
    )
    print(f"pinned {branch} at {sha[:SHA_CHARS]}")
    return sha


# --- verify ---------------------------------------------------------------------------------------


def pending_pins(paths: Paths) -> list[dict]:
    judged = {row["sha"] for row in ledger.Ledger(paths.verdicts, VERDICT_COLUMNS).rows()}
    pins = ledger.Ledger(paths.queue, QUEUE_COLUMNS).rows()
    return [pin for pin in pins if pin["sha"] not in judged]


def verify(paths: Paths, night: str) -> list[dict]:
    """Judge up to MAX_CANDIDATES pinned candidates. A pin whose branch moved is skipped."""
    _require_sync(paths, night)
    _fetch(paths, MAIN)
    results: list[dict] = []
    try:
        for pin in pending_pins(paths):
            if sum(r["status"] != SKIPPED for r in results) >= MAX_CANDIDATES:
                break
            results.append(_verify_one(paths, night, pin))
    finally:
        save_state(paths, night, "verify", results)
    return results


def _verify_one(paths: Paths, night: str, pin: dict) -> dict:
    entry = {"branch": pin["branch"], "sha": pin["sha"], "targets": pin["targets"], "flags": []}
    reason = _skip_reason(paths, pin)
    if reason:
        return _judged(paths, night, entry, SKIPPED, reason)
    result, targets = inspect(paths, pin["sha"])
    entry["flags"] = result.flags
    if result.violations:
        return _judged(paths, night, entry, pertask.REJECTED, "; ".join(result.violations))
    _git(paths.worktree, "checkout", "-q", "-f", "--detach", pin["sha"])
    _git(paths.worktree, "clean", "-q", "-f", "-d")
    code = run_check(paths)
    if code != 0:
        return _judged(paths, night, entry, pertask.REJECTED, f"the check failed with exit {code}")
    verdict = judge(paths, night, pin["sha"], targets)
    entry.update(
        fixed=verdict.fixed,
        broken=verdict.broken,
        held_out_broken=verdict.held_out_broken,
        not_judged=verdict.not_judged,
    )
    return _judged(paths, night, entry, verdict.status, verdict.reason)


def _skip_reason(paths: Paths, pin: dict) -> str:
    if pin["ref"].startswith(f"refs/remotes/{REMOTE}/"):
        _fetch(paths, pin["ref"].removeprefix(f"refs/remotes/{REMOTE}/"))
    if not _git_ok(paths.root, "rev-parse", "--verify", "--quiet", pin["ref"]):
        return f"{pin['ref']} is gone"
    if _git(paths.root, "rev-parse", pin["ref"]) != pin["sha"]:
        return f"{pin['branch']} moved after it was pinned; pin it again"
    for path in HARNESS_FILES:
        if _show(pin["sha"], path, paths.root) != _show(BASE_REF, path, paths.root):
            return f"its {path} is not main's; merge main into it and pin it again"
    return ""


def judge(paths: Paths, night: str, sha: str, targets: list[str]) -> pertask.Verdict:
    """Targets three times, the rest of their groups and the held-out tasks once as sentinels,
    a sentinel that broke twice more, then the per-task verdict."""
    tasks = worktree_tasks(paths)
    hidden = held_out(tasks)
    groups = {tasks[t]["group"] for t in targets if t in tasks}
    sentinels = sorted(
        t
        for t, task in tasks.items()
        if t not in targets and (task["group"] in groups or t in hidden)
    )
    book = ledger.Ledger(paths.candidates)
    runs: dict[str, list[pertask.Outcome]] = {}
    label = f"verify-{night}-{sha[:SHA_CHARS]}"
    for index in range(pertask.TARGET_RUNS):
        _collect(runs, run_and_record(paths, book, night, f"{label}-t{index + 1}", targets, tasks))
    if sentinels:
        _collect(runs, run_and_record(paths, book, night, f"{label}-s1", sentinels, tasks))
    past = {task: outcomes(rows) for task, rows in history(paths, tasks).items()}
    again = pertask.reruns(past, {t: o for t, o in runs.items() if t not in targets})
    for index in range(pertask.SENTINEL_RERUNS if again else 0):
        _collect(runs, run_and_record(paths, book, night, f"{label}-r{index + 1}", again, tasks))
    return pertask.verdict(past, runs, targets, hidden)


def _collect(runs: dict[str, list[pertask.Outcome]], new: list[dict]) -> None:
    for run in new:
        runs.setdefault(run["id"], []).append(
            pertask.Outcome(run["success"] is True, run.get("cents", 0.0))
        )


def _judged(paths: Paths, night: str, entry: dict, status: str, reason: str) -> dict:
    entry = {**entry, "status": status, "reason": reason}
    ledger.Ledger(paths.verdicts, VERDICT_COLUMNS).append(
        {
            "night": night,
            "branch": entry["branch"],
            "sha": entry["sha"],
            "status": status,
            "fixed": ",".join(entry.get("fixed", [])),
            "broken": ",".join(entry.get("broken", []) + entry.get("held_out_broken", [])),
            "reason": reason,
        }
    )
    print(f"verify: {entry['branch']} {entry['sha'][:SHA_CHARS]} {status}: {reason}")
    return entry


# --- triage ---------------------------------------------------------------------------------------


def build_night(paths: Paths, night: str) -> dict[str, Any]:
    """The night as a cloud session may read it: classes, alarms, candidates and the redacted
    triage of every FAIL, FLAKY and NEW-FAIL task. Held-out tasks show pass or fail only."""
    state = load_state(paths, night)
    sync_state = state.get("sync", {"ok": False, "reason": "not run"})
    data: dict[str, Any] = {
        "night": night,
        "sha": sync_state.get("sha", ""),
        "sync": {"ok": sync_state["ok"], "reason": sync_state["reason"]},
        "spent_cents": round(spent_tonight(paths, night), 2),
        "budget_cents": budget_cents(),
        "candidates": [_public_candidate(entry) for entry in state.get("verify", [])],
        "classes": {},
        "triage": [],
        "held_out": [],
    }
    if "census" not in state:
        return data
    tasks = load_tasks(_show(data["sha"], TASKS_PATH, paths.root))
    hidden = held_out(tasks)
    found = state["census"]["labels"]
    last = _last_runs(paths, state["census"]["runs"])
    rows = history(paths, tasks)
    for task_id in sorted(found, key=lambda t: (_rank(found[t]), t)):
        if task_id in hidden:
            continue
        data["classes"][task_id] = found[task_id]
        if found[task_id] in TRIAGED and task_id in last:
            passes = [row["success"] == "1" for row in rows[task_id][-HISTORY_SHOWN:]]
            data["triage"].append(
                triage.record(tasks[task_id], last[task_id], found[task_id], passes)
            )
    first = _first_runs(paths, state["census"]["runs"])
    data["held_out"] = [
        triage.held_out_record(t, first[t]["success"] is True) for t in sorted(hidden) if t in first
    ]
    return data


def _rank(state: str) -> int:
    return TRIAGED.index(state) if state in TRIAGED else len(TRIAGED)


def _public_candidate(entry: dict) -> dict:
    keys = ("branch", "sha", "targets", "flags", "status", "fixed", "broken", "held_out_broken")
    return {key: entry.get(key, []) for key in keys} | {"reason": entry["reason"]}


def _harness_runs(paths: Paths, labels_: list[str]) -> list[dict]:
    runs = []
    for label in labels_:
        out = paths.worktree / HARNESS_OUT / f"{label}.json"
        if out.exists():
            runs += score.load(out)
    return runs


def _last_runs(paths: Paths, labels_: list[str]) -> dict[str, dict]:
    """Each task's last failing census run tonight, else its last run."""
    found: dict[str, dict] = {}
    for run in _harness_runs(paths, labels_):
        if run["id"] not in found or run["success"] is not True:
            found[run["id"]] = run
    return found


def _first_runs(paths: Paths, labels_: list[str]) -> dict[str, dict]:
    found: dict[str, dict] = {}
    for run in _harness_runs(paths, labels_):
        found.setdefault(run["id"], run)
    return found


def render(data: dict[str, Any]) -> str:
    """The night as Markdown: alarms and flagged candidates first."""
    lines = [f"# Autotune night {data['night']}", ""]
    if data["sync"]["ok"]:
        lines.append(f"main {data['sha'][:SHA_CHARS]}: the check passed.")
    else:
        lines.append(f"The night stopped at sync: {data['sync']['reason']}")
    lines.append(f"Spent {data['spent_cents']:.1f}¢ of {data['budget_cents']:.1f}¢ tonight.")
    alarms = [t for t, state in data["classes"].items() if state == pertask.NEW_FAIL]
    lines += ["", "## Regression alarms (NEW-FAIL)", ""]
    lines += [f"- {task}" for task in alarms] or ["None."]
    lines += ["", "## Candidates", ""] + _candidate_lines(data["candidates"])
    lines += ["", "## Census", "", "| task | class |", "| --- | --- |"]
    lines += [f"| {task} | {state} |" for task, state in data["classes"].items()]
    lines += ["", "## Held out (pass or fail only)", "", "| task | result |", "| --- | --- |"]
    lines += [f"| {r['task']} | {r['result']} |" for r in data["held_out"]]
    lines += ["", "## Triage", ""]
    for record in data["triage"]:
        lines += _record_lines(record)
    return "\n".join(lines) + "\n"


def _candidate_lines(candidates: list[dict]) -> list[str]:
    if not candidates:
        return ["None verified."]
    ordered = sorted(candidates, key=lambda c: not c["flags"])
    lines = []
    for c in ordered:
        lines.append(
            f"- **{c['branch']}** {c['sha'][:SHA_CHARS]}: **{c['status']}**, {c['reason']}"
        )
        lines += [f"  - FLAG {flag}" for flag in c["flags"]]
        lines.append(
            f"  - targets {c['targets'] or 'none'}; fixed {c['fixed']}; broken {c['broken']}"
        )
    return lines


def _record_lines(record: dict) -> list[str]:
    return [
        f"### {record['task']} ({record['group']}): {record['class']}, {record['cause']}",
        "",
        f"- history: {record['history']}",
        f"- failed checks: {', '.join(record['failed_checks']) or 'none'}",
        f"- said: {record['said']}",
        f"- asked: {' | '.join(record['confirmations']) or 'nothing'}",
        f"- last tools: {', '.join(record['tools']) or 'none'}",
        f"- url: {record['url'] or 'none'}",
        f"- error: {record['error'] or 'none'}",
        "",
    ]


def write_night(paths: Paths, night: str) -> tuple[Path, Path]:
    data = build_night(paths, night)
    paths.nights.mkdir(parents=True, exist_ok=True)
    as_json = paths.night_file(night, ".json")
    as_md = paths.night_file(night, ".md")
    as_json.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    as_md.write_text(render(data), encoding="utf-8")
    print(f"triage: {as_json} and {as_md}")
    return as_json, as_md


# --- publish --------------------------------------------------------------------------------------


def publish(paths: Paths, night: str) -> str:
    """Commit nights/<night>.json and .md onto the data-only branch and push it. Nothing else."""
    files = [paths.night_file(night, ".json"), paths.night_file(night, ".md")]
    missing = [str(f) for f in files if not f.exists()]
    if missing:
        raise AutotuneError(f"nothing to publish: {', '.join(missing)} missing; run triage")
    parent = ""
    if _git_ok(paths.root, "ls-remote", "--exit-code", "--heads", REMOTE, DATA_BRANCH):
        _fetch(paths, DATA_BRANCH)
        parent = _git(paths.root, "rev-parse", DATA_REF)
    with tempfile.TemporaryDirectory() as scratch:
        env = {"GIT_INDEX_FILE": str(Path(scratch) / "index")}
        _git(paths.root, "read-tree", *([parent] if parent else ["--empty"]), env=env)
        for file in files:
            blob = _git(paths.root, "hash-object", "-w", str(file))
            entry = f"100644,{blob},{DATA_DIR}/{file.name}"
            _git(paths.root, "update-index", "--add", "--cacheinfo", entry, env=env)
        tree = _git(paths.root, "write-tree", env=env)
    if parent and _git(paths.root, "rev-parse", f"{parent}^{{tree}}") == tree:
        print(f"publish: {DATA_BRANCH} already has night {night}")
        return parent
    message = f"chore: autotune night {night}"
    commit = _git(
        paths.root, "commit-tree", tree, *(["-p", parent] if parent else []), "-m", message
    )
    _git(paths.root, "push", "-q", REMOTE, f"{commit}:refs/heads/{DATA_BRANCH}")
    save_state(paths, night, "publish", {"commit": commit})
    print(f"publish: {DATA_BRANCH} {commit[:SHA_CHARS]}")
    return commit


# --- report ---------------------------------------------------------------------------------------


def report(paths: Paths, night: str) -> Path:
    """The local morning report: the published night, then what stayed on the Mac."""
    state = load_state(paths, night)
    published = paths.night_file(night, ".md")
    body = (
        published.read_text(encoding="utf-8")
        if published.exists()
        else render(build_night(paths, night))
    )
    pins = pending_pins(paths)
    lines = [
        body.rstrip("\n"),
        "",
        "## On this Mac",
        "",
        f"- Published: {state.get('publish', {}).get('commit', 'no')}",
        f"- Pins still waiting: {', '.join(p['branch'] for p in pins) or 'none'}",
        f"- Budget: {BUDGET_ENV}={budget_cents():.1f}¢ per night",
    ]
    out = paths.report(night)
    paths.logs.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"report: {out}")
    return out


# --- command line ---------------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m evals.autotune", description=__doc__)
    commands = parser.add_subparsers(dest="cmd", required=True)
    commands.add_parser("sync", help="reset ../zoya-autotune to origin/main and run the check")
    commands.add_parser("census", help="run every task once on main; FLAKY tasks twice more")
    pin = commands.add_parser("queue", help="guard a candidate branch and pin its SHA")
    pin.add_argument("branch")
    commands.add_parser("verify", help=f"judge up to {MAX_CANDIDATES} pinned candidates")
    commands.add_parser("triage", help="write logs/autotune/nights/<night>.json and .md")
    commands.add_parser("publish", help=f"push tonight's files to {DATA_BRANCH}")
    commands.add_parser("report", help="write logs/autotune/report-<night>.md")
    args = parser.parse_args(argv)
    night = tonight()
    try:
        paths = Paths(main_checkout(Path.cwd()))
        if args.cmd == "sync":
            sync(paths, night)
        elif args.cmd == "census":
            census(paths, night)
        elif args.cmd == "queue":
            queue(paths, args.branch)
        elif args.cmd == "verify":
            verify(paths, night)
        elif args.cmd == "triage":
            write_night(paths, night)
        elif args.cmd == "publish":
            publish(paths, night)
        else:
            report(paths, night)
    except AutotuneError as err:
        print(f"autotune: {err}", file=sys.stderr)
        return 1
    return 0
