# Zoya

**A voice-first AI agent that operates a Mac for blind and low-vision people.**

Say **"Hey Zoya"** and describe a goal — *"order my usual groceries"*, *"make a presentation on renewable energy"*, *"what's on my screen?"* — and Zoya does the whole task: opens apps, drives the browser, clicks and types, remembers preferences, runs helper agents in the background, and narrates everything with calm speech and a vocabulary of soft sounds. Before anything irreversible (paying, sending, deleting) it **always** asks for a spoken "confirm".

> *VoiceOver tells you what's on the screen. Zoya does what you meant.*

Built for the **Vision OS** hackathon with the **Strands Agents SDK** and **AWS**.

---

## Status

🚧 **Hackathon build in progress.**

## Architecture at a glance

```mermaid
---
config:
  look: handDrawn
  theme: neutral
  flowchart:
    curve: basis
---
flowchart TB
  USER(["🗣️ “Hey Zoya, book a hotel in Goa for 2”"])

  subgraph MAC["💻 On the Mac: private and local"]
    direction TB
    HEAR["👂 <b>Hear</b><br/>Silero VAD + Whisper wake word<br/>Smart Turn end-of-turn · Whisper turbo on Apple GPU"]
    ROUTER{"⚡ <b>Router</b><br/>rules first · 0 ms"}
    FAST["Instant actions<br/>open app · music · notes · time"]

    subgraph STRANDS["🧠 Strands Agents SDK"]
      direction TB
      ORCH["<b>Orchestrator Agent</b><br/>one per task · streaming · hooks · cost cap"]
      SKILLS["<b>Skills & helper agents</b><br/>Amazon · MakeMyTrip · YouTube · Spotify · X<br/>browser · computer use · documents · memory"]
      GATE["🛡️ <b>Safety gate</b><br/>spoken “confirm” before pay · send · post · delete"]
      ORCH --> SKILLS --> GATE
    end

    ACT["🖱️ <b>Act</b><br/>Playwright browser · Accessibility API<br/>clicks and keys · Mac apps"]
    SPEAK["🔊 <b>Speak</b><br/>calm voice · earcons · live overlay"]
  end

  subgraph BRAIN["☁️ Models: one adapter, one setting"]
    direction LR
    NOVA["<b>Amazon Bedrock</b><br/>Amazon Nova"]
    OPENAI["<b>OpenAI</b><br/>fallback"]
    NOVA -. "fallback" .-> OPENAI
  end

  subgraph AWS["☁️ AWS services"]
    direction LR
    A1["🗣️ Polly · Translate"]
    A2["👁️ Rekognition · Textract"]
    A3["🗄️ DynamoDB · S3 · Secrets Manager"]
    A4["🔔 SNS · EventBridge Scheduler · Location"]
    A5["📈 CloudWatch · X-Ray"]
  end

  USER --> HEAR --> ROUTER
  ROUTER -- "simple" --> FAST --> SPEAK
  ROUTER -- "a real task" --> ORCH
  ORCH <--> BRAIN
  GATE --> ACT --> SPEAK
  SKILLS <--> AWS
  SPEAK -. "Polly voice" .-> A1

  classDef mac fill:#EEF5FF,stroke:#2F6FEB,color:#0B1F44
  classDef strands fill:#FFF7E6,stroke:#FF9900,color:#232F3E
  classDef aws fill:#FFF3E0,stroke:#FF9900,color:#232F3E
  classDef model fill:#F4F4F5,stroke:#52525B,color:#18181B
  classDef safe fill:#E8F7EE,stroke:#16A34A,color:#052E16
  class HEAR,ROUTER,FAST,ACT,SPEAK mac
  class ORCH,SKILLS strands
  class GATE safe
  class A1,A2,A3,A4,A5 aws
  class NOVA aws
  class OPENAI model
```

**How one request flows**
1. **Hear.** The wake word, end-of-turn detection and speech-to-text all run on the Mac. Your voice never leaves it.
2. **Route.** Simple commands take a rule and finish in milliseconds, with no AI call.
3. **Think.** A real task gets its own **Strands Agents** orchestrator. It plans with **Amazon Nova on Bedrock** and falls back to **OpenAI**, behind one provider adapter (`zoya/models.py`, `MODEL_PROVIDER`).
4. **Act.** Skills drive the browser and the Mac. Anything that pays, sends, posts or deletes passes the **safety gate** first, and only your spoken "confirm" unlocks it.
5. **Speak.** Zoya narrates each step with the Amazon Polly voice and soft earcons, and the overlay shows the same steps on screen.

| Layer | What powers it |
|---|---|
| Agent framework | **Strands Agents SDK**: agents, tools, hooks, streaming, OpenTelemetry |
| Models | **Amazon Bedrock (Amazon Nova)**, with **OpenAI** as fallback |
| Voice | Whisper on-device (hear) · **Amazon Polly** Kajal (speak) · **Amazon Translate** for Hindi |
| Seeing | ScreenCaptureKit + Accessibility API · **Rekognition** (reads amounts before confirming) · **Textract** (documents) |
| Memory and data | Supermemory · **DynamoDB** (task history, confirmation audit) · **S3** · **Secrets Manager** |
| Reach out | **SNS** (trusted-contact alerts) · **EventBridge Scheduler** (reminders) · **Location Service** (places near you) |
| Observability | **CloudWatch / X-Ray** traces via Strands OpenTelemetry |
| Safety | Voice-issued, single-use confirmation tokens · click guard · least-privilege IAM user |

> Our AWS account's Bedrock quotas were still pending while we built, so the live demo runs on the OpenAI fallback. Switching to Nova is one setting: `MODEL_PROVIDER=bedrock`.

Everything that controls the Mac runs **locally**.

## Getting started

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
playwright install chrome
cp .env.example .env        # fill in your own keys
python -m zoya.setup_models # one-time model download
.venv/bin/python -m zoya.main --overlay
```

macOS permissions required: **Microphone, Accessibility, Screen Recording** (and Automation per app) for the terminal/Python running Zoya.

## Sound credits

Earcons from [UI SFX](https://github.com/romainsimon/uisfx) — audio dedicated to the public domain under CC0 1.0 (see `sounds/candidates/LICENSE-AUDIO-uisfx.txt`).
