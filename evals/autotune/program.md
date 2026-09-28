# Autotune: the overnight program

You are tuning Zoya while its owner sleeps. You make one small change at a time,
the runner measures it against the harness eval, and it keeps the change only if it
clearly helps. You never edit code yourself: you write a patch, and the runner decides.

## Where things are

- The main checkout is your working directory. Do not edit anything in it.
- The experiments run in the worktree `../zoya-autotune`, on the branch `autotune`.
  Read the current surface files there, because kept changes land there and not on `main`:
  - `../zoya-autotune/zoya/config.py`
  - `../zoya-autotune/zoya/prompts.py`
- The ledger of every experiment: `logs/autotune/ledger.tsv`
  (`utc, exp_id, description, patch_sha, success_mean, cents_total, seconds_median, verdict`).
- The current baseline, including its per-run summaries: `logs/autotune/baseline.json`.
- The latest report: `logs/autotune/report-<date>.md`.
- The raw eval runs, with each task's `error`: `../zoya-autotune/logs/harness/autotune-*.json`.
- The guard's rules: `evals/autotune/surface.py`. Read it before your first patch.

## Your tools

You have exactly three: the Read tool, the Write tool for files under `logs/autotune/patches/`,
and Bash for only two commands: `date` (with any format) and
`.venv/bin/python -m evals.autotune try ...`. Any other Bash command is refused; that does not
mean Bash is off. Read files with the Read tool, not `cat` or `git`. The runner checks the
worktree, the baseline and the budget itself before every experiment, so you do not.

## The surface: the only things you may change

1. These constants in `zoya/config.py`, and only within their ranges:

   | constant | allowed |
   | --- | --- |
   | `BRAIN_PLANNING_REASONING_EFFORT` | `"low"`, `"medium"`, `"high"` |
   | `BRAIN_STEP_REASONING_EFFORT` | `"none"`, `"low"` |
   | `COMPUTER_MAX_JEV_STEPS` | 6 to 20 |
   | `MAX_FAILED_ATTEMPTS` | 2 to 5 |
   | `WEB_RENDER_WAIT_S` | 2.0 to 10.0 |
   | `MAX_TOOL_CALLS_PER_TASK` | 20 to 60 |

2. Prompt text in `zoya/prompts.py`, except any line that contains a protected word:
   confirm, password, otp, card, pay, order, purchase, safety, never, stop, secret, store,
   untrusted, delete, send, post. Do not add, remove or change those lines.

Never edit anything else. Never touch safety checks, confirmation rules, thresholds or cost
caps, even if a change there looks like it would raise the score. Never try to get around the
guard: no renames, no new files, no binary patches, no splitting a forbidden change across
patches. If the guard rejects a patch, read its reason and move on; do not retry a variant
of the same thing.

## Each experiment

1. **Read** the ledger, the baseline and the latest report. Know what has been tried,
   what was kept and what the budget has left.
2. **Think about the last experiment first.** If it was discarded or rejected, say in one
   or two sentences why you believe it failed: which tasks or groups got worse, what the
   `error` fields say, whether the cost went up. Let that decide what you try next. Do not
   try the same idea again with a slightly different number unless you have a reason.
3. **Propose one small, reversible change**: one constant, or one prompt sentence.
   Prefer changes you can explain from the evidence over random search.
4. **Write it as a unified diff** against the worktree, with paths `a/zoya/...` and
   `b/zoya/...`, into `logs/autotune/patches/<next exp_id>.diff`. Check your context lines
   against the worktree's current file, or `git apply` will refuse it.
5. **Run it**, with the same `--group` and `--runs` as the baseline (the night uses 3;
   two repeats are mostly noise):

   ```
   .venv/bin/python -m evals.autotune try logs/autotune/patches/<id>.diff --desc "<what and why, one line>" --runs <N> --group "<group>"
   ```

   It prints `keep: ...`, `discard: ...`, or a refusal. A kept patch is committed on
   `autotune` and becomes the new baseline; a discarded one is undone.
6. Repeat.

A patch is kept only if the mean success rises by at least one task, no group gets worse,
and the cost per success is at most 15% worse. Aim for that.

## When to stop

Stop and end your turn, without starting another experiment, as soon as any of these is true:

- the runner refuses with `budget:` (the ledger's spend plus the estimate would pass
  `AUTOTUNE_BUDGET_CENTS`);
- the local time is at or past the stop time in your prompt (check with `date` before every
  experiment);
- the runner refuses because the worktree is dirty, missing or on another branch. Do not
  try to repair it; the owner will look in the morning.

Before you stop, write two or three sentences on what you learned tonight and what you would
try next. The night script writes the report.
