"""The autotune night against a temporary git repository, its bare origin and a fake eval.

The fake eval reads zoya/behaviour.json in the checkout it runs in, so a candidate branch changes
what passes by committing a different one. Nothing here imports zoya.
"""

from __future__ import annotations

import ast
import json
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from evals.autotune import ledger, loop, pertask

NIGHT = "2026-09-30"
CENTS = 1.0
TASKS = [
    {"id": "search-a", "group": "web", "command": "find a", "checks": [{"said": "a"}]},
    {"id": "search-b", "group": "web", "command": "find b", "checks": [{"said": "b"}]},
    {"id": "open-c", "group": "web", "command": "open c", "checks": [{"url": "c"}]},
    {"id": "open-d", "group": "web", "command": "open d", "checks": [{"url": "d"}]},
    {"id": "held-web", "group": "web", "held_out": True, "command": "h", "checks": [{"said": "h"}]},
    {"id": "note-e", "group": "mac", "command": "note e", "checks": [{"said": "e"}]},
    {"id": "held-mac", "group": "mac", "held_out": True, "command": "m", "checks": [{"said": "m"}]},
]
BEHAVIOUR = {task["id"]: not task["id"].startswith("search") for task in TASKS}
PRIVATE_SAID = "Mail owner@private.example or call 919876543210 about it."
PRIVATE_TOOL = 'browser_type {"text": "hunter2"}'
PRIVATE_URL = "https://shop.example/account?token=s3cret"

FAKE_EVAL = f"""
import json, os, pathlib, sys

label = sys.argv[1]
only = sys.argv[3].split(",") if len(sys.argv) > 3 and sys.argv[2] == "--only" else []
tasks = json.loads(pathlib.Path("evals/harness/tasks.json").read_text())
behaviour = json.loads(pathlib.Path("zoya/behaviour.json").read_text())
with open(os.environ["FAKE_EVAL_LOG"], "a") as log:
    log.write("\\t".join([os.getcwd(), label, ",".join(only)]) + "\\n")
runs = []
for task in tasks:
    if only and task["id"] not in only:
        continue
    ok = behaviour.get(task["id"], True)
    runs.append({{
        "id": task["id"], "group": task["group"], "command": task["command"], "success": ok,
        "steps": 3, "model_calls": 2, "jev_calls": 0, "seconds": 10.0, "cents": {CENTS},
        "said": [] if ok else [{PRIVATE_SAID!r}], "confirmations": [],
        "url": {PRIVATE_URL!r}, "failed_checks": [] if ok else [json.dumps(task["checks"][0])],
        "route": "", "error": "", "leftover": "", "tools": [{PRIVATE_TOOL!r}, "browser_task {{}}"],
        "tabs": 1, "blank_tabs": 0,
    }})
out = pathlib.Path("logs/harness")
out.mkdir(parents=True, exist_ok=True)
(out / (label + ".json")).write_text(json.dumps(runs))
"""
FAKE_CHECK = "import pathlib, sys\nsys.exit(1 if pathlib.Path('BROKEN').exists() else 0)\n"


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(cwd), *args], check=True, capture_output=True, text=True
    ).stdout.strip()


def write(root: Path, files: dict[str, object]) -> None:
    for name, content in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        text = content if isinstance(content, str) else json.dumps(content, indent=1)
        path.write_text(text, encoding="utf-8")


def commit(root: Path, message: str, files: dict[str, object]) -> str:
    write(root, files)
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", message)
    return git(root, "rev-parse", "HEAD")


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    origin = tmp_path / "origin.git"
    git(tmp_path, "init", "-q", "--bare", "-b", "main", str(origin))
    main = tmp_path / "zoya"
    main.mkdir()
    git(main, "init", "-q", "-b", "main")
    for key, value in (
        ("user.name", "autotune test"),
        ("user.email", "autotune@example.invalid"),
        ("commit.gpgsign", "false"),
    ):
        git(main, "config", key, value)
    files = {
        ".gitignore": "logs/\n",
        "evals/harness/tasks.json": TASKS,
        "evals/harness/run.py": "RUN = 1\n",
        "evals/harness/grade.py": "GRADE = 1\n",
        "zoya/behaviour.json": BEHAVIOUR,
        "zoya/safety.py": "CONFIRM = True\n",
        "zoya/tools.py": "x = 1\n",
        "tests/test_existing.py": "def test_x():\n    assert True\n",
    }
    commit(main, "chore: start", files)
    git(main, "remote", "add", "origin", str(origin))
    git(main, "push", "-q", "-u", "origin", "main")
    fake, check = tmp_path / "fake_eval.py", tmp_path / "check.py"
    fake.write_text(FAKE_EVAL)
    check.write_text(FAKE_CHECK)
    python = shlex.quote(sys.executable)
    monkeypatch.setenv("AUTOTUNE_EVAL_CMD", f"{python} {shlex.quote(str(fake))}")
    monkeypatch.setenv("AUTOTUNE_CHECK_CMD", f"{python} {shlex.quote(str(check))}")
    monkeypatch.setenv("FAKE_EVAL_LOG", str(tmp_path / "evals.log"))
    monkeypatch.setenv("AUTOTUNE_BUDGET_CENTS", "1000")
    monkeypatch.setenv("AUTOTUNE_NIGHT", NIGHT)
    monkeypatch.delenv("AUTOTUNE_DEADLINE", raising=False)
    monkeypatch.chdir(main)
    return main.resolve()


