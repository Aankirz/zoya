# Autotune v2: find, fix by day, prove at night

Status: proposal. Prototype of the riskiest piece: `evals/autotune/fence.py`, `tests/autotune/test_fence.py`.

## 1. Diagnosis: why v1 kept nothing

1. **The surface can't reach the failures.** v1 may change six constants and non-protected prompt lines (`evals/autotune/surface.py:20-31`). Night 1's misses are all capability or validity problems: a search control it can't find (flipkart, boat-buy), a login wall (goodreads), navigation that stops one page short (wikipedia), a false ask (imdb, fixed in `b7e2e08`, which edited `zoya/safety.py`). No knob reaches these.
2. **Pooled means blur per-task outcomes.** `score.summarize` keeps only group counts (`score.py:27-40`), and `decide` asks for +1 mean task with no group drop (`score.py:43-78`). Outcomes are nearly fixed per task, so the baseline spread [4,6,5] comes from two flaky tasks (wikipedia 13/18, newsletter 3/18). A fix that flips one dead task clears +1.0 only if those two don't wobble down: a coin flip.
3. **The agent read the wrong field.** `program.md:18` points it at `error`, but `run.py` sets `error` only for an exception or the 300 s limit (`run.py:251,256`). The reason a task failed is in `said` and `failed_checks`.
4. **A win never reaches the product.** Kept patches are committed on the `autotune` branch in `../zoya-autotune` (`loop.py:30,316`). That branch was cut from `main` once (`loop.py:94`), so it falls further behind `main` every night.
5. **The budget is lifetime, not nightly.** `check_budget` sums every ledger row ever (`ledger.py:62-64`, `loop.py:173-181`); five nights like night 1 exhaust the 1000¢ default (`loop.py:35`).
6. **Some tasks are invalid as graded.** goodreads hits a sign-in page. boat-newsletter *can* pass under D96: its check is `confirm` (`tasks.json:104-110`), and the harness records the gate's question before answering cancel (`run.py:167-171`, `safety.py:1262,1292`). It passed 3 of 18; the other 15 "Cancelled" runs asked something, so the question's wording missed the regex or it asked at the wrong step. That needs triage, not tuning.

## 2. The v2 loop

**Measure per task.** No agent runs at night: the night only measures; the thinking happens by day in cloud sessions.

