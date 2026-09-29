"""The v2 fence: which candidate diffs the night may run unattended. Nothing here imports zoya."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from evals.autotune import fence

ROOT = Path(__file__).resolve().parents[2]


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


def new_file(path: str, body: str = "x = 1", mode: str = "100644") -> str:
    return (
        f"diff --git a/{path} b/{path}\n"
        f"new file mode {mode}\n"
        "index 0000000..3333333\n"
        "--- /dev/null\n"
        f"+++ b/{path}\n"
        "@@ -0,0 +1 @@\n"
        f"+{body}\n"
    )


WEB_FIX = edit("zoya/tools/browser.py", "x = find_field(page)", "x = find_field(page, role=True)")


def test_a_plain_zoya_fix_with_a_new_test_may_run() -> None:
    diff = WEB_FIX + new_file("tests/test_find_field.py", "def test_x(): pass")
    assert fence.check(diff) == []


def test_new_fixture_files_may_run() -> None:
    assert fence.check(new_file("tests/fixtures/web/site.json", "{}")) == []


@pytest.mark.parametrize(
    "path",
    [
        "zoya/safety.py",
        "evals/harness/run.py",
        "evals/harness/tasks.json",
        "evals/autotune/fence.py",
        "scripts/autotune-night.sh",
        "tests/autotune/test_fence.py",
        "tests/evals/safety_replay.py",
        "pyproject.toml",
        "Makefile",
    ],
)
def test_only_zoya_and_new_tests_may_change(path: str) -> None:
    violations = fence.check(edit(path, "a = 1", "a = 2"))
    assert violations and path in violations[0]


@pytest.mark.parametrize("path", ["tests/conftest.py", "tests/fixtures/web/conftest.py"])
def test_a_conftest_never_runs_unattended(path: str) -> None:
    assert fence.check(new_file(path))


def test_an_existing_test_is_read_only() -> None:
    violations = fence.check(edit("tests/test_step_loop.py", "assert a", "assert a or True"))
    assert violations == ["tests/test_step_loop.py: an existing test file changes"]


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ("JEV_STEP_CONFIDENCE = 0.70", "JEV_STEP_CONFIDENCE = 0.50"),
        ("PER_TASK_COST_CAP_USD = 0.50", "PER_TASK_COST_CAP_USD = 5.0"),
        ("OPENAI_MONTHLY_BUDGET_USD = 15.0", "OPENAI_MONTHLY_BUDGET_USD = 150.0"),
        ("gated = needs_confirmation(label)", "gated = False"),
        ("# Guard 2 runs first", "# runs first"),
        ("x = 1", "require_confirmation = lambda *a: None"),
        ("x = 1", "safety.stop = None"),
        ("x = 1", "click('Place ORDER')"),
        ("x = 1", "con​firmed = True"),  # an invisible character does not hide the word
    ],
)
def test_a_line_touching_the_gate_or_a_cap_is_fenced(old: str, new: str) -> None:
    assert fence.check(edit("zoya/config.py", old, new))


@pytest.mark.parametrize(
    ("header", "reason"),
    [
        ("deleted file mode 100644", "deletes a file"),
        ("old mode 100644", "changes a file mode"),
        ("similarity index 90%", "renames or copies a file"),
        ("rename from zoya/a.py", "renames a file"),
        ("Binary files a/zoya/x.png and b/zoya/x.png differ", "is a binary patch"),
    ],
)
def test_deletes_renames_modes_and_binaries_are_refused(header: str, reason: str) -> None:
    diff = f"diff --git a/zoya/x.py b/zoya/x.py\n{header}\n"
    assert fence.check(diff) == [f"zoya/x.py: the diff {reason}"]


def test_an_executable_new_file_is_refused() -> None:
    assert fence.check(new_file("zoya/run_me.py", mode="100755"))


@pytest.mark.parametrize(
    "header",
    [
        "diff --git a/zoya/a.py b/zoya/b.py",
        'diff --git "a/zoya/x y.py" "b/zoya/x y.py"',
        "diff --git a/zoya/../evals/x.py b/zoya/../evals/x.py",
        "diff --git zoya/a.py zoya/a.py",
    ],
)
def test_unreadable_or_escaping_paths_fail_closed(header: str) -> None:
    assert fence.check(header + "\n")


@pytest.mark.parametrize("diff", ["", "hello\n", "diff --git a/zoya/x.py b/zoya/x.py\r\n"])
def test_empty_or_foreign_input_fails_closed(diff: str) -> None:
    assert fence.check(diff)


def test_a_stray_line_inside_a_hunk_fails_closed() -> None:
    assert fence.check(WEB_FIX + "index 1234567..89abcde\n")


def test_a_large_diff_needs_the_owner() -> None:
    body = "".join(f"+x{i} = {i}\n" for i in range(fence.MAX_CHANGED_LINES + 1))
    diff = (
        "diff --git a/zoya/big.py b/zoya/big.py\nnew file mode 100644\n--- /dev/null\n"
        f"+++ b/zoya/big.py\n@@ -0,0 +1,{fence.MAX_CHANGED_LINES + 1} @@\n{body}"
    )
    assert fence.check(diff) == [
        f"{fence.MAX_CHANGED_LINES + 1} changed lines; at most {fence.MAX_CHANGED_LINES} run "
        "unattended"
    ]


def test_the_cli_exits_non_zero_on_a_violation() -> None:
    def run(diff: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "evals.autotune.fence"],
            input=diff,
            capture_output=True,
            text=True,
            cwd=ROOT,
        )

    assert run(WEB_FIX).returncode == 0
    refused = run(edit("zoya/safety.py", "a = 1", "a = 2"))
    assert refused.returncode == 1 and "zoya/safety.py" in refused.stderr