def paths(repo: Path) -> loop.Paths:
    return loop.Paths(repo)


def worktree(repo: Path) -> Path:
    return repo.parent / "zoya-autotune"


def eval_calls(repo: Path) -> list[tuple[str, str, str]]:
    log = repo.parent / "evals.log"
    lines = log.read_text().splitlines() if log.exists() else []
    return [tuple(line.split("\t")) for line in lines]


def seed(repo: Path, task: str, passes: list[bool], cents: float = CENTS) -> None:
    """Census rows for one task on main's current commit, one night each, before NIGHT."""
    sha = git(repo, "rev-parse", "origin/main")
    group = next(t["group"] for t in TASKS if t["id"] == task)
    book = ledger.Ledger(paths(repo).history)
    for day, ok in enumerate(passes, 1):
        book.append(
            {
                "night": f"2026-09-{day:02d}",
                "sha": sha,
                "task": task,
                "group": group,
                "success": int(ok),
                "cents": cents,
                "seconds": 10.0,
                "cause": "pass" if ok else "wrong-answer",
            }
        )


def seed_usual(repo: Path) -> None:
    """Six census nights at each task's usual outcome: search-* FAIL, every other task PASS."""
    for task, ok in BEHAVIOUR.items():
        seed(repo, task, [ok] * pertask.WINDOW)


def push_main(repo: Path, message: str, files: dict[str, object]) -> str:
    sha = commit(repo, message, files)
    git(repo, "push", "-q", "origin", "main")
    return sha


def candidate(repo: Path, branch: str, files: dict[str, object], targets: str = "search-a") -> str:
    git(repo, "checkout", "-q", "-b", branch, "origin/main")
    message = f"fix: {branch}" + (f"\n\nAutotune-Targets: {targets}" if targets else "")
    sha = commit(repo, message, files)
    git(repo, "push", "-q", "origin", branch)
    git(repo, "checkout", "-q", "main")
    return sha


def behaving(**changes: bool) -> dict[str, object]:
    return {"zoya/behaviour.json": {**BEHAVIOUR, **changes}}


def night_json(repo: Path) -> dict:
    return json.loads(paths(repo).night_file(NIGHT, ".json").read_text())


# --- sync -----------------------------------------------------------------------------------------


def test_sync_resets_a_stale_worktree_to_origin_main(repo: Path) -> None:
    assert loop.main(["sync"]) == 0
    wt = worktree(repo)
    assert git(wt, "rev-parse", "HEAD") == git(repo, "rev-parse", "origin/main")
    git(wt, "checkout", "-q", "--detach", "HEAD")
    write(wt, {"zoya/tools.py": "x = 'dirty'\n", "stray.txt": "left over"})
    fixed = push_main(repo, "fix: main moves on", {"zoya/tools.py": "x = 2\n"})

    assert loop.main(["sync"]) == 0

    assert git(wt, "rev-parse", "HEAD") == fixed
    assert git(wt, "rev-parse", "--abbrev-ref", "HEAD") == "HEAD"
    assert git(wt, "status", "--porcelain") == ""
    assert (wt / "zoya" / "tools.py").read_text() == "x = 2\n"


def test_a_failing_check_stops_the_night_and_the_report_says_why(repo: Path) -> None:
    push_main(repo, "chore: break the check", {"BROKEN": "yes"})

    assert loop.main(["sync"]) == 1
    assert loop.main(["census"]) == 1
    assert loop.main(["verify"]) == 1
    assert eval_calls(repo) == []

    assert loop.main(["report"]) == 0
    text = paths(repo).report(NIGHT).read_text()
    assert "The night stopped at sync" in text and "failed with exit 1" in text


