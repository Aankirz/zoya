# Zoya capability harness — research report (2026-09-14)

> Requested by the owner after Phase 2 ("a skill prepared for it in Zoya's harness. Kind of directory… proper end-to-end actions"; "low token consumption… faster. Caching"; "Skill directories, MCP directories, actions, and all"). Strands-first per the owner (coordinator). Research only; nothing is built. The coordinator decides which phase it goes in. Key Strands claims were spot-checked by the Phase 2 builder against the installed source (`vended_plugins/skills/skill.py` allowed-tools parsing, `tools/_caller.py` "cannot raise interrupt in direct tool call", `models/openai.py` cache_key mapping).

Scope: how to make Zoya find the right capability, finish tasks end to end, and do it fast with few tokens. Built on **Strands primitives first** (strands-agents 1.55.1, strands-agents-tools 0.8.8, as installed in `.venv`). "SRC" = `.venv/lib/python3.12/site-packages/`. **[UNVERIFIED]** marks claims I could not confirm in docs or source.

## 1. Strands feature audit (docs + installed source)

| Feature | What 1.55.1 actually provides | Doc URL | Source |
|---|---|---|---|
| Tools / ToolRegistry | `@tool`, `registry.register_dynamic_tool()`, `replace()`, `reload_tool()`. `Agent(load_tools_from_directory=True)` hot-reloads `./tools/` (watchdog `ToolWatcher`). **Direct deterministic call** `agent.tool.<name>(**kw)` needs no model call, but still runs through `ToolExecutor._stream`, so hooks fire. | https://strandsagents.com/docs/user-guide/concepts/tools/ | SRC/strands/tools/registry.py:289,360,561; tools/watcher.py:19; tools/_caller.py (acall → ToolExecutor._stream) |
| Concurrent tools | `ConcurrentToolExecutor` / `SequentialToolExecutor` via `Agent(tool_executor=…)` | …/concepts/tools/executors/ | SRC/strands/tools/executors/concurrent.py:19 |
| Hooks (permission layer) | `BeforeToolCallEvent` (can change `tool_use` or `selected_tool`, set `cancel_tool`, `interrupt()`), `BeforeToolsEvent`, `Before/AfterModelCallEvent`, `BeforeInvocationEvent` | …/concepts/agents/hooks/ , …/concepts/interrupts/ | SRC/strands/hooks/events.py:137,208 |
| Interventions (newer, higher-level) | `InterventionHandler` returns `Proceed / Deny / Guide / Confirm / Transform`. `Confirm` works only on beforeToolCall. Vended `hitl` handler (optional LLM risk classifier) and `cedar` policy authorization. | …/concepts/agents/interventions/human-in-the-loop/ | SRC/strands/interventions/actions.py:89; vended_interventions/hitl/hitl.py; vended_interventions/cedar/ |
| MCP client | `MCPClient(transport, tool_filters={"allowed":[str/regex],"rejected":[…]}, prefix=…)`. It is a ToolProvider you pass straight to `Agent(tools=[client])`. It also offers `call_tool_sync/async` for direct calls and config-file loading with `prefix_with_server_name`. | https://strandsagents.com/docs/user-guide/concepts/tools/mcp-tools/ | SRC/strands/tools/mcp/mcp_client.py:184-293,1009,1074 |
| Agents-as-tools | `agent.as_tool(name, description, preserve_context, delegate)`. `delegate=True` makes it the only call that turn, and the sub-agent's reply becomes the final answer (plugin `_agent_delegation.py`). | …/concepts/multi-agent/agents-as-tools/ | SRC/strands/agent/agent.py:1127; agent/_agent_delegation.py |
| Swarm / Graph / Workflow | `multiagent.Swarm`, `multiagent.GraphBuilder`/`Graph` (with `BeforeNodeCallEvent`, interruptible); `strands_tools.workflow` tool (task DAG with parallelism) | …/multi-agent/swarm/ , /graph/ , /workflow/ | SRC/strands/multiagent/swarm.py:266, graph.py:309,502; SRC/strands_tools/workflow.py:918 |
| Conversation / context | `SlidingWindowConversationManager` (default), `SummarizingConversationManager`, `context_manager="auto"/"agentic"` (auto summarises at 0.85 fill), `ContextOffloader` plugin. Sessions: File/S3/Snapshot session managers. | …/concepts/agents/conversation-management/ , …/concepts/context-management/ | SRC/strands/agent/conversation_manager/; session/ |
| Caching | `CacheConfig(strategy, ttl, system_prompt_ttl, cache_key, tools_ttl)`; `cachePoint` content blocks. **For OpenAI only `cache_key`→`prompt_cache_key` and `ttl` ∈ {"in_memory","24h"}→`prompt_cache_retention` are mapped; `cachePoint` is skipped with a warning.** Any `params` you pass are merged into the request last, so `prompt_cache_options` can be passed that way. | …/model-providers/openai/ [page not fetched] | SRC/strands/models/model.py:135; models/_openai_cache.py; models/openai.py:421,508-530 |
| Structured output | `Agent(structured_output_model=PydanticModel)` | …/concepts/agents/structured-output/ | SRC/strands/agent/agent.py:221 |
| Model routing | `ModelRouter` + `ClassifierStrategy` / `FallbackStrategy` (the docs call the API "provisional") | …/model-providers/model-routing/ | SRC/strands/models/routing/ |
| **Skills (official)** | `AgentSkills` plugin, following the Agent Skills spec. It injects `<available_skills>` (name, description, location) into the system prompt and adds a `skills(skill_name)` tool that returns the SKILL.md body plus a list of `scripts/ references/ assets/`. Sources can be a directory, a parent directory, HTTPS, or a `Skill(...)` object. `set_available_skills()` is applied before each invocation. It bundles **no** file or shell tools. `allowed_tools` is **only shown as text, not enforced**. | https://strandsagents.com/docs/user-guide/concepts/plugins/skills/ | SRC/strands/vended_plugins/skills/agent_skills.py:74,161,391-392; skill.py:241-247 |
| SOPs | `strands-agents/agent-sop` (Apache-2.0, pkg `strands-agents-sops`): Markdown SOPs with RFC-2119 MUST/SHOULD, parameters, and distribution "as MCP tools, Agent Skills, Python modules". This is guidance text, not a runtime. | https://github.com/strands-agents/agent-sop ; https://aws.amazon.com/blogs/opensource/introducing-strands-agent-sops-natural-language-workflows-for-ai-agents/ | not installed |
| Browser / computer | `strands_tools.browser` (LocalChromiumBrowser, AgentCoreBrowser) and `use_computer` | …/concepts/tools/community-tools-package/ | SRC/strands_tools/browser/ |
| Tool search / deferred loading | **None in Strands.** No `tool_search` or `defer_loading` anywhere in SRC/strands. | — | grep of SRC |

