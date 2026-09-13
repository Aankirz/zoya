## 2026-09-13 — Technical design doc
- Created BEACON_TECHNICAL_DOC.md: capabilities, limitations, user flows, architecture, performance review, cost, build plan.

## 2026-09-13 — Overlay + commerce patterns
- Added 9.11 stage overlay and 9.12 commerce-agents patterns; updated stack, structure, build plan, cut list, demo setup, references.

## 2026-09-13 — Clicky patterns
- 9.1 push-to-talk backup, 9.6 multi-monitor, 9.11 action highlight, 20 roadmap Clicky fork, references.

## 2026-09-13 — Rename to Zoya + Wispr Flow lessons
- Product renamed Beacon to Zoya (folder, file, wake word rationale). Added 13.5 Wispr Flow lessons, intent router (9.3, 10, 13.1, 13.2), reference.

## 2026-09-14 — Multitasking Task Manager
- Added 9.13 Task Manager (resource classes, user-priority foreground, audio rules), Flow 11, updated 7.2, 9.2, 9.3, 9.5, build plan phase 8.

## 2026-09-14 — Clarify 4.1 table
- Confirmation column relabelled; No -> Just does it.

## 2026-09-14 — Model right-sizing
- Replaced Haiku defaults with rules/Nova Micro/Nova 2 Lite; PPT on Sonnet 5; new 10.1 section; updated cost, stack, build plan phase 0.

## 2026-09-14 — Quality gates
- Reverted screen description to Haiku 4.5; added 17.1b router eval + screenshot benchmark; phase 0 updated.

## 2026-09-14 — Sounds + phase-wise build plan
- Added sounds/candidates (UI SFX zen+soft, CC0) and sounds/audition.sh.
- 7.3 earcon palette mapped to UI SFX cues, fallback sources, design rules, ffmpeg pipeline; 9.10 source updated.
- Section 16 rewritten: Phases 0-8 with goal, build, out of scope, doc refs, done-when tests, judge demo.

## 2026-09-14 — Initial repository setup
- Moved technical doc to docs/, split phase briefs into docs/phases with file ownership and dependencies.
- Added README, AGENTS.md, CLAUDE.md, DECISIONS.md, CREDENTIALS.md, .env.example, .gitignore, pyproject.toml, empty package skeleton.
- Documented Supermemory free-plan pricing in 9.8.

## 2026-09-14 — Session plan
- Added docs/SESSION_PLAN.md (3 parallel Claude sessions, waves, merge order, test checkpoints T0-T7), docs/PROGRESS.md; Phase 1 owns contracts (config/events/speech); Phase 2 split into 2a audio / 2b voice.

## 2026-09-14 — No-PR workflow
- Sessions push branches and fast-forward merge into main after human approval; no pull requests (per owner).
