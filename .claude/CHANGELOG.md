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

## 2026-09-14 — AEC research recorded
- AUDIT.md §5 + D56: measured wake rates under music, Apple VP limits, OpenWhispr AEC3+process-tap design, deps, risks.

## 2026-09-14 — Learning doc
- learning/learning.md: architecture overview and the story of phases 0–2 for the owner.

## 2026-09-14 — Offline model loading
- HF_HUB_OFFLINE at runtime, MODEL_PINS + zoya/setup_models.py, fail-fast on missing models; AUDIT §6 (startup hang on black-holed IPv6).

## 2026-09-14 — Phase 4: web research and in-tab site control
- Phase 4 brief: TinyFish Search/Fetch research tools, Spotify/YouTube in-tab control with the safety gate for subscribe/like/comment, 3 Done-when items.

## 2026-09-14 — Phase 2 final-run triage fixes
- D57: duck through wake wait, en/hi STT, junk/runaway filters, repeated-wake, filler prefixes, browser rule, prompt honesty; replays 6/6.

## 2026-09-14 — Web-first opening (D58)
- open_app opens Spotify/YouTube/WhatsApp/Gmail websites unless "app" was said; router explicit-app override.

## 2026-09-14 — Media keys for browser playback
- media_control posts system media keys (browser tabs + apps); AppleScript only for explicit app; Accessibility permission prompt.

## 2026-09-14 — Open fallback + fast-turn context (D59)
- open_app miss → orchestrator; fuzzy app lookup ≥ 3 chars; fast turns in conversation; skills-directory idea logged for Phase 4.

## 2026-09-14 — Harness research
- docs/research/harness.md: Strands feature audit, 3-layer harness design, caching plan, Phase 3–6 rollout (research only).

## 2026-09-14 — Harness rollout into phase briefs
- Phases 4–6: Strands-first harness layers from docs/research/harness.md (skills + actions + caching in 4, Shortcuts/recorded flows in 5, multi-agent in 6); phase 5 duplicate line removed.

## 2026-09-14 — Duck state survives a kill
- audio.py/main.py: SIGTERM/SIGHUP restore the volume; pre-duck level persisted to logs/duck_state.json and restored at startup after kill -9; no compounding over repeated kills (tests/test_duck_state.py)

## 2026-09-14 — Zoya Chrome profile confirmed (D60)
- DECISIONS D60 + §20 roadmap: Playwright Zoya profile for the hackathon; real-Chrome extension later.

## 2026-09-14 — Phase 3 safety gate
- zoya/safety.py, zoya/screen.py, zoya/tools/browser.py, tests/test_safety.py, fixtures, tests/evals/safety_replay.py: voice-minted confirmation tokens, fail-closed click guard, risk registry, OCR amount check, audit log (D61).
- orchestrator/voice/speech/audio/events/router/main: gate wiring, PTT answers a confirmation, warning/cancel earcons, EventLoopException unwrap, page actions skip the router, --page flag.
- Docs: D61, §9.9 as-built facts, removed the duplicate line in the Phase 3 brief.

## 2026-09-14 — AEC plumbing (flag off)
- zoya/aec.py, tests/evals/aec_replay.py, livekit + pyobjc CoreAudio pins, mixer reference feed; AEC_ENABLED=False (D62 in progress)

## 2026-09-14 — Phase 4 AWS resources
- zoya-memory table (pk/sk), zoya-alerts SNS topic + owner email subscription, geo-places permissions for zoya-app (infra/iam/zoya-app-policy.json).

## 2026-09-14 — Learning doc: Phase 3
- learning/learning.md: Phase 3 safety gate section.

## 2026-09-14 — Phase 5 computer use
- zoya/tools/computer.py, ax.py, documents.py, agents/computer_agent.py, screen_describer.py, screen.py display capture; safety registry + native/permission guards; tests/test_coords.py, test_computer_safety.py; screen benchmark --zoya; D63.

## 2026-09-14 — D62 echo-cancellation barge-in
- DECISIONS D62: AEC in front of Whisper rejected with replay numbers; barge-in detector design, wake-over-music replay, onsets/min; AEC_ENABLED stays False pending owner stop clips + live run

