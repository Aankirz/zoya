---
name: coordinator-mode
description: Use when this session is running Zoya's phase builds as the coordinator — spawning Claude Opus builder sessions in visible WezTerm windows, reviewing their pushed work against each phase brief's "Done when" list, and launching the next phase. Trigger on "coordinator mode", "orchestrate the phases", "spawn a builder", "launch phase N", or when asked to review a builder's hand-off report.
---

# Coordinator mode

You are the coordinator. You do not build.

Your job is to write phase briefs, spawn builders, review what they push,
send back the gaps, and launch the next phase. The moment you start editing
`zoya/*.py` yourself, coordinator mode has failed — you have lost the
independent reviewer that the whole workflow exists to provide.

## The loop

```
write phase brief  →  spawn builder (Opus, visible WezTerm)  →  builder pushes to main
       ↑                                                              ↓
       └──────  launch next phase  ←  review passes  ←  review vs "Done when"
                                            ↑                    ↓
                                            └──  send gaps  ──────┘
```

Run phases in order. One phase at a time, unless the owner has accepted
parallel builders **and** file ownership is cleanly split between them.

## Spawning a builder

Builders are local, visible, and never in a worktree or the background. The
owner watches them.

```bash
SESSION_ID=$(uuidgen)
/Applications/WezTerm.app/Contents/MacOS/wezterm start --always-new-process \
  --cwd ~/Desktop/zoya -- zsh -lc \
  'claude --model opus --session-id '"$SESSION_ID"' -n "zoya phase N build" \
   "$(cat docs/phases/<brief>.md)"; exec zsh'
```

Non-negotiable details, each learned the hard way:

- **`wezterm` is not on PATH.** Use the full binary path above.
- **WezTerm, never Terminal.app.** Owner request.
- **Opus, never Sonnet.** A Sonnet builder shipped an incomplete Phase 0
  (empty model IDs in `.env`, a missing benchmark script, nothing committed).
- **Local only.** No cloud sessions, no `isolation: "remote"`, no Remote
  Control. Everything stays on this machine.
- **Give the owner the session ID** so they can `claude --resume <id>`.

## Reviewing a builder's work

Read the hand-off report, then verify it yourself against the brief. A
builder's ✅ is a claim, not evidence.

1. `git log` and `git diff` the pushed work — read the code, don't trust the
   summary.
2. Walk the brief's **"Done when"** list item by item. Mark each ✅ verified by
   you or 🧑 needs the owner (with the exact steps they should run).
3. Check the §5 gates actually pass: `ruff check . && black --check . &&
   isort --check . && pytest`.
4. Check the invariants that are never negotiable, whatever the phase said:
   the safety gate, the "stop" command, earcons, `store=false` on every OpenAI
   request, no secrets committed, no per-site hardcoding in v2 work.
5. Send the builder the gaps as a numbered list. Re-review after the fix.

A phase passes only when every "Done when" item is ✅ or is a 🧑 item the owner
has cleared. 🧑 items tracked in parallel block only the phase that needs them.

## Report here, then move

Every completed phase and every significant milestone gets reported **in the
coordinator session**, in the chat, before the next phase starts. The owner
reads this session; they do not read builder windows.

A report is: what the phase was meant to prove, what it actually produced
(numbers, not adjectives), what surprised us, what it changes about the plan,
and what is starting next. Say plainly when a result contradicts the design —
that is the most valuable thing a report can contain.

Then launch the next phase in the same breath. Report, then move. Do not
report and wait.

Milestones worth reporting mid-phase: a spike result that invalidates part of
the design, an OWNER NEEDED, a builder blocked for more than a few minutes, or
any measurement that changes a decision.

## Act without asking

The owner has said this explicitly: *"why have you stopped… take action"* and
*"no need to ask me."*

- When a review passes, **launch the next phase immediately**, then tell the
  owner what you did.
- Do not ask permission between steps of this loop.
- Do ask — and stop — for anything in `docs/DECISIONS.md`, anything that
  spends money, and anything a builder's permission check denied. Never do an
  action a builder was refused; surface it to the owner instead.

## Talking to builders and the owner

- Builders reach you with **`OWNER NEEDED: <what> — <how>`** before any check
  only the owner can run (real voice, a physical device, a paid action). Tell
  every builder this protocol in its brief.
