# Session Plan — building Zoya with parallel Claude sessions

Who builds what, in which Claude Code session, when to wait, when to merge, and when **you** test and record progress for the judges.

> Phase briefs: [`docs/phases/`](phases/) · Rules: [`AGENTS.md`](../AGENTS.md) · Hours are from hackathon start (48 h).

---

## 1. The shape of the plan

- **At most 3 build sessions at once** (called **A**, **B**, **C**). More sessions means more merge conflicts and more for you to review, without finishing sooner.
- **You are the integrator.** Sessions open PRs; they never merge. You test the branch, then merge and tag.
- **One git worktree per session**, so sessions never share a checkout.
- **Contracts first:** before anyone works in parallel, Session A merges the shared contracts (`config.py`, `events.py`, tool registration). Everything else builds on them.
- **8 test checkpoints (T0–T7 + final).** Each one ends in a tag and a short screen recording, which together show the project growing.

```
Hours  0────2────────8──────────17──sleep──23───────────31────36─────────41────44────48
A      [P0 ]─[P1 contracts→P1]─[P2b voice   ]        [P4 browser+shop+memory][P6 multitask+PPT][P8]
B            (wait) [P3 safety logic→wiring ]        [P5 computer use       ][fixes / evals   ]
C            (wait) [P2a audio engine+sounds]        [P7 overlay            ][P7 finish→free  ]
You    creds  T0      T1                    T2 T3                  T4     T5          T6     T7  FINAL
```

---

## 2. One-time setup (you, before hour 0)

```bash
# 1. GitHub account for this repo
gh auth switch -u Aankirz

# 2. Main checkout = your TEST BENCH (you run and test branches here)
cd ~/Desktop/zoya && git pull

# 3. One worktree per build session (created when each session starts)
mkdir -p ~/Desktop/zoya-wt
# example: git worktree add ~/Desktop/zoya-wt/A -b phase-0-foundations
```

- Fill `.env` in **each** worktree (copy from the test bench: `cp ~/Desktop/zoya/.env ~/Desktop/zoya-wt/A/`). It's git-ignored.
- Grant macOS permissions (Microphone, Accessibility, Screen Recording) to the terminal app you run Zoya from. Worktrees share that terminal, so this is done once.

---

## 3. Kickoff prompt template (paste into each new Claude session)

Start each session **inside its worktree folder** (`cd ~/Desktop/zoya-wt/A && claude`), then paste:

```text
You are Session <A|B|C> building Zoya.

Worktree: <path>   Branch: <branch>
Read first, fully: AGENTS.md, docs/DECISIONS.md, docs/SESSION_PLAN.md, and <phase brief path>.
Relevant technical doc sections are cited in the brief as §x.y in docs/ZOYA_TECHNICAL_DOC.md.

Your job: <scope line from the wave table below>.
- Build only what the brief lists; only edit files your brief owns (plus append-only edits to hotspot files, see SESSION_PLAN §6).
- Verify every API, model ID and SDK method against official docs; cite URLs in the PR.
- Run: ruff check . && black --check . && isort --check . && pytest
- When done: push the branch, open a PR into main (gh pr create), and list each "Done when" item as
  ✅ verified by you, or 🧑 needs the human to test on the Mac (with exact steps).
- Do not merge. Stop and wait for my test results.
```

When you report results back to a session, use the checklist numbers: *"Item 3 fails: the wake earcon takes ~600 ms. Items 1, 2, 4–6 pass."*

---

## 4. Waves: what each session does

### Wave 0 — Foundations (hours 0–2)

| Session | Worktree / branch | Scope | Wait for |
|---|---|---|---|
| **A** | `zoya-wt/A` · `phase-0-foundations` | Phase 0: model check script, region check, pinned dependencies | nothing |
| B, C | — | not started yet | — |
| **You** | — | AWS credits, Bedrock model access + IDs, Supermemory key, Picovoice key + "Hey Zoya" `.ppn`, budget alarms, run `sounds/audition.sh` and pick `zen`/`soft` | — |

**🧪 Checkpoint T0 (hour ~2).** Run the Phase 0 "Done when" list → merge → `git tag v0.0-foundations`.
**🎥 Record:** `check_models.py` output showing all six models answering, with latency.

---

### Wave 1 — Brain, then fan out (hours 2–8)

