# Zoya

**A voice-first AI agent that operates a Mac for blind and low-vision people.**

Say **"Hey Zoya"** and describe a goal — *"order my usual groceries"*, *"make a presentation on renewable energy"*, *"what's on my screen?"* — and Zoya does the whole task: opens apps, drives the browser, clicks and types, remembers preferences, runs helper agents in the background, and narrates everything with calm speech and a vocabulary of soft sounds. Before anything irreversible (paying, sending, deleting) it **always** asks for a spoken "confirm".

> *VoiceOver tells you what's on the screen. Zoya does what you meant.*

Built for the **Vision OS** hackathon with the **Strands Agents SDK** and **Amazon Bedrock**.

---

## Status

🚧 **Initial setup only.** No product code yet. Build proceeds phase by phase — see [Build phases](#build-phases).

## Documentation (read in this order)

| Doc | What it's for |
|---|---|
| [`AGENTS.md`](AGENTS.md) | **Rules for every coding agent.** Read before touching code. |
| [`docs/ZOYA_TECHNICAL_DOC.md`](docs/ZOYA_TECHNICAL_DOC.md) | Source of truth: product, user flows, audio design, architecture, performance, cost, risks |
| [`docs/DECISIONS.md`](docs/DECISIONS.md) | Decisions already made — don't relitigate |
| [`docs/phases/`](docs/phases/) | One self-contained brief per build phase |
| [`docs/SESSION_PLAN.md`](docs/SESSION_PLAN.md) | Which Claude session builds what, merge order, test checkpoints |
| [`docs/PROGRESS.md`](docs/PROGRESS.md) | Checkpoint log: what works at each tag |
| [`docs/CREDENTIALS.md`](docs/CREDENTIALS.md) | Accounts, keys and permissions to prepare |
| [`.env.example`](.env.example) | Every environment variable |

## Architecture at a glance

```
"Hey Zoya" ─► Wake word (Porcupine, on-device) ─► earcon
                 │
                 ▼
   Voice layer: Strands BidiAgent + Amazon Nova 2 Sonic   (talk, interrupt, status)
                 │ start_task(goal)
                 ▼
   Intent router: rules (0 ms) → Amazon Nova Micro
        │ simple                         │ multi-step
        ▼                                ▼
   Fast tools (open app/URL,       Task Manager → one orchestrator per task
   notes, AppleScript)             (Strands Agent + Claude Sonnet 5)
                                        ├─ browser_agent   (Playwright, own Chrome profile)
                                        ├─ computer_agent  (screenshots + mouse/keyboard)
                                        ├─ ppt_agent       (python-pptx + Nova Canvas)
                                        ├─ screen_describer (Claude Haiku 4.5)
                                        └─ memory          (Supermemory)
   Safety layer: spoken-confirmation tokens + click guard on every risky action
   Audio engine: UI SFX "zen" earcons (CC0) + speech, never silent
```

Everything that controls the Mac runs **locally**; AWS Bedrock provides the models. Details: §8–§10 of the technical doc.

## Build phases

| Phase | Goal | Brief |
|---|---|---|
| 0 | Every cloud service and permission proven on the demo Mac | [phase-0](docs/phases/phase-0-foundations.md) |
| 1 | Typed command → Mac acts in ≤ 1 s and Zoya speaks | [phase-1](docs/phases/phase-1-brain-fast-actions.md) |
| 2 | Fully hands-free with the calm audio system | [phase-2](docs/phases/phase-2-voice-sound.md) |
| 3 | Nothing irreversible without a spoken "confirm" | [phase-3](docs/phases/phase-3-safety-gate.md) |
| 4 | Search, remember, and shop up to confirmation | [phase-4](docs/phases/phase-4-browser-shopping-memory.md) |
| 5 | Operate any app by seeing the screen | [phase-5](docs/phases/phase-5-computer-use.md) |
| 6 | Several tasks at once while the user keeps navigating | [phase-6](docs/phases/phase-6-multitasking-ppt.md) |
| 7 | Judges can see what Zoya is doing | [phase-7](docs/phases/phase-7-stage-polish.md) |
| 8 | Demo runs clean 3× in a row | [phase-8](docs/phases/phase-8-rehearsal-submission.md) |

**Parallel lanes:** after Phase 1, Phases 2 and 3 can run together; after Phase 3, Phases 4 and 5 can run together; Phase 7 can start any time after Phase 2.

## Getting started (after Phase 0 lands)

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
playwright install chrome
cp .env.example .env        # fill in values — see docs/CREDENTIALS.md
./sounds/audition.sh zen    # hear the earcon palette
```

macOS permissions required: **Microphone, Accessibility, Screen Recording** (and Automation per app) for the terminal/Python running Zoya.

## Sound credits

Earcons from [UI SFX](https://github.com/romainsimon/uisfx) — audio dedicated to the public domain under CC0 1.0 (see `sounds/candidates/LICENSE-AUDIO-uisfx.txt`).
