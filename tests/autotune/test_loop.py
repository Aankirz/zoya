"""The autotune runner against a temporary git repository and a fake, deterministic eval.

surface, score and ledger are built in parallel; these tests stand them in with minimal fakes
that follow the contract's signatures, so only loop.py is under test. Nothing here imports zoya.
"""

from __future__ import annotations

import csv
import hashlib
import importlib
import json
import shlex
import statistics
import subprocess
import sys
import types
from pathlib import Path

import pytest

from evals.autotune import surface as real_surface

SURFACE_FILES = {"zoya/config.py", "zoya/prompts.py"}
TASKS = 10
CENTS_PER_TASK = 5.0  # one fake eval run costs 50 cents
PLAIN_SUCCESSES = 5
TUNED_SUCCESSES = 8
TUNED_LINE = "MAX_FAILED_ATTEMPTS = 4"

FAKE_EVAL = f"""
import json, os, pathlib, sys

label = sys.argv[1]
tuned = {TUNED_LINE!r} in pathlib.Path("zoya/config.py").read_text()
with open(os.environ["FAKE_EVAL_LOG"], "a") as log:
    log.write(os.getcwd() + "\\t" + label + "\\n")
wins = {TUNED_SUCCESSES} if tuned else {PLAIN_SUCCESSES}
tasks = [
    {{"id": f"t{{i}}", "group": "mac app", "success": i < wins, "seconds": 10.0 + i,
      "cents": {CENTS_PER_TASK}, "steps": 3, "model_calls": 2, "jev_calls": 1, "error": None}}
    for i in range({TASKS})
]
out = pathlib.Path("logs/harness")
out.mkdir(parents=True, exist_ok=True)
(out / (label + ".json")).write_text(json.dumps(tasks))
"""


# --- stand-ins for the sibling modules (contract signatures only) ---------------------------------


def _check_patch(unified_diff: str, root: Path | None = None) -> list[str]:
    violations = []
    for line in unified_diff.splitlines():
        if line.startswith(("--- a/", "+++ b/")) and line[6:] not in SURFACE_FILES:
            violations.append(f"outside the surface: {line[6:]}")
    return violations


def _load(path) -> list[dict]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _summarize(runs: list[dict]) -> dict:
    by_group: dict[str, list[int]] = {}
    for run in runs:
        counts = by_group.setdefault(run["group"], [0, 0])
        counts[0] += bool(run["success"])
        counts[1] += 1
    return {
        "success": sum(bool(r["success"]) for r in runs),
        "total": len(runs),
        "by_group": by_group,
        "median_seconds": statistics.median(r["seconds"] for r in runs),
        "cents": sum(r["cents"] for r in runs),
    }


def _decide(baseline: list[dict], candidate: list[dict], min_gain: float = 1.0):
    base = statistics.fmean(s["success"] for s in baseline)
    cand = statistics.fmean(s["success"] for s in candidate)
    return (cand >= base + min_gain, f"success {base} -> {cand}")


COLUMNS = [
    "utc",
    "exp_id",
    "description",
    "patch_sha",
    "success_mean",
    "cents_total",
    "seconds_median",
    "verdict",
]


class _Ledger:
    def __init__(self, path) -> None:
        self.path = Path(path)

    def append(self, row: dict) -> None:
        new = not self.path.exists()
        with self.path.open("a", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, COLUMNS, delimiter="\t")
            if new:
                writer.writeheader()
            writer.writerow(row)

    def rows(self) -> list[dict]:
        if not self.path.exists():
            return []
        with self.path.open(newline="", encoding="utf-8") as fh:
            return list(csv.DictReader(fh, delimiter="\t"))

    def spent_cents(self) -> float:
        return sum(float(row["cents_total"]) for row in self.rows())


@pytest.fixture
def loop(monkeypatch: pytest.MonkeyPatch):
    import evals.autotune as package

    fakes = {
        "surface": {"check_patch": _check_patch},
        "score": {"load": _load, "summarize": _summarize, "decide": _decide},
        "ledger": {"Ledger": _Ledger},
    }
    for name, attrs in fakes.items():
        module = types.ModuleType(f"evals.autotune.{name}")
        module.__dict__.update(attrs)
        monkeypatch.setitem(sys.modules, module.__name__, module)
        monkeypatch.setattr(package, name, module, raising=False)
    monkeypatch.delitem(sys.modules, "evals.autotune.loop", raising=False)
    return importlib.import_module("evals.autotune.loop")


