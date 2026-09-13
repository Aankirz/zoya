# Decisions

Settled choices for Zoya. Agents must not change these without the owner's approval; if one must change, update this file in the same PR.

| # | Date | Decision | Why | Doc |
|---|---|---|---|---|
| D1 | 2026-09-13 | Product name and wake word: **Zoya / "Hey Zoya"** | High recall like Siri/Alexa; rare "Z" + "oy" sounds → few false triggers; no clash with "Hey Siri" (rejected: Beacon, Meera, Iris, Nova) | §7.1 |
| D2 | 2026-09-13 | **All agent logic runs locally on the Mac**; AWS Bedrock provides models | Agents must control the local mouse, keyboard, apps and logged-in browser | §8.2 |
| D3 | 2026-09-13 | Agent framework: **Strands Agents SDK** (Python); voice via **BidiAgent + Nova 2 Sonic**, fallback Transcribe + Polly | Hackathon ingredients; real-time interruptible voice | §9.2 |
| D4 | 2026-09-14 | Models: **rules → Nova Micro** router; **Sonnet 5** orchestrator, computer use, PPT content; **Haiku 4.5** screen description and summaries; **Nova Canvas** images | Fast where the user waits, best quality where they don't; Nova Micro and Nova 2 Lite swaps only if they pass §17.1b quality gates | §10, §10.1 |
| D5 | 2026-09-14 | **No local LLMs** for the hackathon | RAM/heat next to Chrome, load time, weaker structured output; rules already give ~0 ms | §10.1 |
| D6 | 2026-09-13 | Tool tiers: **T0 direct → T1 Accessibility API → T2 browser DOM → T3 pixel computer use** | Speed, reliability and token cost | §9.4 |
| D7 | 2026-09-13 | **Code-enforced confirmation**: voice-issued, single-use, 60 s tokens + click guard; silence never means yes | Safety for blind users; prompt-injection defence | §9.9, §12 |
| D8 | 2026-09-13 | Memory: **Supermemory** (free plan) | 2 tools, < 1 h integration; AgentCore Memory is the swap-in alternative | §9.8 |
| D9 | 2026-09-14 | Earcons: **UI SFX `zen` pack (CC0)**, `soft` as alternative; final pick by ear in Phase 0 | Coherent calm family, public domain, semantic cue names | §7.3 |
| D10 | 2026-09-14 | Multitasking via **Task Manager**: max 3 tasks; background/browser tasks parallel; GUI tasks exclusive; user commands always win the foreground | Users assign tasks and keep navigating | §9.13 |
| D11 | 2026-09-13 | Browser automation: **Playwright with a dedicated Zoya Chrome profile**, launched once at startup | Chrome blocks automation of the default profile; avoids 2–3 s cold starts | §9.7 |
| D12 | 2026-09-13 | `anthropics/commerce-agents` used for **patterns only**, not as a dependency | Built for store-owned backends and never places orders | §9.12 |
| D13 | 2026-09-13 | Clicky (farzaa/clicky) used for **patterns now**, possible Swift shell **after** the hackathon | Swift + Python in 48 h is too costly | §9.1, §9.11, §20 |
| D14 | 2026-09-13 | Examples use **₹ / Amazon.in**; hackathon length **48 h**; budget **$100 AWS credits** | Owner's context | §14 |
| D15 | 2026-09-14 | Zoya's voice: **Nova 2 Sonic `kiara`** (feminine, English-India + Hindi); alternative `tiffany`; Polly fallback `Kajal`. Zoya answers questions conversationally, not only commands | Owner wants a natural female voice; Indian users and Hinglish | §7.4, §9.2 |
| D16 | 2026-09-14 | **Sarvam AI not used** for the hackathon | Nova 2 Sonic listens, thinks and speaks in one interruptible stream with native Strands support; Sarvam would add latency and code without saving meaningful AWS credits | §7.4 |
| D17 | 2026-09-14 | **One region for everything: `ap-northeast-1` (Tokyo)** | Nearest region to Bangalore that offers every Zoya model: Nova 2 Sonic and Nova Canvas natively, Claude and Nova Micro natively or via cross-region inference. One region keeps setup, model access and quotas simple on a new account; Mumbai lacks Nova 2 Sonic and Nova Canvas. Phase 0 measures latency; fallback `us-west-2` | §13.5.4 |
| D18 | 2026-09-14 | **No Cloudflare** (Workers, AI Gateway) in the request path | Zoya calls Bedrock directly from the Mac; a proxy adds a network hop, can't speed up model inference or cut the Bedrock bill, and complicates Nova Sonic's bidirectional stream | §8.2 |
| D19 | 2026-09-14 | Wake word: **local Whisper `base.en` + Silero VAD** (faster-whisper), not Picovoice or sherpa-onnx | Picovoice's free tier ended 30 June 2026. On a 54-clip test on the owner's Mac, Whisper detected 21/24 with 0/30 false triggers vs sherpa-onnx 10/24 (16/24 with 5 false triggers when tuned). Open source (MIT), no key; push-to-talk remains the backup | §9.1 |
