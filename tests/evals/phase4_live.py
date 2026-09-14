"""Phase 4 live checks through the real router, harness, brain, browser and web APIs (typed).

No mic. Each command goes through `orchestrator.handle_command`, like a spoken one after STT;
the timing record (route, source, skill, model_calls, tokens, stage ms) is printed and appended to
logs/timing.log. Speech is captured instead of played so parallel sessions aren't disturbed.
Needs the Zoya profile free, OPENAI/TINYFISH/SUPERMEMORY keys, AWS_PROFILE. An eval, not a pytest.

Usage: .venv/bin/python -u tests/evals/phase4_live.py "Open the MrBeast channel on YouTube" ...
"""

from __future__ import annotations

import os

os.environ["HF_HUB_OFFLINE"] = "1"

import faulthandler  # noqa: E402
import json  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402

from zoya import aws, speech  # noqa: E402
from zoya.config import load_env  # noqa: E402

HANG_DUMP_S = 120


def main(commands: list[str]) -> int:
    faulthandler.dump_traceback_later(HANG_DUMP_S, repeat=True)  # a hang prints every stack
    load_env()
    aws.load_provider_secrets()
    said: list[str] = []
    speech.narrate = said.append  # captured, not played
    from zoya import orchestrator

    for command in commands:
        said.clear()
        started = time.monotonic()
        result = orchestrator.handle_command(command)
        print(f"\n> {command}  ({time.monotonic() - started:.1f} s)")
        print(json.dumps(result.timings_ms))
        print(
            f"  route={result.decision.route} source={result.decision.source} "
            f"skill={result.decision.skill} tool={result.decision.tool} ok={result.ok} "
            f"model_calls={orchestrator.model_calls(result)}"
        )
        print(f"  said: {' | '.join(s for s in said if s)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
