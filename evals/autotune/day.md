# Autotune: the day program

You are a cloud session working on Zoya by day. The Mac measured every harness task on `main`
last night and published what failed. You turn failures into reviewed fixes. You never run the
eval and never touch `main`: you push draft branches, the coordinator pins them, and the next
night proves them or not.

## Rules

- Linux cannot import `zoya` (it needs macOS). Test with offline unit tests and fixtures only.
- Produce **at most 3 outputs a day**, one per failure cluster.
- **No site names.** Nothing under `zoya/` may name a website or reach into one site's markup.
  `tests/test_no_site_hardcoding.py` enforces the hostnames and selectors, and the guard refuses
  a branch that adds a task's site name (flipkart, ebay, imdb, ...) anywhere under `zoya/`.
- **Never touch guarded paths.** The guard (`evals/autotune/guard.py`) refuses a branch that:
  - touches `evals/harness/run.py`, `evals/harness/grade.py`, `evals/autotune/`,
    `scripts/autotune-*` or the `Makefile`;
  - changes, deletes or adds to any existing test file, or any `conftest.py`. Add new test files
    instead;
  - changes `JEV_STEP_CONFIDENCE`, `JEV_STEP_NOUL`, `PER_TASK_COST_CAP_USD` or
    `OPENAI_MONTHLY_BUDGET_USD`;
  - edits a line of `zoya/prompts.py` that holds a protected word (`surface.is_protected`);
  - drops a `confirm` check, or changes a `stakes` or `held_out` mark, in `tasks.json`;
  - changes `zoya/` and `evals/harness/tasks.json` in the same branch;
  - changes more than 400 lines outside `tests/fixtures/`.
- Changes to `zoya/safety.py`, `zoya/speech.py` and the Guard 2 call sites are allowed but
  **flagged**. The coordinator reads every flagged line first. Say in the brief why the gate
  change keeps every real risky action asking.
- Held-out tasks are only ever reported as pass or fail. Never target one.
- Conventional commits, one logical change each. Never commit secrets.

## 1. Read

Fetch the data-only branch and read the newest night:

```
git fetch origin autotune-data
git show origin/autotune-data:nights/<date>.md
git show origin/autotune-data:nights/<date>.json
```

The night lists, in this order:

1. regression alarms: tasks that were PASS until last night (NEW-FAIL);
2. candidates verified last night, with their verdicts and flags;
3. every task's class: PASS, FAIL, FLAKY or NEW;
4. held-out tasks, as pass or fail only;
5. a triage record for every NEW-FAIL, FAIL and FLAKY task.

Each triage record gives the task, its class and pass history (`P`/`F`, oldest first), its
cause, and the evidence from its run: `failed_checks`, the tail of what Zoya `said`, the
`confirmations` she asked, the last 5 tool names, the `url` without its query, and the `error`.

The causes are: `timeout`, `crash`, `false-ask` (asked on a task with no stakes),
`never-reached-gate` (a stakes task that never asked), `ask-wording` (asked, but not in words the
check accepts), `wall` (a sign-in page or captcha), `wrong-page` and `wrong-answer`.

A regression alarm comes first: find the commit on `main` that broke it.

## 2. Cluster

Group the failures by cause and mechanism, not by site. For example, flipkart-search and boat-buy
both failing on "search control not found" are one cluster, and one general fix should move both.
Read the code the evidence points at before you decide.

## 3. Produce one thing per cluster

**(a) A general engineering fix**, on `autotune/fix-<slug>`:

- a change in `zoya/` that would help any site with the same shape of page;
- new offline unit tests for it, in new test files. Recorded page fixtures under
  `tests/fixtures/` are allowed;
- `ruff check`, `black --check` and `isort --check` clean;
- a brief in the branch's first commit message: the cluster, the evidence, the mechanism of the
  fix, and why it is not site-specific.

**(b) A task-validity change**, on `autotune/task-<id>`, when the task and not the product is
wrong: a check that can never match a correct answer, or a task that needs something the
harness cannot give it. Change only `evals/harness/tasks.json`, and regrade the saved runs
offline to show the effect:

```
python evals/harness/grade.py <saved-run>.json --tasks evals/harness/tasks.json
```

A changed task starts a new history, so the night can at best call it consistent. The
coordinator decides from your brief.

A login wall is never a product special case. Either the owner signs in once
(`python -m zoya.main --login`), which you ask for in the park note, or the task is rewritten.

**(c) Park it**, with the reason, when it needs the owner, more evidence or a design decision.
Write the note in your session's report, not in a branch.

## 4. Declare targets

Every branch ends its commit messages with a trailer naming the task ids it should fix:

```
Autotune-Targets: flipkart-search, boat-buy
```

A branch with no targets, unknown ids or a held-out id is refused. Push the branch. The
coordinator reads it and pins it (`python -m evals.autotune queue <branch>`), and the next night
runs the targets 3 times against their own history.

## What proves a branch

- **Fixed:** a target that is FAIL on history passes at least 2 of 3.
- **Broken:** a sentinel that is PASS on history fails at least 2 of 3. One failure only
  triggers two reruns.
- **Proven:** at least one target fixed, no sentinel broken, no held-out task broken, and cents on
  the tasks that pass both ways within 1.15x.
- **Consistent:** every target passed every run but none can be proven (a FLAKY or NEW target).
- **Otherwise rejected.**

Only the coordinator merges, after the night proves a branch. Never push to `main`.