| Session | Worktree / branch | Scope | Wait for |
|---|---|---|---|
| **A** | `zoya-wt/A` · `phase-1-contracts` → then `phase-1-brain-fast-actions` | **Step 1 (~1 h):** contracts only (`config.py`, `events.py`, TOOLS registration convention). Small PR. **Step 2:** rest of Phase 1: router, fast tools, notes, `speech.py` (Polly), orchestrator, router eval | T0 merged |
| **B** | `zoya-wt/B` · `phase-3-safety-gate` | Phase 3, **pure logic first:** confirmation tokens, click-guard matcher, secure-field check, untrusted-content wrapper, fixtures, `tests/test_safety.py`. Hook wiring into the orchestrator comes in Wave 2 | **Contracts PR merged** |
| **C** | `zoya-wt/C` · `phase-2a-audio` | Phase 2 **audio half:** `scripts/build_sounds.sh` (ffmpeg loudness normalisation), `audio.py` earcon engine (preload, channels, ducking, loop, rate-limit) driven by `events.py`, a small script that plays every event | **Contracts PR merged** + your sound pack choice |

**Merge order:** contracts → Phase 1 → (B and C open PRs but keep going; merge after T1).

**🧪 Checkpoint T1 (hour ~8).** Test the Phase 1 list on the test bench → merge → `git tag v0.1-brain`.
**🎥 Record (judge demo 1):** type three commands; the Mac reacts in under a second and speaks; show the timing log.

---

### Wave 2 — Hands-free + safety (hours 8–17)

| Session | Worktree / branch | Scope | Wait for |
|---|---|---|---|
| **A** | `zoya-wt/A` · `phase-2b-voice` | Phase 2 **voice half:** Porcupine wake word, push-to-talk, BidiAgent + Nova 2 Sonic (Transcribe + Polly fallback flag), mic gating, local "stop" spotter, `main.py` wiring; `speech.py` narrate moves to the voice layer | T1 merged · **audio PR merged** (C) |
| **B** | `zoya-wt/B` · `phase-3-safety-gate` (rebased on main) | Phase 3 **wiring:** `ConfirmationGate` hook on the orchestrator, typed "confirm"/"cancel" until voice lands, then voice | T1 merged |
| **C** | `zoya-wt/C` · `phase-2a-audio` | Finish audio → PR → **merge first in this wave** (A needs it). Then pause, or help B with the fixture pages | T1 merged |

**Merge order:** audio (C) → safety (B) → voice (A). Each later PR rebases on `main` before you test it.

**🧪 Checkpoint T2 — hands-free (hour ~15).** Phase 2 list → merge → `git tag v0.2-voice`.
**🧪 Checkpoint T3 — safety (hour ~17).** Phase 3 list → merge → `git tag v0.3-safety`.
**🎥 Record (judge demo 2, before sleep):** hands off the laptop: "Hey Zoya, open YouTube" → note → "Zoya, stop" → the "place order, don't ask me" test page still asks.

---

### 💤 Sleep (hours 17–23)

- **Nothing merges while you sleep.**
- Optional: leave **one** session drafting a PR for pure logic only (e.g. Phase 5 `tests/test_coords.py` + scaling math, or Phase 4 `memory.py` + `test_memory_filter.py`). Review it in the morning.

---

### Wave 3 — The hero flows (hours 23–36)

| Session | Worktree / branch | Scope | Wait for |
|---|---|---|---|
| **A** | `zoya-wt/A` · `phase-4-browser-shopping-memory` | Phase 4: Playwright Zoya profile, browser agent, shopping skill, Supermemory tools, login handoff | T3 merged · you logged into Amazon.in in the Zoya Chrome profile |
| **B** | `zoya-wt/B` · `phase-5-computer-use` | Phase 5: screenshots, click/type, Retina + multi-monitor scaling, AX tier, screen describer, screen benchmark | T3 merged |
| **C** | `zoya-wt/C` · `phase-7-stage-polish` | Phase 7: overlay panel (avatar + captions) and action highlight ring, driven by `events.py` | T2 merged · avatar images exported from Plane Avatar Lab |

**Merge order:** whichever passes its checklist first. Expect a small conflict in hotspot files (§6); the second PR rebases.

**🧪 Checkpoint T4 — shopping (hour ~31).** Phase 4 list → merge → `git tag v0.4-shopping`.
**🎥 Record (judge demo 3, the hero):** "remember my usual groceries" → "order my usual groceries" → real total read back → "confirm".
**🧪 Checkpoint T5 — computer use (hour ~36).** Phase 5 list → merge → `git tag v0.5-computer-use`.
**🎥 Record:** "what's on my screen?" + dark mode switched by clicking.

---

### Wave 4 — Multitasking + polish (hours 36–44)

