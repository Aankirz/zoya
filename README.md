# Zoya

**A voice-first AI agent that operates a Mac for blind and low-vision people.**

Say **"Hey Zoya"** and describe a goal — *"order my usual groceries"*, *"make a presentation on renewable energy"*, *"what's on my screen?"* — and Zoya does the whole task: opens apps, drives the browser, clicks and types, remembers preferences, runs helper agents in the background, and narrates everything with calm speech and a vocabulary of soft sounds. Before anything irreversible (paying, sending, deleting) it **always** asks for a spoken "confirm".

> *VoiceOver tells you what's on the screen. Zoya does what you meant.*

Built for the **Vision OS** hackathon with the **Strands Agents SDK** and **AWS**.

---

## Status

🚧 **Initial setup only.** No product code yet. Build proceeds phase by phase — see [Build phases](#build-phases).

## Documentation (read in this order)

| Doc | What it's for |
|---|---|
| [`AGENTS.md`](AGENTS.md) | **Rules for every coding agent.** Read before touching code. |
| [`docs/STACK.md`](docs/STACK.md) | **Current models, voice and providers** — overrides the technical doc |
| [`docs/ZOYA_TECHNICAL_DOC.md`](docs/ZOYA_TECHNICAL_DOC.md) | Source of truth: product, user flows, audio design, architecture, performance, cost, risks |
| [`docs/DECISIONS.md`](docs/DECISIONS.md) | Decisions already made — don't relitigate |
| [`docs/AUDIT.md`](docs/AUDIT.md) | Verified findings: what was tested, what was wrong, correct APIs and costs |
| [`docs/phases/`](docs/phases/) | One self-contained brief per build phase |
| [`docs/SESSION_PLAN.md`](docs/SESSION_PLAN.md) | The prompts to build, fix and approve each phase |
| [`docs/PROGRESS.md`](docs/PROGRESS.md) | Checkpoint log: what works at each tag |
| [`docs/CREDENTIALS.md`](docs/CREDENTIALS.md) | Accounts, keys and permissions to prepare |
| [`.env.example`](.env.example) | Every environment variable |

## Architecture at a glance

> Current stack: [`docs/STACK.md`](docs/STACK.md). AWS Bedrock is blocked on our account (zero quotas), so models come from OpenAI/Fireworks for now; Bedrock plugs in later via one setting.

```
"Hey Zoya" ─► Silero VAD + Whisper base.en (local) ─► earcon
                 │
                 ▼  your command
   Whisper large-v3-turbo on Apple GPU (local, multilingual) → text
                 │
                 ▼
   Router: rules (0 ms) ──► fast Mac actions (open app/URL, notes, AppleScript)
                 │ otherwise
                 ▼
   Strands Agents SDK — Task Manager → one orchestrator Agent per task
      brain model: OpenAI / Fireworks (Bedrock later)
        ├─ browser_agent    (Playwright, own Chrome profile)
        ├─ computer_agent   (ScreenCaptureKit screenshots + clicks + Accessibility API)
        ├─ ppt_agent        (python-pptx, text slides)
        ├─ screen_describer (vision model)
        └─ memory           (Supermemory)
   Safety layer: spoken-confirmation tokens + click guard (Strands hook)
                 │ streamed reply
                 ▼
   ElevenLabs streaming voice (Indian female) ─► speaker   · earcons (UI SFX zen)
   AWS: CloudWatch traces, SNS trusted-contact alerts, Polly fallback voice
```

Everything that controls the Mac runs **locally**.

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

**Phases are built one at a time.** Each must pass its checklist before the next starts. How: [`docs/SESSION_PLAN.md`](docs/SESSION_PLAN.md).

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
