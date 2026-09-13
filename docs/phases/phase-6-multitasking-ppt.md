# Phase 6 — Multitasking + PPT subagent (36–41h)

> Section numbers (§) refer to [`docs/ZOYA_TECHNICAL_DOC.md`](../ZOYA_TECHNICAL_DOC.md). Read [`AGENTS.md`](../../AGENTS.md) before starting.
>
> **Branch:** `phase-6-multitasking-ppt` · **Depends on:** previous phase approved

**Files this phase creates:**
- `zoya/tasks.py`
- `zoya/agents/ppt_agent.py`

**Goal:** the user assigns long tasks and keeps using the Mac by voice while they run.

**Build**
- Task Manager (§9.13): registry, resource classes (background / browser / GUI), max 3 tasks, one orchestrator instance per task.
- Voice tools: `list_tasks`, `stop_task(name|"all")`, `task_status(name)`, task-named `answer_confirmation` (§9.2).
- Announcement queue: never talk over the user; always name the task; one pending confirmation at a time.
- GUI-task pause/resume when the user issues a foreground command.
- `ppt_agent` (§9.5): Sonnet 5 text-only content, `python-pptx`, text-only slides (Nova Canvas reaches end-of-life in Tokyo on 2026-09-30 — AUDIT A3), saves to `~/Documents/Zoya/`; "read slide N"; edits.
- Earcons: `queued`, `complete`.

**Not in this phase:** overlay, WhatsApp/email flows.

**Doc sections:** §6 Flows 7, 11 · §9.2, §9.5, §9.13, §11.2.

**Done when**
1. ☐ PPT task and grocery order run simultaneously; "open Mail and read my latest email" works meanwhile.
2. ☐ "What's running?" lists both with current steps.
3. ☐ "Stop the presentation" stops only that task.
4. ☐ Grocery confirmation waits until the user stops speaking and names the task.
5. ☐ Finished deck opens in Keynote/PowerPoint with 6 slides; "read slide 2" works.
6. ☐ 4th task → "queue it or stop one?" prompt.

**Judge demo (90 s):** start PPT → start grocery order → "open Mail, read my latest email" → "what's running?" → confirm the order → "Presentation: ready."
