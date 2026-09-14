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

## 2026-09-14 — Sequential build loop
- Replaced parallel session plan with one-session, phase-by-phase build/test/fix/approve prompts; removed parallel wording from README, AGENTS.md, phase briefs.

## 2026-09-14 — Voice: Kiara + conversational answers
- Zoya voice set to Nova 2 Sonic kiara (feminine en-IN/Hindi), Polly Kajal fallback; §9.2 conversational question handling; Phase 2 tests 7-10; D15; audition.sh no longer uses robotic say.

## 2026-09-14 — Sarvam decision
- D16: Sarvam optional fallback voice via Phase 2 A/B only; SARVAM_API_KEY optional; roadmap Indian languages.

## 2026-09-14 — Trim env + fix audition
- .env.example reduced to 9 account-specific values; settings moved to config.py constants; Sarvam removed; audition.sh pack loop fixed (zsh word-splitting bug).

## 2026-09-14 — Regions + no Cloudflare
- D17 regions (ap-south-1, Sonic in ap-northeast-1), D18 no Cloudflare; env and credentials updated.

## 2026-09-14 — Single region Tokyo
- D17 changed to ap-northeast-1 for all models; removed AWS_REGION_NOVA_SONIC.

## 2026-09-14 — Verified model IDs
- Filled Bedrock model/inference-profile IDs in .env.example from ap-northeast-1 listing; created local .env.

## 2026-09-14 — Blank .env.example
- Removed all values from .env.example per owner; real values only in local .env.

## 2026-09-14 — Replace Picovoice
- Picovoice free tier ended; switched wake word to sherpa-onnx KWS (D19) across docs, pyproject, env, gitignore.

## 2026-09-14 — Wake word -> Whisper
- Benchmarked sherpa-onnx KWS vs faster-whisper on 54 clips; switched D19 to Whisper base.en + VAD; updated docs, pyproject, Phase 2 test.

## 2026-09-14 — Architecture audit
- Added docs/AUDIT.md (3 research agents + local tests: Supermemory, latency, wake word). Removed Nova Canvas, fixed coords/overlay/Strands APIs/caching, pinned strands extras, D20-D25, phase briefs updated.

## 2026-09-14 — Primary stack without AWS
- Added docs/STACK.md; D26-D29; rewrote phase 0-2 briefs, patched 1/5/6; README architecture, env example, credentials, pyproject; banners on technical doc and audit.

## 2026-09-14 — AWS services + document agent + voice test
- STACK §8 AWS services (access verified), §9 documents (HeyClicky/Glide research); D30-D32; phase briefs 0-7 updated; pyproject docx/openpyxl/reportlab; ElevenLabs/Polly test evidence in D31.

## 2026-09-14 — Voice locked: Polly Kajal neural
- D33; STACK, phase 0-2 briefs, README updated.

## 2026-09-14 — OpenAI primary + budget
- D34 provider order, D35 no org credentials, STACK §7 budget with verified prices, Phase 0 limits.

## 2026-09-14 — store=false
- D36: store=false on all OpenAI requests; STACK §3 rule with verified Strands behaviour; AGENTS security rule; Phase 0/1 tests.

## 2026-09-14 — Earcons: zen
- D9 confirmed zen; Phase 0 brief updated.

## 2026-09-14 — Minimal tests policy (D37)
- AGENTS.md §5 and docs/DECISIONS.md D37: tests only for privacy, safety gate, cost/money paths and parsers, to save build tokens.

## 2026-09-14 — Phase 0 foundations built and benchmarked
- Pinned pyproject.toml deps against PyPI; verified Strands OpenAIModel/openai_responses store=false mechanics against installed source and Fireworks' OpenAI-compatible base URL against its docs.
- Added zoya/config.py, zoya/models.py (provider adapter, D36 store=false enforced), tests/test_models_privacy.py, scripts/check_providers.py.
- Added tests/evals/router_eval.py, screen_benchmark.py (+ computer-use loop), voice_benchmark.py with fixtures; ran all against live OpenAI/Fireworks/ElevenLabs/AWS Polly.
- D40-D43: BRAIN_MODEL/VISION_MODEL=gpt-5.6-terra, ROUTER_MODEL=gpt-5.6-luna, ElevenLabs fallback voice Tara; documented gpt-5.6.* needs max_completion_tokens + reasoning_effort="none" for tool calls; Whisper returns Devanagari for Hindi input, not romanized Hinglish.
- .env filled with benchmark-chosen model IDs and voice ID (no secrets changed).
- Not done: S3 bucket for results (blocked by permission classifier, needs owner sign-off), real 20-command Whisper/Transcribe benchmark and mic/Accessibility permission grants (need the owner on this Mac).