# --- a temporary repository, its worktree and the fake eval ---------------------------------------


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(cwd), *args], check=True, capture_output=True, text=True
    ).stdout.strip()


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, loop) -> Path:
    main = tmp_path / "zoya"
    (main / "zoya").mkdir(parents=True)
    (main / "zoya" / "config.py").write_text(
        "MAX_FAILED_ATTEMPTS = 3\nCOMPUTER_MAX_JEV_STEPS = 12\n"
    )
    (main / "zoya" / "prompts.py").write_text('PLAN = """Be brief.\nNever pay without asking."""\n')
    (main / "zoya" / "safety.py").write_text("CONFIRM = True\n")
    (main / ".gitignore").write_text("logs/\n")
    git(main, "init", "-q", "-b", "main")
    git(main, "config", "user.name", "autotune test")
    git(main, "config", "user.email", "autotune@example.invalid")
    git(main, "config", "commit.gpgsign", "false")
    git(main, "add", ".")
    git(main, "commit", "-q", "-m", "chore: start")
    fake = tmp_path / "fake_eval.py"
    fake.write_text(FAKE_EVAL)
    monkeypatch.setenv(
        "AUTOTUNE_EVAL_CMD", f"{shlex.quote(sys.executable)} {shlex.quote(str(fake))}"
    )
    monkeypatch.setenv("FAKE_EVAL_LOG", str(tmp_path / "evals.log"))
    monkeypatch.setenv("AUTOTUNE_BUDGET_CENTS", "1000")
    monkeypatch.chdir(main)
    assert loop.main(["init"]) == 0
    assert loop.main(["baseline", "--runs", "2", "--group", "mac app"]) == 0
    return main.resolve()


def worktree(repo: Path) -> Path:
    return repo.parent / "zoya-autotune"


def eval_calls(repo: Path) -> list[tuple[str, str]]:
    log = repo.parent / "evals.log"
    lines = log.read_text().splitlines() if log.exists() else []
    return [tuple(line.split("\t")) for line in lines]


def make_patch(repo: Path, name: str, path: str, old: str, new: str) -> Path:
    """A real `git diff` of one edit in the worktree, which is then put back."""
    wt = worktree(repo)
    target = wt / path
    target.write_text(target.read_text().replace(old, new))
    diff = subprocess.run(
        ["git", "-C", str(wt), "diff"], check=True, capture_output=True, text=True
    ).stdout
    git(wt, "checkout", "--", ".")
    patch = repo.parent / f"{name}.diff"
    patch.write_text(diff)
    return patch


def snapshot(root: Path) -> dict[str, str]:
    """Every file's bytes in the worktree except git's own data and the ignored eval output."""
    return {
        str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(root.rglob("*"))
        if p.is_file() and p.relative_to(root).parts[0] not in {".git", "logs"}
    }


def ledger_rows(repo: Path) -> list[dict]:
    return _Ledger(repo / "logs" / "autotune" / "ledger.tsv").rows()


def baseline_file(repo: Path) -> dict:
    return json.loads((repo / "logs" / "autotune" / "baseline.json").read_text())


# --- the properties -------------------------------------------------------------------------------


def test_guard_rejected_patch_never_runs_the_eval(loop, repo: Path) -> None:
    patch = make_patch(repo, "unsafe", "zoya/safety.py", "True", "False")
    before = (eval_calls(repo), snapshot(worktree(repo)), git(worktree(repo), "rev-parse", "HEAD"))

    code = loop.main(
        ["try", str(patch), "--desc", "loosen safety", "--runs", "2", "--group", "mac app"]
    )

    assert code == 1
    assert eval_calls(repo) == before[0]
    assert snapshot(worktree(repo)) == before[1]
    assert git(worktree(repo), "rev-parse", "HEAD") == before[2]
    assert ledger_rows(repo)[-1]["verdict"].startswith("reject:")
    assert float(ledger_rows(repo)[-1]["cents_total"]) == 0