# --- census ---------------------------------------------------------------------------------------


def test_census_runs_every_task_once_in_the_worktree_and_records_it(repo: Path) -> None:
    assert loop.main(["sync"]) == 0
    assert loop.main(["census"]) == 0

    assert eval_calls(repo) == [(str(worktree(repo)), f"census-{NIGHT}-1", "")]
    rows = ledger.Ledger(paths(repo).history).rows()
    assert [row["task"] for row in rows] == [task["id"] for task in TASKS]
    sha = git(repo, "rev-parse", "origin/main")
    assert {(row["night"], row["sha"]) for row in rows} == {(NIGHT, sha)}
    by_task = {row["task"]: row for row in rows}
    assert by_task["search-a"]["success"] == "0" and by_task["search-a"]["cause"] == "wrong-answer"
    assert by_task["open-c"]["success"] == "1" and by_task["open-c"]["cause"] == "pass"
    assert not (repo / "logs" / "harness").exists()


def test_flaky_tasks_get_two_extra_runs(repo: Path) -> None:
    seed(repo, "open-c", [True, False, True, False, True, False])
    assert loop.main(["sync"]) == 0
    assert loop.main(["census"]) == 0

    assert [call[1:] for call in eval_calls(repo)] == [
        (f"census-{NIGHT}-1", ""),
        (f"census-{NIGHT}-2", "open-c"),
        (f"census-{NIGHT}-3", "open-c"),
    ]
    rows = [r for r in ledger.Ledger(paths(repo).history).rows() if r["night"] == NIGHT]
    assert sum(row["task"] == "open-c" for row in rows) == 3


def test_a_pass_task_failing_tonight_is_the_new_fail_alarm_listed_first(repo: Path) -> None:
    seed_usual(repo)
    push_main(repo, "chore: open-d regresses", behaving(**{"open-d": False}))
    for command in ("sync", "census", "triage"):
        assert loop.main([command]) == 0

    data = night_json(repo)
    assert data["classes"]["open-d"] == pertask.NEW_FAIL
    assert list(data["classes"])[0] == "open-d"
    assert data["triage"][0]["task"] == "open-d"
    text = paths(repo).night_file(NIGHT, ".md").read_text()
    assert text.index("open-d") < text.index("## Candidates")


def test_a_task_history_resets_when_its_entry_changes(repo: Path) -> None:
    seed_usual(repo)
    changed = [{**t, "checks": [{"said": "a|A"}]} if t["id"] == "search-a" else t for t in TASKS]
    marked = [{**t, "held_out": True} if t["id"] == "open-c" else t for t in changed]
    push_main(repo, "fix: search-a's check", {"evals/harness/tasks.json": marked})
    assert loop.main(["sync"]) == 0

    kept = loop.history(paths(repo), loop.worktree_tasks(paths(repo)))
    assert kept["search-a"] == []
    assert len(kept["search-b"]) == len(kept["open-c"]) == pertask.WINDOW


# --- the budget -----------------------------------------------------------------------------------


