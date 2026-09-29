# Autotune v2: measure per task, triage failures, fix by review

Status: proposal. Prototype of the riskiest piece (per-task history, failure causes, keep rule):
`evals/autotune/triage.py`, tested in `tests/autotune/test_triage.py`.

## 1. Diagnosis: why v1 kept nothing

1. **The surface can't reach the failures.** v1 may move six constants (`surface.py:24-31`) or
   edit prompt lines with no protected word in them (`surface.py:34-51`). Night 1's misses are a
   search box nobody found (flipkart, boat-buy), a login wall (goodreads), a false ask (imdb-search,
   fixed in `zoya/safety.py` by b7e2e08) and a wrong URL (wikipedia). None of these is a timeout
   or a step budget, and the fixes belong in `zoya/` code or `tasks.json`.
2. **The bar is higher than the surface can reach.** `score.decide` wants +1 mean task
   (`score.py:515`). On night 1's per-task rates, a knob that made every flaky task always pass
   would add wikipedia 5/18 + imdb-open 2/18 + ebay 2/18 ≈ +0.5. The other ~4.5 missing tasks
   are 0/18 or 1/18, and no constant flips them. So +1 was out of reach from the start.
3. **Totals hide the signal.** Summing 10 tasks turns five near-deterministic tasks and four
   flaky ones into one noisy number. The binomial SD of a run is ≈0.77 tasks, and a mean of 3
   minus a mean of 3 has SD ≈0.63. A real +0.3 gain can't show through that, and a big fix to one
   task is diluted by the other nine.
4. **Nothing reaches main.** A kept patch is committed on branch `autotune` (`loop.py:30-31`,
   `loop.py:315-318`). There's no review step and no PR.
5. **The budget runs for the life of the ledger, not per night.** `Ledger.spent_cents` sums
   every row ever written (`ledger.py:611-613`). `check_budget` compares that sum with the
   1000¢ default (`loop.py:35`, `loop.py:173-180`), so after about five nights like night 1 the
   runner refuses to run at all.
6. **Some tasks may be invalid, and nothing flags them.** boat-newsletter *can* pass as written.
   Its only check is a `confirm` regex over Zoya's question (`tasks.json:103-113`,
   `run.py:223-224`). The "Cancelled" she says afterwards is expected after the harness answers
   cancel (`run.py:154-159`), and success means only no failed check and no error
   (`run.py:283`). It passed 3/18, so the 15 misses are either no ask or an ask the regex didn't
   match. v1 records `confirmations` (`run.py:68`) but never reads it. goodreads may need a
   signed-in eval profile.

## 2. The v2 loop

v2 drops the overnight proposing agent. Nights **measure**, cloud sessions **diagnose and
draft**, and the owner **merges**.

**Night, on the Mac (`scripts/autotune-night.sh`, 00:00-07:00, caffeinated as today):**

1. Run the harness on `main` twice over all 30 tasks in the worktree. Append each task's run to
   the per-task history (`triage.history`, newest `WINDOW = 6` runs, `triage.py:13,26`). Each
   task is then `solid`, `broken`, `flaky` or `new` (`triage.state`, `triage.py:39`).
2. For each branch the owner queued (`logs/autotune/queue.txt`, one `branch sha` per line,
   pinned sha):
   - Run the protected-path guard (§4).
   - Run `pytest tests/test_safety.py tests/test_gate_review.py
     tests/test_no_site_hardcoding.py` plus the branch's own new tests. These need macOS, so
     they run here and not in the cloud.
   - Run the branch's target tasks 3 times and the rest of their group once.
   - Apply `triage.decide` (§3). A `rerun` verdict buys 2 more runs of the flagged tasks.
3. Write `logs/autotune/night-<date>.md`: per-task state, pass counts, cents, and each failing
   run's `cause` (`triage.py:51`: timeout, crash, false-ask, never-reached-gate, ask-wording,
   wall, wrong-page, wrong-answer), plus each queued branch's verdict. For failing runs it also
   includes `error`, `failed_checks`, `url`, `confirmations` and ≤160 chars of the last `said`.
   It never includes tool inputs (typed text) or `leftover` shell output. If
   `AUTOTUNE_PUSH_REPORT=1`, the report is committed alone to branch `autotune-reports` and
   pushed.