## 2. Options compared

| Option | What | Fit for Zoya | Latency / tokens | Dep / licence | Maturity | Source |
|---|---|---|---|---|---|---|
| Strands `AgentSkills` | Lazy SKILL.md loading | High. Native, and already installed | Adds ~1 extra model round-trip when the model activates a skill; the menu costs ~30–60 tok per skill | Apache-2.0 | GA plugin in 1.55.1 | above |
| Anthropic Agent Skills spec | name+description upfront, body on demand, scripts run without loading | This is the format to adopt | "effectively unbounded" bundled context | open spec | Adopted by Claude Code, Codex, Strands | https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills ; https://developers.openai.com/codex/skills |
| Strands `agent.tool.X()` direct calls | Deterministic action, 0 LLM calls | Core of the action layer | ~0 tok. Local latency only | built-in | GA | tools/_caller.py |
| Strands `MCPClient` + `tool_filters` | Mount MCP servers, expose only a few tools | High for Apple apps and the browser | Each exposed tool schema sits in the prefix | built-in | GA | mcp-tools doc |
| OpenAI hosted `tool_search` + `defer_loading`/namespaces | Server-side lazy tool loading, designed to keep the cache | Low now: **Responses API only**, and Strands `OpenAIModel` uses Chat Completions | Saves schema tokens once there are many tools | OpenAI | GA for gpt-5.4+ | https://developers.openai.com/api/docs/guides/tools-tool-search |
| Anthropic Tool Search Tool | Same idea for Claude | N/A (Zoya uses OpenAI). Evidence only | 85% fewer tool-definition tokens (77K→8.7K); Opus 4 accuracy 49%→74%. Costs an extra search step. | Anthropic | GA | https://www.anthropic.com/engineering/advanced-tool-use |
| Microsoft Playwright MCP | Browser via accessibility snapshots; `--user-data-dir`, `--extension`, `--isolated` | Medium. Good fallback explorer, but verbose snapshots | Heavy per step | Apache-2.0, 37k★, pushed 2026-09-11 | Mature | https://github.com/microsoft/playwright-mcp |
| Playwright Python scripted flows | Hand-written selectors per site | High for top tasks (YouTube, Spotify web) | 0 tok on replay | Apache-2.0 | Mature | playwright.dev |
| browser-use / workflow-use | Record → deterministic workflow, falls back to agent | Idea only. workflow-use says "don't use in production" | 0 tok on replay | MIT / **AGPL-3.0** | Early | https://github.com/browser-use/workflow-use |
| Stagehand cache | Caches act/observe/extract, self-heals | Pattern only. **Cache needs a Browserbase cloud browser**, so it conflicts with the local-only rule | 0 tok on hit | MIT | Mature | https://docs.stagehand.dev/v4/best-practices/caching |
| Skyvern code cache | Generated Playwright code cached | Pattern only. Vendor claims "skip the LLM entirely — 3–5× faster, up to 70% cheaper" | — | AGPL-3.0 | Mature | https://www.skyvern.com/products |
| Agent Workflow Memory | Induce reusable workflows from past runs | Pattern for recorded flows (Phase 6) | +24.6% / +51.1% relative success (Mind2Web / WebArena), fewer steps | Apache-2.0 code | Research (ICML'25) | https://arxiv.org/abs/2409.07429 |
| Apple Shortcuts CLI | `shortcuts run "Name" -i in -o out` | High. Gives access to App Intents with no LLM | 0 tok | macOS built-in | GA | https://support.apple.com/guide/shortcuts-mac/run-shortcuts-from-the-command-line-apd455c82f02/mac |
| FradSer/mcp-server-apple-events | Reminders + Calendar via EventKit | Good (Phase 4+) | small schemas | MIT, pushed 2026-08-26 | Active | https://github.com/FradSer/mcp-server-apple-events |
| supermemoryai/apple-mcp | Notes/Mail/etc. | **Archived** — avoid | — | MIT | Dead | GitHub API |
| steipete/macos-automator-mcp | AppleScript/JXA recipe library | Reference only (**archived**) | — | MIT | Archived | GitHub API |
| Spotify MCP (marcelmarais) | Web API playback + search | Weak: the Feb-2026 rules require Premium, cap dev apps at 5 users, and limit search to 10 results. The repo shows no detected licence. | small | licence **unclear** | Active | https://developer.spotify.com/documentation/web-api/tutorials/february-2026-migration-guide |
| YouTube MCP (ZubeidHendricks) | Data API search and transcripts | Low. A URL template is enough | small | MIT | Active | https://github.com/ZubeidHendricks/youtube-mcp-server |
| Registries: official MCP Registry, Docker MCP Catalog (300+ verified images) | Directories | For discovery **at build time only**. Never auto-install at runtime. | — | — | Registry in preview since 2025-09 | https://registry.modelcontextprotocol.io ; https://docs.docker.com/ai/mcp-catalog-and-toolkit/ |
| LiveKit `update_tools()` / Pipecat `register_function` | Voice frameworks that swap tool sets per state | Confirms the "small, per-state tool set" pattern | — | Apache-2.0 / BSD-2 | Mature | https://docs.livekit.io/agents/logic/tools/definition/ ; https://docs.pipecat.ai/pipecat/learn/function-calling |

## 3. Recommended harness (3 layers)

### Layout
```
zoya/skills/
  youtube/
    SKILL.md        # frontmatter: name, description (≤1 line), metadata.triggers (regex), metadata.risk
    actions.py      # @tool deterministic actions: open_channel(query), search(query), play_first_result()
    flows/          # recorded Playwright steps (JSON), Phase 4+
  spotify_web/  apple_notes/  reminders/  weather/  media/  shopping/ (Phase 4)
zoya/harness/
  catalog.py        # scans skills/ once: builds trigger index + compact menu + registry of action tools
  dispatch.py       # rules → trigger → luna pick → action | brain fallback
  gate.py           # Strands InterventionHandler (Phase 3)
  mcp.py            # MCPClient instances with tool_filters (Phase 4)
```

### Layer 1 — deterministic actions (0 model calls)
- Each `actions.py` exposes Strands `@tool` functions. Register all of them in one long-lived "actions" `Agent` and invoke them with `agent.tool.<name>(**slots, record_direct_tool_call=False)`. This keeps hooks and interventions on the path with no LLM (tools/_caller.py).
- Recipes, cheapest first: URL templates (`https://www.youtube.com/results?search_query=<q>`; a channel URL `youtube.com/@handle` works only if the handle is known — handles are official per https://support.google.com/youtube/answer/11585688, but mapping "MrBeast"→`@MrBeast` is a guess, so search first, then click the top channel result); `open.spotify.com/search/<q>` followed by a scripted Play click **[UNVERIFIED selector stability]**; AppleScript/`osascript`; `shortcuts run`.
- The two failing demo tasks become one recipe each: `youtube.open_channel("MrBeast")` and `spotify_web.play("song")`, each with a Playwright script and a spoken result.

### Layer 2 — skills directory with lazy loading (0–1 cheap call)
Dispatch order:
1. Existing regex rules (router.py `match_rules`) → fast tools (unchanged).
2. **Trigger index**: `metadata.triggers` regexes from every SKILL.md, compiled at start. Match plus slot capture → Layer 1 action. 0 model calls.
3. **One luna call** with `structured_output_model=SkillPick{skill, action, slots, confidence}`. Its system prompt is the static catalogue (name + one line + action signatures). Kept byte-identical and ≥1,024 tokens, it is cached. If confidence is high → Layer 1.
4. Otherwise build the **brain** Agent (terra) with `AgentSkills(skills=[picked skill dir])` (or a `Skill(...)` object whose instructions already contain the body, which avoids the extra `skills()` round-trip). Give it the skill's own action tools plus generic fallback tools (browser, narrate). If nothing was picked, pass the whole `skills/` directory and let the model call `skills()`.
- Because `allowed_tools` is not enforced by Strands, Zoya must pass the tool list itself (custom).

### Layer 3 — MCP / tool discovery
- Mount MCP servers via `MCPClient(..., tool_filters={"allowed":[...]}, prefix="rem")`. Each server belongs to exactly one skill, so its tools are exposed only when that skill is active. That is the discovery step: skill pick = tool pick.
- Strands has no tool search. At Zoya's size (<50 tools) the skill → tool-subset split does the same job, in the way LiveKit's `update_tools` does. Revisit OpenAI hosted `tool_search` only if Zoya moves to `OpenAIResponsesModel` (present in SRC/strands/models/openai_responses.py; its tool_search passthrough is **[UNVERIFIED]**).
- Registries (official MCP Registry, Docker catalog) are for the developer to vet servers. Pin versions. Never install from a registry at runtime.

### Mapping: layer → Strands feature → custom work
| Layer | Strands feature used | Must be custom |
|---|---|---|
| Deterministic actions | `@tool`, `ToolRegistry`, `agent.tool.X()` direct call, `ConcurrentToolExecutor` | URL/AppleScript/Playwright recipes, slot extraction, spoken results |
| Skills directory | `AgentSkills`, `Skill`, `set_available_skills`, `structured_output_model` (pick) | Trigger-regex index (`metadata.triggers`), per-skill tool scoping (`allowed_tools` not enforced), catalogue builder |
| Tool discovery | `MCPClient` + `tool_filters`/`prefix`, `agent.as_tool(delegate=True)` for heavy sub-agents (shopping) | Skill→MCP binding; no tool search exists |
| Safety gate | `InterventionHandler` → `Confirm`/`Deny`, `BeforeToolCallEvent.interrupt()`, Graph `BeforeNodeCallEvent` | Confirmation tokens, voice "yes/stop" capture, risk metadata per action |
| Caching | `CacheConfig(cache_key=…)`, `params` passthrough, `SlidingWindowConversationManager` | Stable prefix builder, result TTL cache, flow store |
| Multitasking (P6) | `Swarm`/`Graph`, `strands_tools.workflow`, `background_tasks` module [not studied] | Scheduling and earcons |

## 4. Caching plan

**Prompt prefix (OpenAI).** Sources: https://developers.openai.com/api/docs/guides/prompt-caching and https://developers.openai.com/cookbook/examples/prompt_caching_201
- GPT-5.6+: minimum 1,024 visible tokens. Cache **write costs 1.25×** input and **read costs 0.1×**. TTL is set with `prompt_cache_options.ttl` (only "30m", lasting ≥30 min after last use). Implicit breakpoint at the end of the latest user message. Explicit `prompt_cache_breakpoint` on content parts, up to 4 writes. The Chat Completions reference lists `prompt_cache_options` as "supported for gpt-5.6 and later" (https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create/).
- Strands gap: `CacheConfig.ttl` maps only to `prompt_cache_retention` ("in_memory"/"24h"), which is not the GPT-5.6 control. Pass `params={"prompt_cache_options": {...}, "prompt_cache_key": "zoya-brain-v1"}` directly. Explicit breakpoints would need a custom `OpenAIModel.format_request_messages` override **[UNVERIFIED that it's needed; implicit may suffice]**.
- Order: static persona and rules → skill catalogue → tools (the tools array is part of the prefix; keep names, order and schemas byte-stable) → dynamic content (time, 6 prior turns, request) **last**. Put no timestamps in the system prompt.
- Per-skill agents: each distinct (tools + system prompt) is its own cache entry. Keep one stable prompt per skill and warm it at startup.
- Expected: "TTFT up to 80% and input cost up to 90%". The cookbook measured only **7% faster TTFT at 1,024-token prompts** and 67% at 150k. For Zoya's short prompts the win is mainly cost, not speed. Latency comes from *skipping model calls*.
- Responses API has "40–80% better cache utilization" than Chat Completions, but that is due to persisted reasoning. With `reasoning_effort="none"` that gain is likely small **[UNVERIFIED for Zoya]**. It also conflicts with `store=false` unless you use encrypted reasoning items.
- Cookbook tip: `tool_choice: {"type":"allowed_tools"}` limits tools per turn without changing the prefix. Whether it passes through Strands `params` (merged after `tool_choice`) is **[UNVERIFIED]**.

**Results cache.** An in-process TTL dict keyed by (action, normalised slots): weather 10 min, time none, "what's playing" 5 s, resolved YouTube handle→URL 7 days, Spotify track→URL 7 days. **Never cache** anything that touches money, send or delete.

**Recorded flows.** After a brain-fallback success, save the tool-call trace (Strands `AfterToolCallEvent` hook) as `skills/<skill>/flows/<intent>.json` with parameterised slots. Replay it through Layer 1. On a selector failure, fall back to the brain with the flow as a hint (the AWM / workflow-use / Stagehand self-heal pattern). A human approves a flow before it becomes a trigger. Repeated tasks then cost 0 tokens (Skyvern vendor claim: 3–5× faster; AWM: fewer steps plus higher success).

## 5. Phased rollout
- **Now (before Phase 3, ~1–2 days):** Build `skills/` with youtube, spotify_web, media, notes and weather. Add the trigger index and direct `agent.tool` dispatch. Fix the two demo failures as recipes. Add a luna `SkillPick` structured call. Make the prompt prefix stable and pass `prompt_cache_key` / `prompt_cache_options` through `params`. Log per-layer latency. Measure the hit rate of layers 1–3 against the fallback.
- **Phase 3 (safety gate):** Implement the gate as an `InterventionHandler` (`Confirm` on `before_tool_call`) driven by per-action `risk` metadata in SKILL.md. Because direct calls **cannot raise interrupts** (`_caller.py`: "cannot raise interrupt in direct tool call"), Layer 1 must check the confirmation token *before* calling `agent.tool.X()`, or the handler must `Deny`. "Stop" and earcons stay outside the harness.
- **Phase 4 (browser, shopping, memory):** Add Playwright scripted flows for the dedicated Chrome profile. Add Playwright MCP (filtered to about 6 tools) only as the fallback explorer. Add the shopping skill as `agent.as_tool(delegate=True)`. Add MCPClient for Reminders/Calendar (FradSer). Start recording flows.
- **Phase 5 (computer use):** Add a computer-use skill with Shortcuts (`shortcuts run`) and AppleScript actions first; screen-level control is the last resort.
- **Phase 6 (multitasking):** Run independent recipes with `ConcurrentToolExecutor`/`Graph` and promote recorded flows.

## 6. Risks
- **Safety gate bypass:** direct tool calls skip interrupts (verified). MCP tools and recorded flows must carry risk metadata. By default an unknown MCP tool counts as high risk and needs `Confirm`.
- **Prompt injection:** web pages and accessibility snapshots, MCP tool *descriptions* ("tool poisoning", https://invariantlabs.ai/blog/mcp-security-notification-tool-poisoning-attacks), and third-party SKILL.md files (Anthropic advises auditing skills). Mitigations: vendor-pin MCP servers; review their tool descriptions; wrap page text as untrusted data; allow no side-effect action based only on page text without a gate; never load skills from HTTPS at runtime.
- **Privacy:** `store=False` must also hold for any `OpenAIResponsesModel` or luna calls. Note that Stagehand's cache and Docker/remote MCPs send data off-machine.
- **Brittleness:** Spotify and YouTube DOM selectors break (self-heal fallback needed). Spotify Web API limits (Premium, 5 users) make the API/MCP route a poor fit.
- **Licences:** workflow-use and Skyvern are AGPL-3.0 (use as patterns, not dependencies). The Spotify MCP licence is unclear. apple-mcp and macos-automator-mcp are archived.
- **Strands churn:** the routing API is "provisional", and the skills plugin is new (Mar 2026). Pin 1.55.1.
- **Unverified:** stability of the Spotify Play selector; `allowed_tools` tool_choice passthrough; the benefit of explicit breakpoints versus implicit ones; `OpenAIResponsesModel` tool_search support; `background_tasks` module semantics; the Strands OpenAI provider doc page (not fetched). The extra round-trip for `skills()` activation is inferred from the design, not measured.
