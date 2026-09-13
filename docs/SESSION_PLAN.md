# Session Plan — one Claude session, one phase at a time

Simple loop: **build a phase → you test it → fix until it passes → merge → demo → next phase.**
No parallel sessions, no extra folders.

---

## The loop for every phase

1. **Start a fresh Claude session** in the repo (`cd ~/Desktop/zoya && claude`), or type `/clear` in the current one. A clean context per phase avoids confusion.
2. **Paste the phase prompt** (below).
3. Claude builds on a branch `phase-N-...`, pushes it, and gives you a **hand-off report**: each "Done when" item marked ✅ (verified by Claude) or 🧑 (you test it, with exact steps).
4. **You test** every item on the Mac.
5. **Something fails?** Paste the **fix prompt**. Repeat until everything passes.
6. **Everything passes?** Paste the **approve prompt**. Claude merges into `main`, pushes, and tags the phase.
7. **Record the judge demo clip** (listed in each brief) and fill one row in `docs/PROGRESS.md`.
8. Next phase.

**Never start the next phase until the current one fully passes.**

---

## Before Phase 0 (you)

```bash
cd ~/Desktop/zoya && git pull
cp .env.example .env      # fill in values — see docs/CREDENTIALS.md
./sounds/audition.sh      # listen, pick zen or soft
```

---

## Phase prompt (same for every phase — change only the number and file)

```text
Build Zoya Phase <N>.

Read fully first: AGENTS.md, docs/DECISIONS.md, and docs/phases/<phase file>.
The brief cites sections of docs/ZOYA_TECHNICAL_DOC.md as §x.y — read those too.

Rules:
- Start from the latest main: git switch main && git pull && git switch -c <branch from the brief>
- Build only what the brief lists under "Build"; respect "Not in this phase".
- Verify every API, model ID and package against official docs; never guess. Cite the URLs.
- Run ruff check . && black --check . && isort --check . && pytest before handing off.
- Push the branch (no pull request). Then give me a hand-off report:
  1. what you built,
  2. every "Done when" item marked ✅ verified by you, or 🧑 for me to test, with exact commands/steps,
  3. how to run it,
  4. the judge demo steps from the brief.
- Do not merge. Wait for my test results.
```

| Phase | `<N>` | `<phase file>` | Tag after approval |
|---|---|---|---|
| Foundations | 0 | `phase-0-foundations.md` | `v0.0-foundations` |
| Brain + fast actions | 1 | `phase-1-brain-fast-actions.md` | `v0.1-brain` |
| Voice + sound | 2 | `phase-2-voice-sound.md` | `v0.2-voice` |
| Safety gate | 3 | `phase-3-safety-gate.md` | `v0.3-safety` |
| Browser + shopping + memory | 4 | `phase-4-browser-shopping-memory.md` | `v0.4-shopping` |
| Computer use | 5 | `phase-5-computer-use.md` | `v0.5-computer-use` |
| Multitasking + PPT | 6 | `phase-6-multitasking-ppt.md` | `v0.6-multitask` |
| Stage polish | 7 | `phase-7-stage-polish.md` | `v0.7-stage` |
| Rehearsal + submission | 8 | `phase-8-rehearsal-submission.md` | `v1.0-demo` |

**Extra prep before specific phases**
- Phase 2: the "Hey Zoya" `.ppn` wake-word file from Picovoice.
- Phase 4: log into Amazon.in inside the Zoya Chrome profile when Claude asks.
- Phase 7: avatar images exported into `assets/avatars/`.

---

## Fix prompt (when something fails)

```text
Test results for Phase <N>:
- Item <#>: FAIL — <what you did> → <what happened> (paste errors/logs)
- Item <#>: PASS
Fix the failures on the same branch, rerun checks, push, and give me an updated hand-off report.
```

## Approve prompt (when everything passes)

```text
Phase <N> approved — all "Done when" items pass.
Rebase on origin/main, rerun tests, fast-forward merge into main, push main,
then tag and push: git tag <tag> && git push origin <tag>.
Add a row to docs/PROGRESS.md for this tag (what works now), commit and push it.
```

---

## Showing progress to judges

- Each tag (`v0.0` → `v1.0`) is one step of growth.
- After each approval, record the brief's **judge demo** clip (QuickTime → New Screen Recording, with mic).
- `docs/PROGRESS.md` + the clips = a timeline from "models answer" to "hands-free order with overlay".

## If you fall behind

Cut in this order: Phase 7 → PPT images → multitasking → Supermemory (hard-code memory) → BidiAgent (use Transcribe + Polly).
**Never cut:** safety gate, "stop" command, earcons.