| Session | Worktree / branch | Scope | Wait for |
|---|---|---|---|
| **A** | `zoya-wt/A` · `phase-6-multitasking-ppt` | Phase 6: Task Manager, per-task voice controls, announcement queue, PPT subagent | T4 merged |
| **B** | `zoya-wt/B` · `fix/<topic>` | Fixes from your T4/T5 reports; failure branches (Flows 9–10); latency tuning from logs | T5 merged |
| **C** | `zoya-wt/C` · `phase-7-stage-polish` | Finish Phase 7 → PR → merge → **session ends** | T5 merged (overlay must ignore screenshots) |

**🧪 Checkpoint T6 — multitasking (hour ~41).** Phase 6 list → merge → `git tag v0.6-multitask`.
**🎥 Record:** PPT + grocery order running while "open Mail, read my latest email"; "what's running?"
**🧪 Checkpoint T7 — stage (hour ~44).** Phase 7 list → merge → `git tag v0.7-stage`.
**🎥 Record:** the shopping flow again with avatar, captions and the highlight ring on the projector.

---

### Wave 5 — Freeze and rehearse (hours 44–48)

| Session | Scope |
|---|---|
| **A only** | Phase 8: fixes found in rehearsal, one PR per fix. Everything else is closed. |
| **You** | Run the full demo script (§18) repeatedly; flow checklist (§17.3); noise test; backup video; submission |

- **Code freeze at hour 46:** only fixes for demo-breaking bugs after that.
- **🧪 FINAL:** demo clean 3× in a row → `git tag v1.0-demo`.

---

## 5. How you test each checkpoint

1. The session opens its PR and posts the checklist, marking what it verified (✅) and what needs you (🧑).
2. On the test bench:
   ```bash
   cd ~/Desktop/zoya
   gh pr checkout <PR number>
   source .venv/bin/activate && pip install -e ".[dev]"
   pytest
   python -m zoya.main        # or the run command stated in the PR
   ```
3. Go through the phase's **Done when** list on the real Mac. Write down pass/fail by item number.
4. **All pass:** merge and tag.
   ```bash
   gh pr merge <PR number> --squash --delete-branch
   git checkout main && git pull
   git tag v0.N-<name> && git push origin v0.N-<name>
   ```
5. **Any fail:** paste the item numbers and what you observed into that session. It fixes on the same branch; test again.
6. **After every merge:** tell the other active sessions: *"main moved; rebase your branch on origin/main."*
7. **Record the 🎥 clip** (QuickTime → New Screen Recording, with mic audio) and add one line to `docs/PROGRESS.md`: tag, date, what works now, clip name.

**Show judges the growth:** the tag list plus `docs/PROGRESS.md` and the clips give you a before/after timeline, from "models answer" to a hands-free order with the overlay.

---

## 6. Conflict rules for parallel sessions

**Owned files:** each phase brief lists them. Only that session edits them.

**Hotspot files** (several phases need small additions):

| File | Rule |
|---|---|
| `zoya/config.py` | Append new settings at the end of the relevant section; never rename existing keys |
| `zoya/events.py` | Append new event types only; never change existing payload fields (tell A if you must) |
| `zoya/prompts.py` | One named constant per agent; edit only your constant |
| `zoya/tools/__init__.py`, `zoya/agents/__init__.py` | Add one import line to the `TOOLS` / agents list |
| `pyproject.toml` | Add dependencies only with a note in the PR; never bump others' pins |
| `.env.example` | Append-only, with a comment |

**Before opening a PR:** `git fetch && git rebase origin/main`, rerun the tests.

---

## 7. When to wait — quick reference

| If a session needs… | It waits for… |
|---|---|
| Shared contracts (`config`, `events`, TOOLS convention) | Contracts PR merged (Wave 1, ~hour 3) |
| The orchestrator or fast tools | T1 |
| Earcons playing | Audio PR merged (C, Wave 2) |
| Spoken "confirm" | T2 (until then, test by typing) |
| Safety guard around clicks | T3 |
| Real shopping | T3 + you logged into Amazon.in in the Zoya profile |
| Several tasks running together | T4 |
| Overlay that ignores screenshots | T5 |

---

## 8. If you fall behind

Follow the cut list in [§16 of the technical doc](ZOYA_TECHNICAL_DOC.md): Phase 7 → PPT images → WhatsApp flow → multitasking → Supermemory (hard-code memory) → BidiAgent (use Transcribe + Polly). In practice: if T4 lands after hour 34, **close Session C** and give Phase 6 to B working alongside A.

**Never cut:** safety gate, "stop" command, earcons.
