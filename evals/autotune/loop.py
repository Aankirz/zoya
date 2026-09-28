"""The autotune runner: try one guarded patch at a time against the harness eval, keep what wins.

    python -m evals.autotune init
    python -m evals.autotune baseline --runs N [--group G]
    python -m evals.autotune try PATCH --desc TEXT --runs N [--group G]
    python -m evals.autotune report

Every eval runs in the worktree ../zoya-autotune on branch `autotune`, never in the main checkout.
The guard (surface), the verdict (score) and the spend record (ledger) are the sibling modules.
Standard library only, and it never imports `zoya`, so it runs and tests on Linux.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import statistics
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from evals.autotune import ledger, score, surface

WORKTREE_NAME = "zoya-autotune"
BRANCH = "autotune"
BASE_BRANCH = "main"
EVAL_CMD_ENV = "AUTOTUNE_EVAL_CMD"
DEFAULT_EVAL_CMD = ".venv/bin/python evals/harness/run.py"
BUDGET_ENV = "AUTOTUNE_BUDGET_CENTS"
DEFAULT_BUDGET_CENTS = 1000.0
MIN_RUNS = 2  # score.decide compares means of >= 2 repeated runs on each side
LOG_SUBDIR = Path("logs") / "autotune"
HARNESS_OUT = Path("logs") / "harness"  # run.py writes logs/harness/LABEL.json under its repo
ENV_FILE = ".env"
SHA_CHARS = 12


class AutotuneError(Exception):
    """A refusal or failure the CLI reports in one line with a non-zero exit."""


class Paths:
    """Where everything lives, anchored at the main checkout."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.worktree = self.root.parent / WORKTREE_NAME
        self.logs = self.root / LOG_SUBDIR
        self.baseline = self.logs / "baseline.json"
        self.ledger = self.logs / "ledger.tsv"


def _git(cwd: Path, *args: str) -> str:
    proc = subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True)
    if proc.returncode != 0:
        raise AutotuneError(f"git {' '.join(args)}: {proc.stderr.strip()}")
    return proc.stdout.strip()


def main_checkout(start: Path) -> Path:
    """The main checkout, even when called from inside a linked worktree."""
    common = _git(start, "rev-parse", "--path-format=absolute", "--git-common-dir")
    return Path(common).parent


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _one_line(text: str) -> str:
    return " ".join(text.split())


# --- the worktree ---------------------------------------------------------------------------------


def init(paths: Paths) -> None:
    if paths.worktree.exists():
        check_worktree(paths)
        print(f"worktree ready: {paths.worktree} on {BRANCH}")
        return
    has_branch = subprocess.run(
        ["git", "-C", str(paths.root), "rev-parse", "--verify", "--quiet", f"refs/heads/{BRANCH}"],
        capture_output=True,
    )
    if has_branch.returncode == 0:
        _git(paths.root, "worktree", "add", str(paths.worktree), BRANCH)
    else:
        _git(paths.root, "worktree", "add", "-b", BRANCH, str(paths.worktree), BASE_BRANCH)
    # run.py loads .env from its own repo root (zoya.config.load_env); link, never copy, the keys.
    env = paths.root / ENV_FILE
    if env.exists() and not (paths.worktree / ENV_FILE).exists():
        (paths.worktree / ENV_FILE).symlink_to(env)
    check_worktree(paths)
    print(f"worktree created: {paths.worktree} on {BRANCH} from {BASE_BRANCH}")


def check_worktree(paths: Paths) -> None:
    """Refuse unless ../zoya-autotune is a linked worktree of this repo on the autotune branch."""
    if not paths.worktree.is_dir():
        raise AutotuneError(f"no worktree at {paths.worktree}: run `python -m evals.autotune init`")
    top = Path(_git(paths.worktree, "rev-parse", "--show-toplevel")).resolve()
    if top != paths.worktree.resolve() or top == paths.root:
        raise AutotuneError(f"{paths.worktree} is not its own worktree (top level {top})")
    if main_checkout(paths.worktree).resolve() != paths.root:
        raise AutotuneError(f"{paths.worktree} belongs to another repository")
    branch = _git(paths.worktree, "rev-parse", "--abbrev-ref", "HEAD")
    if branch != BRANCH:
        raise AutotuneError(f"{paths.worktree} is on {branch}, not {BRANCH}")


def _require_clean(paths: Paths) -> None:
    dirty = _git(paths.worktree, "status", "--porcelain")
    if dirty:
        raise AutotuneError(f"{paths.worktree} has uncommitted changes:\n{dirty}")


def _revert(paths: Paths, files: list[str]) -> None:
    _git(paths.worktree, "checkout", "--", ".")
    if files:
        _git(paths.worktree, "clean", "-f", "--", *files)


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