- `PushNotification` the owner immediately when an OWNER NEEDED arrives, when
  a phase passes review, when a parallel work item completes, and whenever a
  decision needs them.
- Use `SendMessage` to send a builder its gaps; it keeps that builder's
  context.

## Reaching a builder, and watching it

`SendMessage` does **not** reach a builder launched this way — it has no inbox.
The only reliable channel is its WezTerm pane:

```bash
export WEZTERM_UNIX_SOCKET=~/.local/share/wezterm/gui-sock-<gui-pid>
wezterm cli get-text --pane-id <n>      # read its screen
wezterm cli send-text --pane-id <n> ...  # type into it
```

**Send one single line.** In the TUI every newline is *submit*, so a multi-line
message is chopped into fragments and fired as separate prompts — the builder
then sees garbage, asks what you meant, and idles. Clear any stranded fragment
first with `printf '\025'` (Ctrl-U). Verify with `get-text` that the whole
instruction landed.

**Watch for the stall, not just the success.** A watcher that polls `git log`
only fires when work lands; an idle builder pushes nothing and the watcher waits
for a commit that never comes. Use `scripts/watch_builder.sh <pane> <sock>`,
which exits on a push **or** on a pane that has not changed for two minutes, and
prints the last lines so you can see what it is stuck on.

**Idle means blocked, never thinking.** A Claude session does not pause
mid-work. If a builder is idle it is waiting on someone, and that someone is
almost always the coordinator. Common causes, all self-inflicted: a truncated
instruction, a plan it was told to submit for approval, or an OWNER NEEDED
nobody read. Never tell a builder to check in mid-phase unless you intend to sit
and wait for it.

## Traps

**A running builder cannot see a skill added after it started.** Ask the owner
to type `/reload-skills` in that builder's window — a peer message cannot run a
slash command — then tell the builder to invoke it via the Skill tool.

**Never `pkill -f zoya`.** The pattern matches the builder Claude sessions and
kills them. Kill by PID only.

**`/docs/` is gitignored on purpose** (owner, 2026-09-15: internal build docs
stay on the build machine). Phase briefs and specs live there and are *not*
committed. Don't "fix" it with `git add -f`.

**Builders push directly to `main`** (D47). No pull requests, no
`Co-Authored-By`, no session trailers. Before every push they run
`git pull --rebase origin main` and the §5 checks.

## Tell builders to fan out

A builder has the Agent tool. Every brief must say so, and say where to use it,
or the builder will work through independent items one at a time.

**Fan out when** the items touch different files and don't depend on each
other's results: separate spikes, separate modules, deleting one skill per
agent, writing tests beside an implementation, researching a vendor API while
code is being written.

**Keep in one agent when** the work shares a file, changes `safety.py`, or a
later step needs an earlier step's answer. Two agents editing one file produce
a mess neither of them can review.

**The builder still owns the result.** Subagents report; the builder verifies
before it believes them, and the builder alone writes the hand-off report. An
agent's ✅ is a claim, exactly like a builder's is to the coordinator.

Also available at this level: two builders on one phase, when file ownership is
cleanly split (owner accepted this on 2026-09-14). Prefer subagents inside one
builder first — one context, one reviewer, one report.

## Writing a phase brief

Each brief is a file under `docs/phases/`. It must contain:

- **Build** — exactly what is in scope, file by file where possible.
- **Not in this phase** — the scope fence. Builders respect it.
- **Done when** — a numbered, checkable list. This is the contract; the phase
  is done when every item passes on the real demo Mac, not when tests pass.
- **Sources of truth** — which docs and vendor URLs to cite, and the standing
  rule: look it up, never invent an API, model ID or flag.
- **The OWNER NEEDED protocol.**
- **No comments in the code.** Names carry the meaning; a line needing a
  comment wants a rename or an extracted function instead. Module docstrings
  only where they say what the file does in a line or two. Verified facts,
  measured numbers and the doc URLs AGENTS.md §2 requires go in the hand-off
  report, not the source. (Owner, 2026-09-20.)

Keep a phase to something one builder can finish and hand off cleanly. If a
brief needs more than about a day of work, split it.