## 2026-09-14 — Phase 4 browser, shopping, memory, harness
- zoya/harness.py + zoya/skills/{youtube,spotify_web,shopping,media,notes,weather,memory}: skills directory, trigger index, learned picks, skill-scoped brain, direct actions (D65).
- zoya/tools/web.py (TinyFish, D64), memory.py (secret filter, Supermemory + local + DynamoDB), places.py (Amazon Location v2), handoff.py (Flow 10 + SNS), cache.py; browser.py launch switches + guarded recipe helpers (D66).
- safety: Phase 4 registry, YouTube final buttons, Amazon Add to Cart allowlist, row-bound struck-price rule; earcons progress-step/add-to-cart/purchase/checkpoint/blocked; --login, --order-limit.
- tests/test_memory_filter.py, tests/test_harness.py, tests/evals/phase4_live.py, phase4_gate_replay.py; docs §9.7/§9.8/§9.12 as built.

## 2026-09-14 — Phase 6: multitasking, document agent, reminders
- zoya/tasks.py Task Manager; task-bound confirmations in safety.py (D61 extended, D67); voice controls (named stop, what's running, queue it).
- document_agent (as_tool delegate) + office/share tools; set_reminder (EventBridge Scheduler → SNS, no Lambda); earcons queued/complete.
- Tests: tests/test_tasks.py, tests/test_office_reminders.py; eval tests/evals/multitask_replay.py (3/3 pass). Docs: D67, STACK §8 row.

## 2026-09-14 — Phase 6 review fixes
- Formula-looking spreadsheet text stored as text (xlsx) / apostrophe-prefixed (csv); outside-task confirmations refused while any task runs; reminder caps (5 per command, 20 active).

## 2026-09-14 — Phase 6 AWS resources + managed IAM policy (D68)
- Created zoya-reminders schedule group, zoya-scheduler-sns role, zoya-shared bucket, zoya-shares topic; moved zoya-app to a managed policy (inline 2,048-byte limit).

## 2026-09-14 — Phase 7: stage overlay, action ring, CloudWatch dashboard spec
- zoya/overlay.py + overlay_app.py (child-process NSPanel: presence states, masked captions, ring); screen.display_filter excludes the overlay in every display capture; aws.traced span per AWS call; infra/cloudwatch/zoya-stage-dashboard.json; zoya-app policy +xray:PutSpans/PutSpansForIndexing; tests/test_overlay.py, tests/evals/overlay_check.py; D69, §9.11 as built.

## 2026-09-14 — Barge-in enabled
- AEC_ENABLED=True after the owner stop-clip replay (6->8/10) and wake-over-music replay (13->16/21); D62 updated; live run pending

## 2026-09-14 — Phase 7 AWS + sister share subscription
- zoya-app managed policy v2 (X-Ray spans), zoya-stage dashboard, Transaction Search (logs resource policy + X-Ray → CloudWatch Logs), sister email subscribed to zoya-shares with recipient filter (pending her confirm).

## 2026-09-14 — Sharing to sister enabled
- SHARE_CONTACTS=("sister",) after her zoya-shares email subscription was confirmed.

## 2026-09-15 — D62 live run recorded
- Owner live laptop-speaker run results in D62; OnsetDetector skips the empty first block (numpy empty-mean warning)

## 2026-09-15 — Zoya website brief
- docs/website/BRIEF.md: one-page GTM site brief (blind-first, waitlist, blue orb, Next.js); builder session launched.

## 2026-09-15 — Waitlist database for the Zoya website
- Created Neon project zoya-waitlist (empty-firefly-95814779, aws-ap-southeast-1, personal org) with table waitlist(email pk, created_at); owner chose Neon for Vercel deploy. DATABASE_URL goes to Vercel env only, never committed.

## 2026-09-15 — Vercel project for the Zoya website
- Created Vercel project zoya (team aankir101-5169s-projects), enabled Web Analytics, added DATABASE_URL (production) from the Neon zoya-waitlist DB. Owner asked for a Vercel deploy + analytics + visitor count.

## 2026-09-15 — Zoya website moved to the right Vercel account
- Created Vercel project zoya in team aankirzs-projects, connected to GitHub Aankirz/zoya (production branch main, root directory site, Next.js), Web Analytics on, DATABASE_URL (production) set, ignored build step skips deploys when site/ is unchanged.
- Rotated the Neon neondb_owner password so the copy left in the unused aankir101-5169 project is dead (owner chose to keep that project). Nothing was ever deployed there.

## 2026-09-15 — Zoya one-page website built in site/
- Next.js 16 App Router site per docs/website/BRIEF.md: hero (h1, value line, real Polly Kajal "Hear Zoya" clip with word-synced transcript, waitlist), promises, transformation, things you can say, FAQ, closing waitlist, footer with contact and visitor count.
- Waitlist + unique visitor count on Neon via DATABASE_URL (lib/waitlist.ts, lib/visitors.ts), jsonl fallback in local dev, honeypot + best-effort in-memory rate limit, Vercel Analytics only on Vercel.
- Verified: axe 0 violations (AA + AAA contrast, both themes), Lighthouse mobile 99/100/100/100, no overflow at 320/375/768/1440 or 200% zoom, reduced motion stops the orb.

## 2026-09-15 — Vercel ignored-build step fixed
- The first Git deploy (a10ab09) was cancelled: the ignore step compared only HEAD^..HEAD, and the last pushed commit touched docs only. Now it compares against VERCEL_GIT_PREVIOUS_SHA and always builds when there is none. Re-triggered production from main via the Vercel API.

## 2026-09-15 — Website redesign brief v2
- docs/website/BRIEF-v2.md: owner rejected the split layout, the gradient orb and the scripted examples. The new direction is centered and heyliki.com-inspired (near-black, cream line art, script greeting, mono meta, a real Zoya voice greeting), sent to the builder.

## 2026-09-15 — Zoya website v2 redesign (BRIEF-v2)
- Rebuilt site/ as one centered column with heyliki's components: pill nav, script "Zoya" h1, outlined chip, intro, mono line, clickable cream line-art of Zoya that speaks a real Polly Kajal greeting with a speech bubble, cream waitlist button, numbered ruled promise rows, hairline mono footer with the visitor counter.
- Removed the orb and every radial gradient/blur, the grocery clip and transcript, the transformation band, "things you can say", the FAQ and the duplicate form.
- Verified: axe 0 violations (AA and AAA contrast, dark and light), Lighthouse mobile 98/100/100/100, no overflow at 320/375/768/1440 or 200% zoom, character fits the first screen at 1280×800, bubble clear of every stroke.

## 2026-09-15 — Website brief v3 (heyclicky, light)
- docs/website/BRIEF-v3.md: owner confirmed heyclicky.com as the reference, in a light theme only, centered, with illustrated props (no videos), no founder note, and glossy pills allowed; sent to the builder.

## 2026-09-15 — Zoya website v3 (heyclicky style, BRIEF-v3)
- Rebuilt site/ in heyclicky's DNA with our own drawn assets, light only and centered: macOS menu bar with an animated Zoya mark, dotted desktop hero with SVG props (notes and Finder windows, folders, trash, "hello my name is" sticker, kaomoji) around "zoya", the subline and the waitlist, a big "hello" Mac window that plays Zoya's real Polly Kajal greeting with waveform dots and a typing glossy bubble, three stacked promise rows with typing bubbles (confirm / done / zoya, stop), white FAQ rows, and a footer "zoya" built from drawn folders with the visitor counter and contact.
- Inter replaces Atkinson (owner: exactly like heyclicky); greys darkened to >= 7:1. Removed the v2 script name, chip, line art and dark theme.
- Verified: axe 0 violations incl. AAA contrast, Lighthouse mobile 99/100/100/100, no overflow at 320/375/390/768/1440 or 200% zoom, reduced motion honoured, clean-clone build.

## 2026-09-15 — Website v3 deployed
- Pushed main@775b1b6 (heyclicky-style light centered site); Vercel production READY at https://zoya-indol.vercel.app. Live checks: no secrets or personal data beyond the approved contact email, no third-party origins, waitlist GET 405 / POST validates, voice clip and analytics 200.

## 2026-09-15 — Rune Icons on the Zoya website
- Added 12 Rune Icons (Nexvyn, Apache-2.0) as inline components in site/app/icons/rune.tsx: glass folder, trash, notes and microphone for the desktop props and hello window; outline eye, plus, play, stop, wifi and battery for UI; two pixelated accents (ear, message) in the desktop hero. Glass ids are namespaced per instance.
- Added site/THIRD_PARTY_NOTICES.md with the Apache-2.0 text and a footer credit "icons by rune icons". axe 0 (incl. AAA), no overflow at 320–1440 and 200% zoom, build clean.

## 2026-09-15 — Rune Icons live on the website
- Pushed main@fdcfe5b (Rune Icons, Apache-2.0, inline SVG + THIRD_PARTY_NOTICES + footer credit); Vercel production READY. Live checks pass; the only external reference is the credit link.

## 2026-09-15 — Website: no hackathon credit, two promises
- Owner change: removed the "built for the vision os hackathon" footer line (the only such mention in site/) and the "stop means stop" promise row. The promises are now "confirm" and "done"; the hello window's "stop" control is unchanged.

## 2026-09-15 — Website: show real abilities (owner)
- Owner: remove hackathon mentions and the stop promise; replace the generic hero windows and promises with drawn Amazon / Spotify / presentation windows and a "what zoya does" section (real shipped abilities, no invented prices or songs). Sent to the builder.