def run_eval(paths: Paths, label: str, group: str) -> list[dict]:
    command = eval_command(paths) + [label] + (["--group", group] if group else [])
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


def estimate_per_run(paths: Paths) -> float:
    """What one eval run is expected to cost: the current baseline's mean, else nothing known."""
    base = load_baseline(paths, required=False)
    if not base or not base["summaries"]:
        return 0.0
    return statistics.fmean(s["cents"] for s in base["summaries"])


def check_budget(book: ledger.Ledger, planned_cents: float) -> None:
    spent = book.spent_cents()
    budget = budget_cents()
    if spent + planned_cents > budget:
        raise AutotuneError(
            f"budget: spent {spent:.1f}¢ + estimate {planned_cents:.1f}¢ > {budget:.1f}¢ "
            f"({BUDGET_ENV})"
        )


def run_many(
    paths: Paths, book: ledger.Ledger, prefix: str, runs: int, group: str, summaries: list[dict]
) -> None:
    """Run the eval `runs` times, appending each summary as it lands so a failure keeps the spend.

    Before every run the ledger's spend, this command's spend so far and the estimate for the
    runs left must fit the budget, or nothing more starts."""
    per_run = estimate_per_run(paths)
    for index in range(runs):
        spent_here = sum(s["cents"] for s in summaries)
        check_budget(book, spent_here + per_run * (runs - index))
        summaries.append(score.summarize(run_eval(paths, f"autotune-{prefix}-{index + 1}", group)))


# --- baseline and ledger --------------------------------------------------------------------------


def load_baseline(paths: Paths, required: bool = True) -> dict[str, Any] | None:
    if not paths.baseline.exists():
        if required:
            raise AutotuneError("no baseline: run `python -m evals.autotune baseline` first")
        return None
    return json.loads(paths.baseline.read_text(encoding="utf-8"))


def _save_baseline(paths: Paths, group: str, summaries: list[dict], exp_id: str) -> None:
    paths.logs.mkdir(parents=True, exist_ok=True)
    data = {
        "utc": _now(),
        "exp_id": exp_id,
        "group": group,
        "commit": _git(paths.worktree, "rev-parse", "HEAD"),
        "summaries": summaries,
    }
    paths.baseline.write_text(json.dumps(data, indent=1), encoding="utf-8")


def _open_ledger(paths: Paths) -> ledger.Ledger:
    paths.logs.mkdir(parents=True, exist_ok=True)
    return ledger.Ledger(paths.ledger)


def _next_exp_id(book: ledger.Ledger) -> str:
    return f"{len(book.rows()) + 1:03d}"


def _record(
    book: ledger.Ledger,
    exp_id: str,
    description: str,
    patch_sha: str,
    summaries: list[dict],
    verdict: str,
) -> None:
    book.append(
        {
            "utc": _now(),
            "exp_id": exp_id,
            "description": _one_line(description),
            "patch_sha": patch_sha,
            "success_mean": (
                round(statistics.fmean(s["success"] for s in summaries), 3) if summaries else 0.0
            ),
            "cents_total": round(sum(s["cents"] for s in summaries), 3),
            "seconds_median": (
                round(statistics.median(s["median_seconds"] for s in summaries), 2)
                if summaries
                else 0.0
            ),
            "verdict": _one_line(verdict),
        }
    )


# --- commands -------------------------------------------------------------------------------------


def baseline(paths: Paths, runs: int, group: str) -> None:
    check_worktree(paths)
    _require_clean(paths)
    book = _open_ledger(paths)
    exp_id = _next_exp_id(book)
    commit = _git(paths.worktree, "rev-parse", "HEAD")[:SHA_CHARS]
    summaries: list[dict] = []
    try:
        run_many(paths, book, f"base{exp_id}", runs, group, summaries)
    except AutotuneError as err:
        if summaries:
            _record(book, exp_id, f"baseline {group or 'all'}", commit, summaries, f"error: {err}")
        raise
    _save_baseline(paths, group, summaries, exp_id)
    _record(book, exp_id, f"baseline {group or 'all'}", commit, summaries, "baseline")
    print(f"baseline {exp_id}: {[s['success'] for s in summaries]} of {summaries[0]['total']}")


def _patch_files(paths: Paths, patch: Path) -> list[str]:
    numstat = _git(paths.worktree, "apply", "--numstat", str(patch))
    return [line.split("\t", 2)[2] for line in numstat.splitlines() if line.count("\t") >= 2]


