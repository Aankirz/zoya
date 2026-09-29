# Autotune v2: triage at night, engineering by day, per-task verdicts

Status: proposal. Prototype of the riskiest piece (keep rule + branch guard):
`evals/autotune/pertask.py`, tested in `tests/autotune/test_pertask.py` (stdlib, never imports zoya).

## 1. Diagnosis: why v1 kept nothing

1. **The failures sit outside the surface.** v1 may edit only `zoya/config.py` constants and
   unprotected lines of `zoya/prompts.py` (`surface.py:18-31`). Night 1's misses are search
   controls not found (flipkart-search, boat-buy), a login wall (goodreads-search), a gate false
   positive (imdb-search) and a host-only open (wikipedia-open). Those live in the browser tools,
   the web loop, `safety.py` and `tasks.json`. Even `open_url`'s docstring, which nudges bare
   hosts (`e.g. "youtube.com"`, `zoya/tools/fast.py:103`), is out of reach.
2. **The bar can't be reached from the knobs.** `score.decide` needs +1 mean success over the
   whole group (`score.py:43`, `:56`). The imperfect passers offer at most 0.5 of it
   (wikipedia-open lost 5 of 18, imdb-open 2, ebay-search 2: 9/18). The rest must come from
   tasks that passed at most 3 of 18 under every setting tried, and that takes code or a task
   change.
3. **Aggregation throws away the signal.** `score.summarize` collapses runs to per-group counts
   (`score.py:27-39`). So the verdict can't see that 9 of 10 tasks are deterministic. Baseline
   noise [4, 6, 5] comes from two or three tasks, yet 162 of the 180 task-runs (90%) had an
   outcome that was already known.
4. **It measures a stale product.** `init` branches `autotune` from main once
   (`loop.py:94`). An existing worktree is only checked, never updated (`loop.py:83-86`). So
   b7e2e08's imdb-search fix never reaches the eval.
5. **No path to main.** Kept patches land on `autotune`, "not on `main`" (`program.md:11`).
6. **Invalid tasks count as failures.** goodreads-search hits a sign-in wall.
   boat-newsletter *can* pass as written. Its only check is `confirm`, matched against the
   question asked (`run.py:223-224`), and "Cancelled" is just the harness's D96 cancel
   (`run.py:154-159`, `safety.py:1168`). 3/18 did pass. The other 15 need their `confirmations`
   field read: either nothing was asked or the wrong control was asked about. That is triage,
   not tuning.

## 2. The v2 loop

The unit is a task's outcome over time, not a group mean. The night is plain Python with no
proposing agent. Everything creative happens in cloud sessions by day. Nothing reaches main
without the owner.

**Night (Mac, 00:00-07:00, `scripts/autotune-night.sh`)**

