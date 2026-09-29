"""evals/harness/grade.py: the harness's pure grading, which day sessions regrade with on Linux."""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from evals.harness import grade

TOKEN = "zoyaeval123401"


def check(task_checks: list[dict], said=(), asked=(), url="", shell=lambda _: "") -> list[str]:
    task = {"id": "t", "checks": task_checks}
    return grade.failed_checks(task, list(said), list(asked), url, TOKEN, shell)


def test_said_counts_matches_against_min() -> None:
    rule = [{"said": r"₹\s?\d", "min": 2}]
    assert check(rule, said=["₹499 and", "₹ 599"]) == []
    assert check(rule, said=["₹499 only"]) == [json.dumps(rule[0], ensure_ascii=False)]


def test_not_said_confirm_and_url_read_their_own_field() -> None:
    assert check([{"not_said": "error"}], said=["All good"]) == []
    assert check([{"not_said": "error"}], said=["An ERROR"])
    assert check([{"confirm": "subscribe"}], said=["subscribe"], asked=["Sign up?"])
    assert check([{"confirm": "subscribe"}], asked=["Subscribe to it?"]) == []
    assert check([{"url": r"ebay\."}], url="https://www.ebay.com/sch") == []
    assert check([{"url": r"ebay\."}], said=["ebay.com"])


def test_the_token_is_filled_in_and_shell_checks_use_the_given_shell() -> None:
    ran: list[str] = []

    def shell(command: str) -> str:
        ran.append(command)
        return f"note {TOKEN} milk"

    rule = [{"shell": "notes list {token}", "match": "{token} milk"}]
    assert check(rule, shell=shell) == []
    assert ran == [f"notes list {TOKEN}"]


def saved_run(**fields: object) -> dict:
    return {
        "id": "t",
        "said": [],
        "confirmations": [],
        "url": "",
        "failed_checks": [],
        "error": "",
        "success": False,
    } | fields


def test_regrade_replays_the_transcript_and_keeps_recorded_shell_results() -> None:
    shell_rule = {"shell": "ls", "match": "x"}
    task = {"id": "t", "checks": [{"said": "keyboard"}, shell_rule]}
    recorded = json.dumps(shell_rule, ensure_ascii=False)
    assert grade.regrade(task, saved_run(said=["a keyboard"], failed_checks=[recorded])) == [
        recorded
    ]
    assert (
        grade.regrade(task, saved_run(said=["a keyboard"], failed_checks=['{"said": "x"}'])) == []
    )
    assert grade.regrade(task, saved_run(said=["a mouse"])) == ['{"said": "keyboard"}']


def test_regrade_file_grades_a_saved_run_against_changed_checks(tmp_path: Path) -> None:
    tasks = tmp_path / "tasks.json"
    tasks.write_text(json.dumps([{"id": "t", "checks": [{"said": "mouse|mice"}]}]))
    runs = tmp_path / "runs.json"
    old = saved_run(said=["two mice"], failed_checks=['{"said": "mouse"}'])
    runs.write_text(json.dumps([old, saved_run(said=["mice"], error="over 300 s, stopped")]))
    graded = grade.regrade_file(runs, tasks)
    assert [(run["success"], run["failed_checks"]) for run in graded] == [(True, []), (False, [])]
    assert grade.main([str(runs), "--tasks", str(tasks)]) == 0


def test_regrade_never_runs_a_shell() -> None:
    task = {"id": "t", "checks": [{"shell": "rm -rf /", "match": "x"}]}
    with pytest.raises(ValueError):
        grade.failed_checks(task, [], [], "", "", grade._no_shell)
    assert grade.regrade(task, saved_run()) == []


def test_every_real_task_grades_without_a_shell_on_linux() -> None:
    for task in grade.load_tasks().values():
        grade.regrade(task, saved_run(id=task["id"]))


def test_grade_imports_only_the_standard_library() -> None:
    tree = ast.parse(Path(grade.__file__).read_text(encoding="utf-8"))
    imported = {
        (node.module or "") if isinstance(node, ast.ImportFrom) else alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import | ast.ImportFrom)
        for alias in node.names
    }
    assert not any(name.split(".")[0] in {"zoya", "evals"} for name in imported), imported


NIGHT_1_FAILURES = {
    "flipkart-search",
    "goodreads-search",
    "imdb-search",
    "boat-buy",
    "boat-newsletter",
    "wikipedia-open",
}


def test_six_held_out_tasks_spread_over_the_three_groups() -> None:
    tasks = grade.load_tasks().values()
    held = [task for task in tasks if task.get("held_out")]
    assert all(task["held_out"] is True for task in tasks if "held_out" in task)
    assert len(held) == 6
    groups = [task["group"] for task in held]
    assert {groups.count(group) for group in set(groups)} == {2} and len(set(groups)) == 3
    assert not {task["id"] for task in held} & NIGHT_1_FAILURES