## 2026-09-14 — Phase 0 review fixes (from reviewer session zoya-6c)
- Fixed real bug: zoya/models.py didn't set reasoning_effort="none", so a live Strands Agent+tool call through get_model() 400'd for both router and brain roles (D43); fixed and reverified live.
- Added tests/evals/brain_latency.py (D44): streamed time-to-first-token/sentence; neither gpt-5.6-luna nor -terra clears the <=1s preference, and terra is actually faster than luna here despite costing more.
- Added tests/evals/stt_benchmark.py + commands_data.py + scripts/record_commands.py (D45): Amazon Transcribe vs Whisper harness (batch via boto3, not the amazon-transcribe streaming SDK — it pins awscrt~=0.26.1 and broke the zoya AWS profile's login credential provider, caught and reverted). Fixed a real grading bug: Whisper normalizes spoken numbers to digits, so keyword matching needed both surface forms.
- Recorded computer-use call cost, ElevenLabs character usage (50/10,000), and that Fireworks balance isn't readable from the inference API key (D40/D41).
- Fixed voice_benchmark.json to store repo-relative paths and exclude Whisper's one-time model-load from per-clip latency.
- S3 bucket still not created — denied by Claude Code's permission classifier; the reviewer session asked for it again but a peer can't grant that approval, so it was not re-attempted (D46).
- 32fbc1b's direct push to main was this session's own user's explicit instruction (asked and confirmed twice), not an oversight — noted back to the reviewer session rather than reverting to a branch workflow.

## 2026-09-14 — Push directly to main (D47)
- AGENTS.md §7 + DECISIONS D47: no phase branches; builders push to main, coordinator session reviews.

## 2026-09-14 — Phase 1: brain + fast actions
- zoya/{config,events,aws,speech,router,prompts,orchestrator,__main__}.py, zoya/tools/{__init__,fast,notes}.py, tests/test_router_rules.py, tests/test_task_limits.py, tests/evals/router_eval.py rewritten; docs §9.4/§13.5 facts; .env.example OTEL var. Pushed d234433..5c3b610.

## 2026-09-14 — Phase 1 review fixes
- Removed free-form run_applescript (¬ line-continuation bypass) in favour of fixed media_control; multi-step commands skip the router model; AWS failures warn once per session; otel-collector.yaml for CloudWatch/X-Ray; .gitignore .claude/worktrees/.

## 2026-09-14 — Close Phase 0: STT decision, IAM user, benchmark bucket
- D48 Whisper primary/Transcribe fallback from owner recordings; D49 zoya-app least-privilege IAM (infra/iam/zoya-app-policy.json); stt_benchmark.py reads Transcribe output via S3 client; owner .wav recordings git-ignored.

## 2026-09-14 — Phase 7 overlay design direction
- Phase 7 brief + §9.11: AgentPet-style agent presence states and Apple HIG look (materials, motion, SF type, Reduce Motion/Transparency), 3 new Done-when items.

## 2026-09-14 — Phase 2 voice + sound (builder)
- zoya/audio.py mixer engine + zen earcons (scripts/build_sounds.sh, sounds/*.wav); zoya/speech.py streams Polly into the mixer with cancel() barge-in and ZOYA_DISABLE_TTS fallback testing.
- zoya/voice.py + zoya/main.py: VAD → mlx base.en wake/stop spotter (D51) → large-v3-turbo → router/brain; push-to-talk Control+Option; --test-wake/--no-wake/--disable-tts; voice timings in logs/timing.log.
- zoya/orchestrator.py: streamed sentence-by-sentence speech, native Strands cancel_signal stop, 6-turn follow-up context, start_task/stop_task/task_status; router sends questions straight to the brain.
- zoya/tools/weather.py (Open-Meteo, D50); tests for spotter parsers and stop path.

## 2026-09-14 — Phase 2 fixes from owner live run
- One-breath wake via turbo re-check, junk transcripts keep the wake window, volume ducking with guaranteed restore, Control+Option barge-in, echo gate for self-wake, cached_tokens logging, wake sweep eval; D50–D52.

## 2026-09-14 — Phase 2 diagnose: junk after wake
- Confirmed root cause by differential replay (tests/evals/wake_junk_replay.py); push-to-talk keys now fn + Shift (PUSH_TO_TALK_KEYS).

## 2026-09-14 — Phase 2 diagnose: turn-taking and background music
- Follow-up window, loudness-gated VAD, stop cooldown, filler filter, interrupted-turn context, media rule; replay eval extended; D53.

## 2026-09-14 — Phase 2: Smart Turn endpointing + wake veto
- Smart Turn v3.2 end-of-turn (D55), turbo veto of sound-alike wakes with name guard (D54), pinned onnxruntime/huggingface-hub.