def test_guard_reads_the_worktree_when_main_has_moved_on(
    loop, repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(loop, "surface", real_surface)
    config = repo / "zoya" / "config.py"
    config.write_text("RELAY_URL = 'x'\n" + config.read_text())
    git(repo, "commit", "-qam", "feat: main moves on")
    patch = make_patch(repo, "one-more", "zoya/config.py", "= 3", "= 4")

    code = loop.main(["try", str(patch), "--desc", "one more", "--runs", "2", "--group", "mac app"])

    assert code == 0
    assert not ledger_rows(repo)[-1]["verdict"].startswith("reject:")


def test_kept_patch_is_committed_and_becomes_the_new_baseline(loop, repo: Path) -> None:
    wt = worktree(repo)
    patch = make_patch(repo, "tuned", "zoya/config.py", "= 3", "= 4")
    main_head = git(repo, "rev-parse", "main")

    code = loop.main(
        ["try", str(patch), "--desc", "one more attempt", "--runs", "2", "--group", "mac app"]
    )

    assert code == 0
    assert TUNED_LINE in (wt / "zoya" / "config.py").read_text()
    assert git(wt, "status", "--porcelain") == ""
    assert git(wt, "log", "-1", "--format=%s") == "chore: autotune 002: one more attempt"
    assert git(wt, "rev-parse", "--abbrev-ref", "HEAD") == "autotune"
    assert git(repo, "rev-parse", "main") == main_head
    base = baseline_file(repo)
    assert base["commit"] == git(wt, "rev-parse", "HEAD")
    assert [s["success"] for s in base["summaries"]] == [TUNED_SUCCESSES, TUNED_SUCCESSES]
    assert ledger_rows(repo)[-1]["verdict"].startswith("keep:")


def test_discarded_patch_leaves_the_tree_byte_identical(loop, repo: Path) -> None:
    wt = worktree(repo)
    patch = make_patch(repo, "wordier", "zoya/prompts.py", "Be brief.", "Be brief and kind.")
    before = snapshot(wt)
    head = git(wt, "rev-parse", "HEAD")
    base = baseline_file(repo)
    calls = len(eval_calls(repo))

    code = loop.main(
        ["try", str(patch), "--desc", "kinder plan", "--runs", "2", "--group", "mac app"]
    )

    assert code == 0
    assert len(eval_calls(repo)) == calls + 2  # it did run, then lost
    assert snapshot(wt) == before
    assert git(wt, "status", "--porcelain") == ""
    assert git(wt, "rev-parse", "HEAD") == head
    assert baseline_file(repo) == base
    assert ledger_rows(repo)[-1]["verdict"].startswith("discard:")


def test_budget_stops_a_try_before_it_starts(
    loop, repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    wt = worktree(repo)
    patch = make_patch(repo, "tuned", "zoya/config.py", "= 3", "= 4")
    monkeypatch.setenv("AUTOTUNE_BUDGET_CENTS", "150")  # spent 100 + 2 runs x 50 estimate > 150
    before = (eval_calls(repo), snapshot(wt), len(ledger_rows(repo)))

    code = loop.main(
        ["try", str(patch), "--desc", "over budget", "--runs", "2", "--group", "mac app"]
    )

    assert code == 1
    assert eval_calls(repo) == before[0]
    assert snapshot(wt) == before[1]
    assert len(ledger_rows(repo)) == before[2]


def test_budget_stops_a_baseline_before_it_starts(
    loop, repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AUTOTUNE_BUDGET_CENTS", "99")  # 100 already spent
    calls = eval_calls(repo)

    assert loop.main(["baseline", "--runs", "2", "--group", "mac app"]) == 1
    assert eval_calls(repo) == calls


def test_worktree_is_the_sibling_never_the_main_checkout(loop, repo: Path) -> None:
    wt = worktree(repo)
    patch = make_patch(repo, "tuned", "zoya/config.py", "= 3", "= 4")
    main_files = snapshot(repo)
    assert (
        loop.main(["try", str(patch), "--desc", "tuned", "--runs", "2", "--group", "mac app"]) == 0
    )

    assert loop.Paths(repo).worktree == repo.parent / "zoya-autotune"
    assert {Path(cwd).resolve() for cwd, _ in eval_calls(repo)} == {wt.resolve()}
    assert snapshot(repo) == main_files
    assert git(repo, "rev-parse", "--abbrev-ref", "HEAD") == "main"
    assert not (repo / "logs" / "harness").exists()
    # From inside the worktree the runner still anchors at the main checkout.
    assert loop.main_checkout(wt).resolve() == repo


def test_refuses_a_worktree_on_another_branch(
    loop, repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    git(worktree(repo), "checkout", "-q", "-b", "elsewhere")
    patch = make_patch(repo, "tuned", "zoya/config.py", "= 3", "= 4")
    calls = eval_calls(repo)

    assert (
        loop.main(["try", str(patch), "--desc", "tuned", "--runs", "2", "--group", "mac app"]) == 1
    )
    assert eval_calls(repo) == calls


def test_report_lists_every_experiment(loop, repo: Path) -> None:
    patch = make_patch(repo, "tuned", "zoya/config.py", "= 3", "= 4")
    loop.main(
        ["try", str(patch), "--desc", "one more attempt", "--runs", "2", "--group", "mac app"]
    )

    assert loop.main(["report"]) == 0
    (report,) = (repo / "logs" / "autotune").glob("report-*.md")
    text = report.read_text()
    assert "one more attempt" in text
    assert "1 kept" in text