**Night (owner's Mac, 00:00–07:00, `scripts/autotune-night.sh`):**
1. `probe`: run every task in `tasks.json` once on the current `origin/main` and append one row per task to `logs/autotune/history.tsv`.
2. `verify` each candidate commit the owner has pinned (see §4):
   - run `fence.check` on `git diff origin/main...SHA`;
   - check out SHA detached in `../zoya-autotune` and run `make check` (`Makefile:10`, macOS-only tests included);
   - run the commit's target tasks and its sentinels with `run.py --only` (`run.py:348-361`);
   - score with §3.
3. `digest`: push `nights/<date>.json` to an orphan branch `autotune-data`: per run the id, success, failed_checks, error, route, query-less url, first 300 chars of `said` and `confirmations`, tool **names** (never inputs), and the verdicts.

**Day (cloud session, Linux, stdlib):**
1. `python -m evals.autotune triage` reads the digests and gives each task a state:
   - **stable-pass**: its last 5 main runs all passed;
   - **stable-fail**: none of them passed;
   - **flaky**: anything in between;
   - **new-fail**: it was stable-pass until last night. This is the regression alarm.

   Each failure gets a class by explicit rules:
   - **login-wall**: `said` mentions a sign-in page;
   - **grader**: a `confirm` or `url` check failed although the task looks done;
   - **false-ask**: `confirmations` is non-empty on a task with no `stakes`;
   - **timeout**;
   - **capability**: anything else, grouped by the first sentence Zoya said.
2. Claude, following `evals/autotune/day.md`, turns the top items into outputs:
   - **Engineering brief**: evidence, root-cause hypothesis with file:line, a *generic* fix (`tests/test_no_site_hardcoding.py` forbids site code).
   - **Draft PR** on `autotune/fix-<slug>` with a trailer `Autotune-Targets: flipkart-search,boat-buy`, after ruff/black/isort and the fence pass locally (zoya's tests run at night, on macOS).
   - **Task-validity PR** for tasks.json, or an owner action. For goodreads that means signing in once with `python -m zoya.main --login` (`zoya/main.py:10`) or rewriting the task.
3. The next day's session posts the night's verdict on the PR and marks a *proven* one ready for review.

**Reaching main:** only by the owner merging a PR; nothing auto-merges. A constant change (e.g. `WEB_RENDER_WAIT_S`) is just another candidate PR.

## 3. Keep rule and noise

A candidate names its targets. The night runs each target 3 times, or 5 if main passed it at least once.

It compares them with a one-sided Fisher exact test against main's last 5 runs of that task (probe history, tonight included): exact for small pass/fail samples, ~15 lines of `math.comb`.

| main | candidate | p | verdict |
| --- | --- | --- | --- |
| 0/5 | 3/3 | 0.018 | proven |
| 0/5 | 2/3 | 0.107 | not proven |
| 1/5 (newsletter-like) | 5/5 | 0.024 | proven |
| 4/5 (wikipedia-like) | 3/3 | 0.625 | consistent only |

- **proven**: p ≤ 0.05 for at least one target.
- **consistent**: all target runs passed but p > 0.05. A near-passing task can't be proven cheaply; the owner decides from the brief's mechanism and later probes confirm.
- **Regression**: every stable-pass task in the targets' groups runs once. If one fails, it gets 2 more runs, and 2 failures out of 3 is a regression, which rejects the candidate. By chance that happens about 0.5% of the time for a task that fails 1 run in 20.
- **Cost**: the sentinels' mean cents may be at most 1.15× main's on the same night (reusing `MAX_CENTS_PER_SUCCESS_RATIO`, `score.py:14`).

Near-determinism makes this cheap: 3 runs prove a dead task came alive.

## 4. Safety

- **Nothing that drives Chrome is changed.** `run.py`, its `answer_cancel` (`run.py:154-159`), D96, Guard 2, `JEV_STEP_CONFIDENCE` (`config.py:355`) and the caps (`config.py:20-21`) all stay as they are.
- **The fence** (`fence.py`, prototyped here) decides what may run unattended, and it fails closed:
  - only `zoya/` may change, never `zoya/safety.py`, and nothing there is deleted, renamed, re-moded or binary;
  - `tests/` may only gain new `test_*.py` files or fixtures; existing tests and any `conftest.py` are read-only, so a candidate can't weaken the suite that judges it;
  - no added or removed `zoya/` line may contain a protected word (surface's list plus guard, budget, cost_cap, confidence);
  - at most 400 changed lines.

  It refuses `b7e2e08` (the IMDb false ask: it edits `safety.py`); such fixes go to an owner slot by design.
- **The fence is a tripwire, not a sandbox**: code can reach the gate indirectly. So the owner reads the diff and pins it, `scripts/autotune-queue.sh SHA` (appends to `logs/autotune/queue.txt`); the night runs exactly that SHA or nothing.
- **Two human reviews:** pin before the night runs it, merge after it's proven. Task edits (`evals/`) are fenced, so they are always human-merged, and the next probe grades with them.

## 5. Cost

Night 1 cost 10.6¢ per 10-task run ($1.91 / 18).

- **Probe**: 30 tasks once, about 32¢, assuming the other groups cost the same. `estimate_per_run` (`loop.py:165-170`) will read the real figure.
- **Verify**: about 10–12 task runs per candidate, roughly 12¢. Five candidates come to about 60¢.
- **Total**: about $1 a night against the $10 cap, with the cap made nightly (§6).

Cheaper: no night agent, no 3× full-group repeats per idea, stable-pass tasks run once, and triage, briefs and patches use cloud credit.

## 6. File-by-file plan

| file | change |
| --- | --- |
| `evals/autotune/fence.py` | **add** (prototype in this branch) |
| `evals/autotune/score.py` | add `by_task`, `fisher_one_sided`, `verdict` (§3); delete `decide`, `_shape`, `_cents_per_success` |
| `evals/autotune/triage.py` | **add**, about 120 lines: states and failure classes from digests |
| `evals/autotune/loop.py` | replace `baseline` and `try` with `probe`, `verify SHA`, `digest`; worktree detached at SHA (`check_worktree`'s branch check, `:112-114`, becomes a SHA check); budget counts tonight's rows only; `report` lists per-task states and verdicts |
| `evals/autotune/ledger.py` | `Ledger(path, columns)`; reuse it for `history.tsv` (utc, label, sha, task, group, success, cents) |
| `evals/autotune/surface.py` | keep `PROTECTED_WORDS` and `is_protected` (the fence uses them); delete `check_patch` and its parser |
| `evals/autotune/program.md` | **delete** (no night agent) |
| `evals/autotune/day.md` | **add**: the cloud program (triage, then at most 3 briefs, then fenced draft PRs with the trailer; no site code; never touch §4 items) |
| `scripts/autotune-night.sh` | drop `claude -p`/`allowed` (`:106-128`); run probe, verify the queued SHAs, digest, push `autotune-data`; keep caffeinate, `STOP_HOUR` and log rotation |
| `scripts/autotune-queue.sh` | **add**, about 10 lines |
| `tests/autotune/` | `test_fence.py` (added); new tests for triage and `fisher_one_sided`; trim the `test_surface.py` and `test_loop.py` parts that cover removed code |

**Done when:**
1. `pytest tests/autotune` passes on Linux without zoya installed.
2. The fence refuses every case in `test_fence.py` and `git diff b7e2e08~1 b7e2e08`.
3. One night's probe writes 30 history rows and a digest on `autotune-data` with no tool inputs.
4. On night 1's data, triage marks flipkart, goodreads and boat-buy stable-fail, puts goodreads in login-wall, and shows boat-newsletter's question text.
5. `verify` refuses an unpinned or moved SHA and any commit the fence rejects.
6. A candidate that makes a fake stable-fail task pass 3/3 comes out *proven*; a sentinel failing 2/3 comes out *regression*. Both are tested with a fake eval, as `test_loop.py` does now.
7. The budget refuses a run past the nightly cap, not a lifetime one.
8. The first cloud day produces at least one brief and one fenced draft PR from real night data.

## 7. Alternatives rejected

- **Widen v1's surface.** The failures aren't in knobs, and each knob adds chances to keep luck.
- **More repeats or a lower `min_gain`.** Noise isn't the blocker; the pooled mean and the surface are.
- **A night agent writing and auto-keeping zoya/ patches.** Unreviewed code in a logged-in Chrome, and it still needs a merge.
- **An LLM judge.** Cost and noise; regex checks are deterministic and regradable (`run.py:326-345`).
- **Cloud evals on recorded pages** (`record_web.py`). zoya needs macOS; recordings drift from live sites.
- **Per-site skills or selectors.** They are being retired and `tests/test_no_site_hardcoding.py` forbids them.
- **The fence alone gating night runs.** A diff check can't prove the gate intact; a pin costs one command.
