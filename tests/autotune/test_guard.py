"""The candidate-branch guard: each Safety case is refused, gate changes are flagged."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from evals.autotune import guard
from evals.harness import grade


def edit(path: str, old: str, new: str) -> str:
    return (
        f"diff --git a/{path} b/{path}\n"
        "index 1111111..2222222 100644\n"
        f"--- a/{path}\n"
        f"+++ b/{path}\n"
        "@@ -1,3 +1,3 @@\n"
        " def f():\n"
        f"-    {old}\n"
        f"+    {new}\n"
        "     return x\n"
    )


def new_file(path: str, *lines: str) -> str:
    return (
        f"diff --git a/{path} b/{path}\n"
        "new file mode 100644\n"
        "index 0000000..3333333\n"
        "--- /dev/null\n"
        f"+++ b/{path}\n"
        f"@@ -0,0 +1,{len(lines)} @@\n" + "".join(f"+{line}\n" for line in lines)
    )


def deleted(path: str) -> str:
    return (
        f"diff --git a/{path} b/{path}\n"
        "deleted file mode 100644\n"
        "index 3333333..0000000\n"
        f"--- a/{path}\n"
        "+++ /dev/null\n"
        "@@ -1 +0,0 @@\n"
        "-x = 1\n"
    )


WEB_FIX = edit("zoya/tools/browser.py", "x = find_field(page)", "x = find_field(page, role=True)")


def test_a_generic_fix_with_a_new_test_and_fixture_passes() -> None:
    diff = (
        WEB_FIX
        + new_file("tests/test_find_field.py", "def test_x(): pass")
        + new_file("tests/fixtures/web/search.html", "<form role=search></form>")
    )
    assert guard.check(diff) == guard.Result([], [])


@pytest.mark.parametrize(
    "path",
    [
        "evals/harness/run.py",
        "evals/harness/grade.py",
        "evals/autotune/pertask.py",
        "evals/autotune/guard.py",
        "scripts/autotune-night.sh",
        "Makefile",
        "tests/test_step_loop.py",
        "tests/test_no_site_hardcoding.py",
        "tests/conftest.py",
    ],
)
def test_the_judge_and_existing_tests_are_refused(path: str) -> None:
    violations = guard.check(edit(path, "a = 1", "a = 2")).violations
    assert violations and path in violations[0]


@pytest.mark.parametrize("path", ["tests/conftest.py", "tests/fixtures/web/conftest.py"])
def test_a_new_conftest_is_refused(path: str) -> None:
    assert guard.check(new_file(path, "import pytest")).violations


def test_deleting_an_existing_test_is_refused() -> None:
    assert guard.check(deleted("tests/test_safety.py")).violations


@pytest.mark.parametrize("name", guard.PROTECTED_CONSTANTS)
def test_protected_constants_are_refused(name: str) -> None:
    violations = guard.check(edit("zoya/config.py", f"{name} = 0.70", f"{name} = 0.60")).violations
    assert len(violations) == 2 and all("protected constant" in v for v in violations)
    assert guard.check(edit("zoya/agents/step_loop.py", "x = 1", f"x = {name} - 0.1")).violations


def test_a_protected_prompt_line_is_refused_but_other_prompt_text_passes() -> None:
    assert guard.check(edit("zoya/prompts.py", "Always confirm first.", "Just do it.")).violations
    assert guard.check(edit("zoya/prompts.py", "Be brief.", "Be brief and kind.")) == guard.Result()


def test_a_site_name_added_to_zoya_is_refused() -> None:
    for line in ("# flipkart hides its search box", "if 'IMDb' in title:", "HOST = 'www.ebay.in'"):
        assert guard.check(edit("zoya/tools/browser.py", "x = 1", line)).violations, line
    assert guard.check(edit("zoya/tools/browser.py", "x = 1", "x = embay + imdbx")) == (
        guard.Result()
    )
    assert guard.check(new_file("tests/test_search.py", "# flipkart's search box")) == (
        guard.Result()
    )


def test_every_site_name_is_one_the_tasks_use() -> None:
    commands = " ".join(task["command"] for task in grade.load_tasks().values()).casefold()
    assert [name for name in guard.SITE_NAMES if name not in commands] == []


def test_the_changed_line_cap_leaves_fixtures_out() -> None:
    lines = [f"x{i} = {i}" for i in range(guard.MAX_CHANGED_LINES + 1)]
    assert guard.check(new_file("zoya/big.py", *lines)).violations
    assert guard.check(new_file("tests/fixtures/web/big.html", *lines)) == guard.Result()


def test_an_unreadable_diff_fails_closed() -> None:
    assert guard.check("not a diff\n").violations
    assert guard.check('diff --git "a/x y" "b/x y"\n').violations
    assert guard.check(WEB_FIX.replace("b/zoya/tools/browser.py", "b/zoya/other.py", 1)).violations
    binary = "diff --git a/zoya/a.png b/zoya/a.png\nGIT binary patch\n"
    assert guard.check(binary).violations


TASKS = [
    {"id": "buy", "group": "g", "stakes": "money", "checks": [{"confirm": "buy|order"}]},
    {"id": "find", "group": "g", "checks": [{"said": "x"}]},
    {"id": "held", "group": "g", "held_out": True, "checks": [{"said": "y"}]},
]
TASKS_DIFF = edit("evals/harness/tasks.json", '"said": "x"', '"said": "x|y"')


def tasks_after(**changes: dict) -> str:
    return json.dumps([{**task, **changes.get(task["id"], {})} for task in TASKS])


def check_tasks(after: str, diff: str = TASKS_DIFF) -> list[str]:
    return guard.check(diff, json.dumps(TASKS), after).violations


def test_a_task_validity_change_passes() -> None:
    assert check_tasks(tasks_after(find={"checks": [{"said": "x|y"}]})) == []


@pytest.mark.parametrize(
    "after",
    [
        tasks_after(buy={"stakes": None}),
        tasks_after(buy={"checks": []}),
        tasks_after(buy={"checks": [{"confirm": "buy"}]}),
        tasks_after(held={"held_out": False}),
        tasks_after(find={"held_out": True}),
        json.dumps([task for task in TASKS if task["id"] != "buy"]),
        json.dumps(TASKS + [{"id": "new", "group": "g", "held_out": True, "checks": []}]),
        "not json",
    ],
)
def test_dropping_a_confirm_check_or_a_mark_is_refused(after: str) -> None:
    assert check_tasks(after)


def test_product_and_grading_in_one_branch_are_refused() -> None:
    violations = check_tasks(tasks_after(), WEB_FIX + TASKS_DIFF)
    assert any("split it" in v for v in violations)


def test_gate_and_voice_changes_are_flagged_not_refused() -> None:
    for path in guard.FLAGGED_FILES:
        result = guard.check(edit(path, "x = 1", "x = 2"))
        assert result.violations == [] and result.flags == [
            f"{path}: changes the gate or the voice; read every line"
        ]


def test_a_guard_2_call_site_is_flagged() -> None:
    result = guard.check(
        edit("zoya/tools/browser.py", "click_checked(page, ref)", "click_checked(page, ref, 1)")
    )
    assert result.violations == [] and len(result.flags) == 2


def test_targets_must_be_declared_known_and_not_held_out() -> None:
    ids, held = {"a", "b", "h"}, {"h"}
    assert guard.check_targets(["a"], ids, held) == []
    assert guard.check_targets([], ids, held) == ["declares no Autotune-Targets trailer"]
    assert guard.check_targets(["a", "zz"], ids, held) == ["targets unknown tasks ['zz']"]
    assert guard.check_targets(["h"], ids, held) == ["targets held-out tasks ['h']"]


def test_the_day_program_names_every_guarded_path_and_the_trailer() -> None:
    day = (Path(guard.__file__).with_name("day.md")).read_text(encoding="utf-8")
    named = [*guard.REFUSED_FILES, *guard.REFUSED_PREFIXES, *guard.PROTECTED_CONSTANTS]
    assert [name for name in named if name not in day] == []
    assert "Autotune-Targets:" in day and "at most 3 outputs a day" in day
    assert not Path(guard.__file__).with_name("program.md").exists()