**Day, in a cloud session (Linux, the owner's spare credit):** the session reads the latest
report and `zoya/` source. Each day it takes the one or two broken tasks with the most runs of
the same cause and produces exactly one of:

- **Task-validity PR**, editing only `evals/harness/tasks.json`. For example, flag goodreads as
  `wall`, or replace a task whose check can't be met. The owner decides, and v2 never drops a
  task on its own.
- **Engineering brief + draft PR** on `claude/fix-<task>`: cause, evidence, cited code, a general
  patch (never site names, which `tests/test_no_site_hardcoding.py` enforces) and offline tests.
  The PR body lists its target task ids.
- **Autotune code** (stdlib-only `evals/autotune/`), fully tested in the cloud.

`program.md` becomes this day brief.

**Reaching main:** the owner reads the draft PR and adds its `branch sha` to the queue. That
night returns a verdict, which the next day session posts on the PR. The owner merges. Nothing
merges itself.

## 3. Keep rule and noise

The rule is `triage.decide` (`triage.py:77`), which judges each task against its own main
history:

- **Keep** needs all three:
  - some *broken* target (history pass rate ≤ 1/3) passes at least 2 of 3;
  - no *solid* task (≥ 5/6) fails twice;
  - solid tasks cost ≤ 15% more cents per run (v1's cost bar, measured per run so that a
    tolerated failure isn't counted twice).
- **Rerun** when a solid task failed once in fewer than 3 runs.
- **Discard** otherwise.

Flaky and new tasks can neither prove a fix nor veto one. They are reported, not scored.

Why this handles the noise:

- **False keep:** a task that is 0/18 has essentially no chance of passing 2 of 3 by luck. At
  1/6 the chance is 7.4%, and the owner's review stands behind it.
- **False discard:** a solid 5/6 task fails 2 of 3 by chance 7.4% of the time. A 6/6 task
  essentially never does.
- **Site drift:** main runs every night and feeds the history. If a site changes and a solid
  task starts failing on main too, it drifts to flaky or broken and stops vetoing branches.
- **Merged fixes:** history is per task and rolls, so a fix merged to main shows up within
  three nights.

## 4. Safety

- **The runner refuses any branch whose diff touches** `zoya/safety.py`, `zoya/speech.py`
  (whose `narrate`/`say_and_wait` the harness stubs, `run.py:167-175`), `evals/harness/`,
  `evals/autotune/` or `scripts/autotune-*`. It also refuses a changed `zoya/config.py` line
  naming `JEV_STEP_CONFIDENCE` or `*_CAP_*` (`config.py:355`, `config.py:21`), and changed
  `zoya/prompts.py` lines that fail `surface.is_protected` (`surface.py:125`). The guard fails
  closed.
- **D96 holds:** the harness is main's own `run.py`, which always answers "cancel"
  (`run.py:154-175`). A branch can't change it, because the paths above are refused.
- **Gate tests must pass first:** the gate's own tests pass on the branch before any real site
  is opened.
- **Cloud sessions never touch the Mac or Chrome.** They write PRs.
- **Human review, twice:**
  - The owner reads a branch before queueing it, because it will run on their Mac.
  - The owner merges the PR.
- **Task edits are owner-merged PRs:** `stakes` tasks keep their `confirm` checks.

## 5. Cost

Night 1 spent $1.91 on 180 task-runs, about 1.06¢ each (model + Jev as metered by `run.py:92-129`;
recheck on night 1 of v2, since other groups may cost more).

v2 night:

| Item | Task-runs | Cost |
| --- | --- | --- |
| Main, 30 tasks × 2 | 60 | ≈ $0.65 |
| Up to 4 queued branches (2 targets × 3 + ~9 canary + reruns ≈ 18 each) | ≈ 72 | ≈ $0.80 |
| **Total** | ≈ 132 | **≈ $1.50** |

That is well under the $10 cap, which becomes **per night** (§6).

What gets cheaper:

- There is no overnight Claude agent (v1's was capped only if `AUTOTUNE_AGENT_MAX_USD` was set,
  `autotune-night.sh:611-612`).
- There is no knob search (v1 spent 15 of its 18 runs on it).
- Solid tasks run once per branch instead of three times.
- The baseline is shared across nights instead of being rebuilt.
- Diagnosis runs on cloud credit.

## 6. File-by-file plan

- **Add** `evals/autotune/triage.py` (prototype here) and its test. Later add `report(history,
  tasks)`, which renders the night report.
- **Change** `evals/autotune/loop.py`:
  - Replace `baseline`/`try` (`loop.py:260-324`) with `night-main` (append main runs to history)
    and `eval-branch BRANCH SHA --targets IDS` (guard, checkout of the pinned sha in the
    worktree, the gate tests, runs, `triage.decide`).
  - Make `check_budget` count only tonight's rows.
  - Keep `init`, `check_worktree`, `run_eval` and `report`.
- **Change** `evals/autotune/ledger.py`: `spent_cents(since=None)` filters on `utc`. Add columns
  `branch` and `targets`.
- **Change** `evals/autotune/surface.py`: add `PROTECTED_PATHS` and
  `check_branch(diff) -> list[str]`, reusing `_parse`/`is_protected`. Delete
  `ALLOWED_CONSTANTS` and the config-line checks (`surface.py:24-31`, `278-321`, `387-417`) once
  `check_branch` covers `config.py`.
- **Delete** `score.decide` and `_shape` (`score.py:502-542`) and their tests, which v2's rule
  replaces. Keep `load`/`summarize`.
- **Rewrite** `evals/autotune/program.md` as the day-session brief: read the report, pick one
  broken task, produce one of the three outputs, never touch the §4 paths.
- **Change** `scripts/autotune-night.sh`:
  - Remove the `claude -p` block (`autotune-night.sh:595-640`).
  - Run `night-main` twice, then `eval-branch` for each queue line, then the report and the
    optional push.
- **Leave** `evals/harness/run.py` and `tasks.json` unchanged. Task changes arrive as PRs.

## Done when

1. `python -m evals.autotune night-main` appends two full-suite main runs to the history, and the
   report lists every task's state and each failure's cause.
2. The budget is per night: a ninth night runs even after $10 of lifetime spend.
3. `eval-branch` refuses a diff touching any §4 path, with a test for each path, and runs no site
   when the gate tests fail.
4. `triage.decide` gives keep, rerun and discard as tested in `tests/autotune/test_triage.py`.
5. A night with one queued branch writes its verdict, and the next day session posts it on the PR.
6. The first v2 week produces at least one owner-reviewed PR for a task that was broken on night
   1, or a task-validity PR the owner accepts or rejects.
7. The night script no longer starts a Claude agent, and the whole `tests/autotune` suite passes
   on Linux.

## 7. Alternatives rejected

- **A wider knob surface or a lower bar (+0.5).** The ceiling argument in §1.2 still holds: no
  knob flips a 0/18 task, and a lower bar only keeps more noise.
- **A night agent that writes `zoya/` patches and self-keeps.** This would run unreviewed code
  in the owner's Chrome. The only thing between that code and the gate would be a path guard. It
  would also burn night hours that measurement needs, and a night agent can't do better
  diagnosis than a day session with the same code.
- **Statistical tests (bootstrap, Fisher) on totals.** Near-deterministic tasks carry their
  signal per task, and pooling throws it away.
- **An LLM judge instead of regex checks.** Adds cost and a new noise source, and the checks
  aren't what's failing.
- **A fully offline or cloud eval (headless Chrome, recorded pages).** `zoya` needs macOS to
  import. `record_web.py` captures element tables only, not whole tasks. Live sites are the
  product.
- **Per-site fixes or skills.** Forbidden, and `tests/test_no_site_hardcoding.py` enforces it.
- **Auto-quarantining failing tasks.** It would make the score look better without making the
  product better. Validity is the owner's call, through a PR.
