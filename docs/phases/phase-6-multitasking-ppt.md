# Phase 6 — Multitasking + document agent (36–41h)

> Read [`AGENTS.md`](../../AGENTS.md) and [`docs/STACK.md`](../STACK.md) first (STACK overrides the technical doc for models/voice/AWS). Section numbers (§) refer to [`docs/ZOYA_TECHNICAL_DOC.md`](../ZOYA_TECHNICAL_DOC.md).
>
> **Branch:** `phase-6-multitasking-ppt` · **Depends on:** previous phase approved

**Files this phase creates:**
- `zoya/tasks.py`
- `zoya/agents/document_agent.py`, `zoya/tools/reminders.py`

**Goal:** the user assigns long tasks and keeps using the Mac by voice while they run.

**Build**
- Task Manager (§9.13): registry, resource classes (background / browser / GUI), max 3 tasks, one orchestrator instance per task.
- Voice tools: `list_tasks`, `stop_task(name|"all")`, `task_status(name)`, task-named `answer_confirmation` (§9.2).
- Announcement queue: never talk over the user; always name the task; one pending confirmation at a time.
- GUI-task pause/resume when the user issues a foreground command.
- `document_agent` (STACK §9): creates **Word (.docx, python-docx), Excel (.xlsx with formulas, openpyxl), slides (.pptx, python-pptx), PDF (reportlab), CSV/Markdown** in `~/Documents/Zoya/`; opens the file by bundle id; reads back structure (title/sections, columns/rows/totals); "read section N" / "read row N"; edits on request. Optional share: upload to S3 + pre-signed link via SNS email.
- **Reminders (STACK §8):** EventBridge Scheduler + Lambda → SNS email and a spoken reminder.
- Earcons: `queued`, `complete`.
- **Harness, multi-agent layer** ([`docs/research/harness.md`](../research/harness.md), Strands-first): use Strands multi-agent primitives (agents-as-tools `as_tool(delegate=True)`, Swarm/Graph where they fit) instead of custom orchestration. Concurrent tasks can run skill recipes and recorded flows, and a flow that succeeds repeatedly gets promoted to a named skill. Verify each API in the strands 1.55.1 source and cite it.

**Not in this phase:** overlay, WhatsApp/email flows.

**Doc sections:** §6 Flows 7, 11 · §9.2, §9.5, §9.13, §11.2.

**Done when**
1. ☐ PPT task and grocery order run simultaneously; "open Mail and read my latest email" works meanwhile.
2. ☐ "What's running?" lists both with current steps.
3. ☐ "Stop the presentation" stops only that task.
4. ☐ Grocery confirmation waits until the user stops speaking and names the task.
5. ☐ "Make a 6-slide presentation…", "make a Word doc with my resume", "make an Excel sheet of my monthly expenses with a total" each produce a correct file that opens, and Zoya reads back its structure; "read row 3" works.
5b. ☐ "Send it to my sister" uploads to S3 and emails a working link via SNS.
5c. ☐ "Remind me in 2 minutes to drink water" fires a spoken reminder and an email.
6. ☐ 4th task → "queue it or stop one?" prompt.

**Judge demo (90 s):** start PPT → start grocery order → "open Mail, read my latest email" → "what's running?" → confirm the order → "Presentation: ready."