def try_patch(paths: Paths, patch_file: str, desc: str, runs: int, group: str) -> bool:
    """Guard, apply, run, decide, then keep (commit + new baseline) or discard (tree restored)."""
    patch = Path(patch_file).resolve()
    text = patch.read_text(encoding="utf-8")
    patch_sha = hashlib.sha256(text.encode("utf-8")).hexdigest()[:SHA_CHARS]
    book = _open_ledger(paths)
    exp_id = _next_exp_id(book)
    violations = surface.check_patch(text, paths.worktree)
    if violations:
        _record(book, exp_id, desc, patch_sha, [], "reject: " + "; ".join(violations))
        raise AutotuneError("rejected by the surface guard: " + "; ".join(violations))
    check_worktree(paths)
    base = load_baseline(paths)
    if base["group"] != group:
        raise AutotuneError(f"the baseline is for group {base['group']!r}, not {group!r}")
    _require_clean(paths)
    check_budget(book, estimate_per_run(paths) * runs)
    try:
        _git(paths.worktree, "apply", "--check", str(patch))
    except AutotuneError as err:
        _record(book, exp_id, desc, patch_sha, [], f"error: does not apply: {err}")
        raise
    files = _patch_files(paths, patch)
    _git(paths.worktree, "apply", str(patch))
    summaries: list[dict] = []
    try:
        run_many(paths, book, exp_id, runs, group, summaries)
        keep, reason = score.decide(base["summaries"], summaries)
    except BaseException as err:
        _revert(paths, files)
        _record(book, exp_id, desc, patch_sha, summaries, f"error: {err}")
        raise
    if keep:
        _git(paths.worktree, "add", "--", *files)
        _git(paths.worktree, "commit", "-q", "-m", f"chore: autotune {exp_id}: {_one_line(desc)}")
        _save_baseline(paths, group, summaries, exp_id)
    else:
        _revert(paths, files)
    verdict = f"{'keep' if keep else 'discard'}: {reason}"
    _record(book, exp_id, desc, patch_sha, summaries, verdict)
    print(f"experiment {exp_id}: {verdict}")
    return keep


def report(paths: Paths) -> Path:
    book = _open_ledger(paths)
    rows = book.rows()
    base = load_baseline(paths, required=False)
    verdicts = [str(row["verdict"]).split(":", 1)[0] for row in rows]
    today = datetime.now().astimezone().strftime("%Y-%m-%d")
    lines = [
        f"# Autotune report {today}",
        "",
        f"Spent {book.spent_cents():.1f}¢ of {budget_cents():.1f}¢ ({BUDGET_ENV}).",
        f"Experiments: {sum(v in ('keep', 'discard', 'reject', 'error') for v in verdicts)} "
        f"({verdicts.count('keep')} kept, {verdicts.count('discard')} discarded, "
        f"{verdicts.count('reject')} rejected, {verdicts.count('error')} errors).",
    ]
    if base:
        successes = [s["success"] for s in base["summaries"]]
        lines.append(
            f"Baseline: experiment {base['exp_id']}, commit {base['commit'][:SHA_CHARS]} on "
            f"{BRANCH}, group {base['group'] or 'all'}, success {successes} of "
            f"{base['summaries'][0]['total']}."
        )
    lines += [
        "",
        "| exp | utc | description | success | cents | seconds | verdict |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        cells = [
            row[key]
            for key in (
                "exp_id",
                "utc",
                "description",
                "success_mean",
                "cents_total",
                "seconds_median",
                "verdict",
            )
        ]
        lines.append("| " + " | ".join(str(c).replace("|", "\\|") for c in cells) + " |")
    out = paths.logs / f"report-{today}.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"report: {out}")
    return out


def _runs(value: str) -> int:
    runs = int(value)
    if runs < MIN_RUNS:
        raise argparse.ArgumentTypeError(f"needs at least {MIN_RUNS} runs to compare means")
    return runs


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m evals.autotune", description=__doc__)
    commands = parser.add_subparsers(dest="cmd", required=True)
    commands.add_parser("init", help="create ../zoya-autotune on branch autotune from main")
    base = commands.add_parser("baseline", help="run the eval N times and store the baseline")
    base.add_argument("--runs", type=_runs, default=MIN_RUNS)
    base.add_argument("--group", default="")
    trial = commands.add_parser("try", help="guard, apply and score one patch")
    trial.add_argument("patch")
    trial.add_argument("--desc", required=True)
    trial.add_argument("--runs", type=_runs, default=MIN_RUNS)
    trial.add_argument("--group", default="")
    commands.add_parser("report", help="write logs/autotune/report-<date>.md")
    args = parser.parse_args(argv)
    try:
        paths = Paths(main_checkout(Path.cwd()))
        if args.cmd == "init":
            init(paths)
        elif args.cmd == "baseline":
            baseline(paths, args.runs, args.group)
        elif args.cmd == "try":
            try_patch(paths, args.patch, args.desc, args.runs, args.group)
        else:
            report(paths)
    except AutotuneError as err:
        print(f"autotune: {err}", file=sys.stderr)
        return 1
    return 0