1. **Sync.** Reset the `autotune` worktree to `origin/main` and run `pytest -q` there.
2. **Census.** Run each task once (`run.py LABEL --group G`) and append one row per task to the
   history ledger. `pertask.classify` labels each task PASS, FAIL or FLAKY (at most one run
   in six the other way, over its last 6 census runs, so a merged fix reclassifies within days;
   night 1's 18 runs give 4 PASS, 5 FAIL, 1 FLAKY: wikipedia-open). FLAKY tasks get 2 extra runs (`--only`, `run.py:348`).
3. **Verify queued candidates** (up to 3, see §4). Each candidate commit gets its own checkout
   of the worktree and must pass `pytest -q`. Then the tasks it targets run 3 times and every
   other task runs once as a sentinel. `pertask.reruns` asks for 2 more runs of any sentinel
   that broke; `pertask.verdict` decides (§3).
4. **Triage.** For every FAIL/FLAKY task, write `triage-DATE.md` with class, pass history, and
   a signature (first failed check + error + last tool). It also carries the evidence already in
   the Run JSON (`run.py:56-76`): `failed_checks`, `said`, `confirmations`, the last 5 `tools`,
   `url` and `error`. Emails other than `harness@example.com` and runs of 10 or
   more digits are redacted, because the evals run in the owner's signed-in Chrome.
5. **Publish.** Push the triage and verdicts to the data-only branch `autotune/data`. That is
   the only push the night makes.

**Day (cloud sessions, spare credit, Linux)**

A session reads the latest `autotune/data`, clusters failures by cause (flipkart-search and
boat-buy look like one "search control" cluster), and turns each cluster into exactly one of:

- **Task fix** on `autotune/task-<id>`: retire or rewrite an invalid task (goodreads-search),
  re-graded offline against saved runs with `evals/harness/grade.py` (new, see §6).
- **Engineering brief + draft patch** on `autotune/fix-<slug>`: a generic fix in `zoya/` with
  unit tests (it may also add a `tests/fixtures/web` page, as `record_web.py` does). It must
  pass `ruff`, and `tests/test_no_site_hardcoding.py` forbids per-site code. The brief names
  its target tasks. Cloud can't import zoya, so the Mac's night run is its test run.
- **Knob patch**, still vetted by `surface.check_patch` (`surface.py:85`), when the evidence
  points at a constant.
- **Park it**, with the reason recorded.

The session opens a draft PR, and the next night's verdict goes into its description.
Improvements reach main only when the owner merges.

## 3. Keep rule and noise

Near-deterministic tasks make per-task history the noise model (`pertask.verdict`):

- **Fixed:** a FAIL task passes ≥ 2 of its 3 runs. If its history rate is ≤ 1/18, 2-of-3 by
  chance has p ≈ 3·(1/18)² ≈ 0.009.
- **Broken:** a PASS task fails ≥ 2 of 3 runs. One sentinel failure is only a reason to rerun:
  at 16/18, two misses in three has p ≈ 0.03.
- **Recommend** when at least one task is fixed and none broken, and cents on the tasks that
  pass both ways rise ≤ 15% (v1's ratio, `score.py:14`).
- **FLAKY tasks are reported, not judged.** Making one stable is itself a fix target.
- History resets per task when its `tasks.json` entry changes.

"Recommend" means "ready for the owner", not "kept". Night 1's best experiment, open_url with
the full URL (5.33, cheaper), was discarded with no record of which tasks moved. v2 records that
per task, and a wikipedia-open gain would point a brief at `fast.py:103-107`.

## 4. Safety

- **The eval can't act.** Every confirmation is answered "cancel" by `install_voice`
  (`run.py:162-175`), and no candidate may touch `run.py`, `evals/autotune/` or the night
  script (`pertask.FORBIDDEN`).
- **The gate can't be weakened quietly.** `pertask.guard_branch` refuses any branch that does
  any of these:
  - removes or changes a line in the gate tests (`test_safety`, `test_gate_review`,
    `test_computer_safety`, `test_unconfirmed_order`, `test_no_site_hardcoding`);
  - touches `JEV_STEP_CONFIDENCE`, `JEV_STEP_NOUL`, `PER_TASK_COST_CAP_USD` or
    `OPENAI_MONTHLY_BUDGET_USD` (`config.py:20-21, 355-356`);
  - edits a protected prompt line (`surface.is_protected`, `surface.py:125`);
  - drops a `confirm` check or `stakes` mark from `tasks.json`;
  - changes product and grading in the same branch.

  A `zoya/safety.py` change can be legitimate (b7e2e08 narrowed a false ask), so it is
  *flagged* and goes first in the report for a line-by-line read.
- **Human review happens twice.** (1) *Before a candidate runs on the Mac*, the owner runs
  `python -m evals.autotune queue BRANCH`. That prints the guard result and diffstat and pins
  the branch's current SHA in the gitignored `logs/autotune/queue.tsv`. Cloud sessions can't
  reach it, and a branch that moves after queueing is skipped. Knob-only diffs that pass
  `surface.check_patch` may be auto-queued, as v1 already ran them unattended. (2) *Merge:*
  only the owner merges PRs. No process merges or pushes to main.

## 5. Cost

Night 1 cost 191¢ for 180 task-runs, about 1.06¢ each (eval metering only; the proposing
agent's own spend was extra). For the no-code group:

| step | task-runs | ≈ cents |
| --- | --- | --- |
| census | 10 | 11 |
| flaky reruns | ~2 | 2 |
| per candidate: 2 targets × 3 + 8 × 1 + ~2 reruns | ~16 | 17 |
| 3 candidates | ~48 | 51 |
| **night** | **~60** | **≈ 64** |

That is about a third of night 1's eval spend, with **no nightly Claude agent**. Triage and
patching move to cloud credit. The rest of the $10 buys a census of all 30 tasks. Other
groups' per-run cost is unmeasured and gets read from the ledger after the first census.
`AUTOTUNE_BUDGET_CENTS` still caps everything (`loop.py:34-35`).

## 6. File-by-file plan

| file | change |
| --- | --- |
| `evals/autotune/pertask.py` | **add** (prototype here): `classify`, `reruns`, `verdict`, `guard_branch` |
| `evals/autotune/score.py` | **delete** `decide`, `_shape`, `_cents_per_success` (`:43-90`); keep `load`, `summarize` |
| `evals/autotune/ledger.py` | `COLUMNS` → `utc, night, ref, commit, task_id, success, cents, seconds, signature`; `spent_cents` unchanged |
| `evals/autotune/loop.py` | `init` → `sync` (fetch, `checkout -B autotune origin/main`); **add** `census`, `queue`, `verify`, `triage`; **delete** `try_patch` and baseline.json (`:200-217`, `:283-324`); `report` reads history + verdicts |
| `evals/autotune/surface.py` | unchanged; now vets knob-only candidates |
| `evals/autotune/program.md` | rewrite as the **day** program for cloud sessions: read triage, one cluster → one branch, generic fixes only, never edit the judge, draft PR |
| `scripts/autotune-night.sh` | **delete** the agent block (`:106-141`); run sync → pytest → census → verify → triage → report → push `autotune/data`; keep caffeinate, hour check, log rotation |
| `evals/harness/grade.py` | **add**: move `failed_checks`' pure part (`run.py:213-231`, shell runner injected) so Linux can regrade |
| `evals/harness/run.py` | import `grade`; record `url` for every web task, not only those with a url check (`run.py:276`) |
| `evals/harness/tasks.json` | no change here; goodreads-search's fate is the owner's first triage decision |
| `tests/autotune/` | `test_pertask.py` added; update `test_score.py`, `test_ledger.py`, `test_loop.py` |

**Done when**

1. `pytest tests/autotune` passes on Linux, and nothing under `evals/autotune` imports zoya.
2. `sync` makes the worktree HEAD equal to `origin/main` every night.
3. One census night produces a per-task history and a redacted `triage-DATE.md` on
   `autotune/data`.
4. `guard_branch` refuses each case in `test_pertask.py`, and the night never runs an unqueued
   or moved branch.
5. A cloud session turns that triage into at least one draft PR. The next night gives it a
   `verdict` line in the report.
6. imdb-search leaves FAIL within a few nights of `sync` measuring main with b7e2e08.
7. The night's eval spend stays ≤ $1 for the no-code group, with no `claude -p` in the night script.
8. One engineering fix that went through this loop is merged and flips a FAIL task to PASS in
   the census.

## 7. Alternatives rejected

- **Widen v1's surface** (more constants, tool docstrings): search-control discovery and login
  walls are still out of reach, and the +1-mean bar stays unreachable (§1.2).
- **More repeats or a significance test on the group mean:** triples the spend to re-measure
  tasks whose outcome is already known. Per-task history is the cheaper noise model.
- **A night agent that writes `zoya/` code and auto-keeps it:** runs unreviewed code in the
  owner's signed-in Chrome under a clock, and the gate is the only thing between a bug and a
  real send. Code comes from reviewed-by-day branches instead.
- **Evals in the cloud, or offline replays** (`record_web.py`): zoya needs macOS and live
  sites drift. Replays stay as unit-test fixtures.
- **An LLM judge for grading:** adds cost and noise. Task validity, not regex grading, is the
  problem.
- **Per-site fixes or skills** for flipkart and boAt: forbidden (`test_no_site_hardcoding.py`),
  and skills are being retired.
- **Auto-merging "recommended" branches:** saves one click but removes the only human check on
  gate changes.
