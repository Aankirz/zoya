"""P2 spike: can a small local model replace ROUTER_MODEL? Measured, not assumed.

Runs Zoya's own router model call (router.ask_router_model → decision_from_choice) on the 38
non-stop utterances of tests/evals/router_eval.py, scored with that eval's score(), once against
the current ROUTER_MODEL through the relay and once against a local model served by
`mlx_lm.server` (OpenAI-compatible). Jev and the rules are skipped: this is the model alone.

Memory is read with Whisper large-v3-turbo loaded in this process and Zoya's Chrome running,
as a real session would have them.

  ZOYA_LICENSE_KEY=... ZOYA_RELAY_URL=http://localhost:8787 \
    .venv/bin/python scripts/spikes/router_local.py --local-url http://127.0.0.1:8090/v1 \
      --local-model <path of mlx-community/Qwen3.5-4B-MLX-4bit> --local-pid <server pid>
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tests" / "evals"))

from router_eval import UTTERANCES, score  # noqa: E402

from zoya import router  # noqa: E402
from zoya.config import LOG_DIR  # noqa: E402

P90 = 0.9
PAGE_BYTES = 16384
OUT = LOG_DIR / "router_local.json"
LOCAL_TIMEOUT_S = 30.0
LOCAL_MAX_TOKENS = 300


def _rss_mb(pid: int) -> float:
    result = subprocess.run(["ps", "-o", "rss=", "-p", str(pid)], capture_output=True, text=True)
    return int(result.stdout.strip() or 0) / 1024


def _system_memory() -> dict[str, Any]:
    vm = subprocess.run(["vm_stat"], capture_output=True, text=True).stdout
    pages = {
        line.split(":")[0]: int(line.split(":")[1].strip().rstrip("."))
        for line in vm.splitlines()[1:]
        if ":" in line
    }
    swap = subprocess.run(["sysctl", "-n", "vm.swapusage"], capture_output=True, text=True).stdout
    return {
        "free_mb": round(pages.get("Pages free", 0) * PAGE_BYTES / 2**20),
        "compressed_mb": round(pages.get("Pages occupied by compressor", 0) * PAGE_BYTES / 2**20),
        "swap": swap.strip(),
    }


def _chrome_rss_mb(pid: int) -> float:
    tree = subprocess.run(["ps", "-A", "-o", "pid=,ppid=,rss="], capture_output=True, text=True)
    rows = [tuple(int(v) for v in line.split()) for line in tree.stdout.splitlines()]
    pids = {pid}
    for _ in range(4):
        pids |= {p for p, parent, _rss in rows if parent in pids}
    return sum(rss for p, _parent, rss in rows if p in pids) / 1024


class LocalRouter:
    """The local model at its best: one forced tool call with Pydantic's own schema, not
    streamed. Through Strands and mlx_lm.server 0.31.3 the same model answered "[blank text]"
    every time (a list of text parts, then the nullable-type tool schema); see the P2 report."""

    def __init__(self, url: str, model: str) -> None:
        import openai

        self.client = openai.OpenAI(api_key="local", base_url=url, timeout=LOCAL_TIMEOUT_S)
        self.model = model
        self.tool = {
            "type": "function",
            "function": {
                "name": "RouteChoice",
                "description": "Route the command",
                "parameters": router.RouteChoice.model_json_schema(),
            },
        }

    def __call__(self, text: str) -> Any:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": router.router_prompt()},
                {"role": "user", "content": text},
            ],
            tools=[self.tool],
            tool_choice={"type": "function", "function": {"name": "RouteChoice"}},
            temperature=0,
            max_tokens=LOCAL_MAX_TOKENS,
        )
        calls = response.choices[0].message.tool_calls or []
        if not calls:
            raise ValueError("no tool call")
        return router.RouteChoice.model_validate_json(calls[0].function.arguments)


def _load_whisper() -> float:
    import mlx_whisper.load_models

    from zoya.config import STT_MODEL_REPO
    from zoya.setup_models import local_model_dir

    started = time.monotonic()
    mlx_whisper.load_models.load_model(local_model_dir(STT_MODEL_REPO))
    return time.monotonic() - started


def run(label: str, ask: Any) -> dict[str, Any]:
    rows = []
    for case in [c for c in UTTERANCES if c[1] != "stop"]:
        started = time.monotonic()
        try:
            decision = router.decision_from_choice(ask(case[0]))
            error = ""
        except Exception as failure:  # noqa: BLE001 — a failed call is a miss, recorded
            decision, error = router.RouteDecision("orchestrator", source="fallback"), repr(failure)
        latency = round((time.monotonic() - started) * 1000)
        rows.append(
            {
                "utterance": case[0],
                "correct": score(case, decision),
                "route": decision.route,
                "tool": decision.tool,
                "args": decision.args,
                "latency_ms": latency,
                "error": error[:200],
            }
        )
        print(label, rows[-1], flush=True)
    latencies = sorted(row["latency_ms"] for row in rows)
    return {
        "label": label,
        "correct": sum(row["correct"] for row in rows),
        "total": len(rows),
        "median_ms": statistics.median(latencies),
        "p90_ms": latencies[int(P90 * (len(latencies) - 1))],
        "misses": [row for row in rows if not row["correct"]],
    }


def main() -> int:
    from zoya.config import load_env
    from zoya.tools import browser

    parser = argparse.ArgumentParser()
    parser.add_argument("--local-url", required=True)
    parser.add_argument("--local-model", required=True)
    parser.add_argument("--local-pid", type=int, required=True)
    parser.add_argument("--local-only", action="store_true")
    args = parser.parse_args()
    load_env()
    whisper_s = _load_whisper()
    browser._chrome()
    chrome_pid = browser._state["chrome"].pid
    local = LocalRouter(args.local_url, args.local_model)
    results = [run("local", local)] if args.local_only else []
    results = results or [run("relay", router.ask_router_model), run("local", local)]
    memory = {
        "local_server_rss_mb": round(_rss_mb(args.local_pid)),
        "this_process_rss_mb_with_whisper": round(_rss_mb(os.getpid())),
        "whisper_load_s": round(whisper_s, 1),
        "zoya_chrome_rss_mb": round(_chrome_rss_mb(chrome_pid)) if chrome_pid else 0,
        "system": _system_memory(),
    }
    browser.close()
    report = {"router_model": os.environ.get("ROUTER_MODEL"), "results": results, "memory": memory}
    OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({**report, "results": [{**r, "misses": len(r["misses"])} for r in results]}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