def test_the_budget_is_per_night_so_a_ninth_night_still_runs(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for task in BEHAVIOUR:
        seed(repo, task, [True] * 8, cents=900 / len(BEHAVIOUR))
    history = ledger.Ledger(paths(repo).history)
    assert sum(float(row["cents"]) for row in history.rows()) > loop.budget_cents()
    monkeypatch.setenv("AUTOTUNE_NIGHT", "2026-09-09")

    assert loop.main(["sync"]) == 0
    assert loop.main(["census"]) == 0
    assert len(eval_calls(repo)) == 1


def test_a_night_over_its_budget_starts_no_eval(repo: Path, monkeypatch: pytest.MonkeyPatch):
    assert loop.main(["sync"]) == 0
    assert loop.main(["census"]) == 0
    monkeypatch.setenv("AUTOTUNE_BUDGET_CENTS", str(len(TASKS) * CENTS + 1))

    assert loop.main(["census"]) == 1
    assert len(eval_calls(repo)) == 1


def test_no_eval_starts_after_the_deadline(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    assert loop.main(["sync"]) == 0
    monkeypatch.setenv("AUTOTUNE_DEADLINE", "1")
    assert loop.main(["census"]) == 1
    assert eval_calls(repo) == []


# --- queue ----------------------------------------------------------------------------------------


def queue_rows(repo: Path) -> list[dict]:
    return ledger.Ledger(paths(repo).queue, loop.QUEUE_COLUMNS).rows()


def test_queue_pins_a_clean_branch_and_prints_its_flags_first(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    sha = candidate(
        repo,
        "autotune/fix-a",
        {**behaving(**{"search-a": True}), "zoya/safety.py": "CONFIRM = 1\n"},
    )

    assert loop.main(["queue", "autotune/fix-a"]) == 0

    out = capsys.readouterr().out
    assert out.startswith("FLAG zoya/safety.py")
    assert "zoya/behaviour.json" in out and "targets: search-a" in out
    (pin,) = queue_rows(repo)
    assert (pin["branch"], pin["sha"], pin["targets"]) == ("autotune/fix-a", sha, "search-a")
    assert pin["ref"] == "refs/remotes/origin/autotune/fix-a"


@pytest.mark.parametrize(
    ("files", "targets"),
    [
        ({"tests/test_existing.py": "def test_x():\n    pass\n"}, "search-a"),
        ({"evals/harness/run.py": "RUN = 2\n"}, "search-a"),
        ({"tests/conftest.py": "import pytest\n"}, "search-a"),
        ({"zoya/tools.py": "x = 'flipkart'\n"}, "search-a"),
        ({"zoya/tools.py": "x = 3\n"}, ""),
        ({"zoya/tools.py": "x = 3\n"}, "no-such-task"),
        ({"zoya/tools.py": "x = 3\n"}, "held-web"),
    ],
)
def test_queue_refuses_a_guarded_branch(repo: Path, files: dict, targets: str) -> None:
    candidate(repo, "autotune/fix-bad", files, targets)
    assert loop.main(["queue", "autotune/fix-bad"]) == 1
    assert queue_rows(repo) == []


# --- verify ---------------------------------------------------------------------------------------


def ready(repo: Path) -> None:
    seed_usual(repo)
    assert loop.main(["sync"]) == 0
    assert loop.main(["census"]) == 0


def verdicts(repo: Path) -> list[dict]:
    return ledger.Ledger(paths(repo).verdicts, loop.VERDICT_COLUMNS).rows()


SENTINELS = "held-mac,held-web,open-c,open-d,search-b"


def test_verify_proves_a_fix_on_its_pinned_sha(repo: Path) -> None:
    sha = candidate(repo, "autotune/fix-a", behaving(**{"search-a": True}))
    assert loop.main(["queue", "autotune/fix-a"]) == 0
    ready(repo)
    before = len(eval_calls(repo))

    assert loop.main(["verify"]) == 0

    label = f"verify-{NIGHT}-{sha[:loop.SHA_CHARS]}"
    assert [call[1:] for call in eval_calls(repo)[before:]] == [
        (f"{label}-t1", "search-a"),
        (f"{label}-t2", "search-a"),
        (f"{label}-t3", "search-a"),
        (f"{label}-s1", SENTINELS),
    ]
    assert {call[0] for call in eval_calls(repo)} == {str(worktree(repo))}
    assert git(worktree(repo), "rev-parse", "HEAD") == sha
    (row,) = verdicts(repo)
    assert (row["sha"], row["status"], row["fixed"]) == (sha, pertask.PROVEN, "search-a")
    assert git(repo, "rev-parse", "origin/main") != sha
    assert loop.main(["verify"]) == 0
    assert len(verdicts(repo)) == 1


def test_a_branch_that_moved_after_pinning_is_skipped(repo: Path) -> None:
    candidate(repo, "autotune/fix-a", behaving(**{"search-a": True}))
    assert loop.main(["queue", "autotune/fix-a"]) == 0
    git(repo, "checkout", "-q", "autotune/fix-a")
    commit(repo, "fix: more", {"zoya/tools.py": "x = 9\n"})
    git(repo, "push", "-q", "origin", "autotune/fix-a")
    git(repo, "checkout", "-q", "main")
    ready(repo)
    before = len(eval_calls(repo))

    assert loop.main(["verify"]) == 0

    assert len(eval_calls(repo)) == before
    (row,) = verdicts(repo)
    assert row["status"] == loop.SKIPPED and "moved" in row["reason"]


def test_a_broken_sentinel_is_rerun_twice_then_rejects(repo: Path) -> None:
    sha = candidate(repo, "autotune/fix-a", behaving(**{"search-a": True, "open-c": False}))
    assert loop.main(["queue", "autotune/fix-a"]) == 0
    ready(repo)
    before = len(eval_calls(repo))

    assert loop.main(["verify"]) == 0

    label = f"verify-{NIGHT}-{sha[:loop.SHA_CHARS]}"
    assert [call[1:] for call in eval_calls(repo)[before + 4 :]] == [
        (f"{label}-r1", "open-c"),
        (f"{label}-r2", "open-c"),
    ]
    (row,) = verdicts(repo)
    assert (row["status"], row["broken"]) == (pertask.REJECTED, "open-c")


def test_a_broken_held_out_task_vetoes_the_fix(repo: Path) -> None:
    candidate(repo, "autotune/fix-a", behaving(**{"search-a": True, "held-mac": False}))
    assert loop.main(["queue", "autotune/fix-a"]) == 0
    ready(repo)

    assert loop.main(["verify"]) == 0

    (row,) = verdicts(repo)
    assert row["status"] == pertask.REJECTED and "held-out" in row["reason"]


def test_a_flaky_target_passing_every_run_is_consistent(repo: Path) -> None:
    seed_usual(repo)
    seed(repo, "search-b", [True, True, False] * 2)
    candidate(repo, "autotune/fix-b", behaving(**{"search-b": True}), "search-b")
    assert loop.main(["queue", "autotune/fix-b"]) == 0
    assert loop.main(["sync"]) == 0
    assert loop.main(["census"]) == 0

    assert loop.main(["verify"]) == 0
    assert verdicts(repo)[0]["status"] == pertask.CONSISTENT


def test_a_candidate_whose_check_fails_is_rejected_without_an_eval(repo: Path) -> None:
    candidate(repo, "autotune/fix-a", {**behaving(**{"search-a": True}), "BROKEN": "yes"})
    assert loop.main(["queue", "autotune/fix-a"]) == 0
    ready(repo)
    before = len(eval_calls(repo))

    assert loop.main(["verify"]) == 0
    assert len(eval_calls(repo)) == before
    assert verdicts(repo)[0]["status"] == pertask.REJECTED


def test_verify_judges_at_most_three_candidates_a_night(repo: Path) -> None:
    for index in range(loop.MAX_CANDIDATES + 1):
        candidate(
            repo, f"autotune/fix-{index}", {**behaving(**{"search-a": True}), "n": str(index)}
        )
        assert loop.main(["queue", f"autotune/fix-{index}"]) == 0
    ready(repo)

    assert loop.main(["verify"]) == 0

    assert len(verdicts(repo)) == loop.MAX_CANDIDATES
    assert [pin["branch"] for pin in loop.pending_pins(paths(repo))] == ["autotune/fix-3"]


# --- triage, publish and report -------------------------------------------------------------------


def test_triage_redacts_evidence_and_shows_held_out_tasks_as_pass_or_fail(repo: Path) -> None:
    seed_usual(repo)
    push_main(repo, "chore: held-mac fails", behaving(**{"held-mac": False}))
    for command in ("sync", "census", "triage"):
        assert loop.main([command]) == 0

    data = night_json(repo)
    published = json.dumps(data) + paths(repo).night_file(NIGHT, ".md").read_text()
    for secret in ("private.example", "919876543210", "hunter2", "token=", "s3cret"):
        assert secret not in published
    assert [r["task"] for r in data["triage"]] == ["search-a", "search-b"]
    assert data["triage"][0]["tools"] == ["browser_type", "browser_task"]
    assert data["triage"][0]["url"] == "https://shop.example/account"
    assert data["held_out"] == [
        {"task": "held-mac", "held_out": True, "result": "fail"},
        {"task": "held-web", "held_out": True, "result": "pass"},
    ]
    assert not {"held-mac", "held-web"} & set(data["classes"])


def data_files(repo: Path) -> list[str]:
    return git(repo, "ls-tree", "-r", "--name-only", "origin/autotune-data").splitlines()


def test_publish_pushes_only_the_data_branch(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ready(repo)
    main_sha = git(repo, "rev-parse", "origin/main")
    assert loop.main(["triage"]) == 0

    assert loop.main(["publish"]) == 0

    git(repo, "fetch", "-q", "origin")
    assert data_files(repo) == [f"nights/{NIGHT}.json", f"nights/{NIGHT}.md"]
    assert git(repo, "rev-list", "--count", "origin/autotune-data") == "1"
    assert git(repo, "rev-parse", "origin/main") == main_sha
    assert loop.main(["publish"]) == 0
    git(repo, "fetch", "-q", "origin")
    assert git(repo, "rev-list", "--count", "origin/autotune-data") == "1"

    monkeypatch.setenv("AUTOTUNE_NIGHT", "2026-10-01")
    for command in ("sync", "census", "triage", "publish"):
        assert loop.main([command]) == 0
    git(repo, "fetch", "-q", "origin")
    assert len(data_files(repo)) == 4
    assert git(repo, "rev-list", "--count", "origin/autotune-data") == "2"


def test_publish_needs_triage_first(repo: Path) -> None:
    assert loop.main(["publish"]) == 1


def test_report_holds_the_night_and_what_stayed_on_the_mac(repo: Path) -> None:
    sha = candidate(repo, "autotune/fix-a", behaving(**{"search-a": True}))
    assert loop.main(["queue", "autotune/fix-a"]) == 0
    ready(repo)
    for command in ("verify", "triage", "publish", "report"):
        assert loop.main([command]) == 0

    text = paths(repo).report(NIGHT).read_text()
    assert f"**autotune/fix-a** {sha[:loop.SHA_CHARS]}: **proven**" in text
    assert "## On this Mac" in text and "Pins still waiting: none" in text
    assert "Published: " in text and "Published: no" not in text


# --- the package ----------------------------------------------------------------------------------


def test_nothing_under_evals_autotune_imports_zoya() -> None:
    package = Path(loop.__file__).parent
    for source in package.rglob("*.py"):
        tree = ast.parse(source.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            else:
                continue
            assert not any(name.split(".")[0] == "zoya" for name in names), source


# --- the night script -----------------------------------------------------------------------------

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "autotune-night.sh"
STEPS = ("sync", "census", "verify", "triage", "publish", "report")


def test_the_night_script_parses_and_runs_no_agent() -> None:
    assert subprocess.run(["bash", "-n", str(SCRIPT)]).returncode == 0
    text = SCRIPT.read_text()
    assert "claude" not in text.replace("claude.ai", "")
    assert "exec caffeinate -i" in text and "STOP_HOUR=7" in text and "gzip -f" in text


def night_script(repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """The real script and package in the temporary repo, with a caffeinate that just runs."""
    (repo / "scripts").mkdir()
    shutil.copy2(SCRIPT, repo / "scripts" / SCRIPT.name)
    (repo / "evals" / "autotune").symlink_to(Path(loop.__file__).parent)
    (repo / ".venv" / "bin").mkdir(parents=True)
    (repo / ".venv" / "bin" / "python").symlink_to(sys.executable)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "caffeinate").write_text('#!/bin/sh\n[ "$1" = "-i" ] && shift\nexec "$@"\n')
    (bin_dir / "caffeinate").chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}:{Path(sys.executable).parent}:/usr/bin:/bin")
    monkeypatch.delenv("AUTOTUNE_CAFFEINATED", raising=False)
    return repo / "scripts" / SCRIPT.name


def test_the_night_script_runs_every_step_in_order(
    repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    script = night_script(repo, tmp_path, monkeypatch)

    done = subprocess.run(["bash", str(script), "--now"], capture_output=True, text=True)

    assert done.returncode == 0, done.stdout + done.stderr
    started = [line.split()[1] for line in done.stdout.splitlines() if " starts " in line]
    assert started == list(STEPS)
    assert [call[1].split("-")[0] for call in eval_calls(repo)] == ["census"]
    git(repo, "fetch", "-q", "origin")
    assert len(data_files(repo)) == 2
    (log,) = (repo / "logs" / "autotune").glob("night-*.log")
    assert "report: " in log.read_text()


def test_the_night_script_stops_at_a_failed_sync_and_still_reports(
    repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    push_main(repo, "chore: break the check", {"BROKEN": "yes"})
    script = night_script(repo, tmp_path, monkeypatch)

    done = subprocess.run(["bash", str(script), "--now"], capture_output=True, text=True)

    assert done.returncode == 1
    started = [line.split()[1] for line in done.stdout.splitlines() if " starts " in line]
    assert started == ["sync", "report"]
    assert eval_calls(repo) == []
    (report,) = (repo / "logs" / "autotune").glob("report-*.md")
    assert "The night stopped at sync" in report.read_text()
