"""Phase 1 text REPL: type a command, see route + tool + timing, hear Zoya.

Usage: python -m zoya
"""

from __future__ import annotations

import logging
import sys

from zoya.config import TIMING_LOG, load_env

EXIT_WORDS = {"quit", "exit", "bye"}


def _warm_up() -> None:
    """Load everything once so the first command is as fast as the rest (§13.3 #3)."""
    from zoya import aws
    from zoya.router import _router_model
    from zoya.tools import collect_tools

    collect_tools("zoya.tools", "zoya.agents")
    _router_model()
    aws.client("polly")


def _print_result(result) -> None:  # noqa: ANN001 — CommandResult, imported lazily
    decision = result.decision
    stages = " ".join(f"{name}={ms}" for name, ms in result.timings_ms.items())
    tool = f" tool={decision.tool}{decision.args}" if decision.tool else ""
    print(f"  route={decision.route} via={decision.source}{tool}")
    print(f"  timing: {stages}")
    print(f"  zoya: {result.spoken}")


def main() -> int:
    load_env()
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    # An expired `aws login` makes botocore log a full traceback on every call; zoya.aws
    # already logs one line with the reason.
    logging.getLogger("botocore.credentials").setLevel(logging.CRITICAL)

    from zoya import aws, speech
    from zoya.orchestrator import handle_command, setup_tracing

    print(f"keys: {aws.load_provider_secrets()}")
    print(f"tracing: {setup_tracing()}")
    _warm_up()
    print(f"timing log: {TIMING_LOG}\nType a command (quit to exit).")

    while True:
        try:
            line = input("zoya> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if line.lower() in EXIT_WORDS:
            break
        if line:
            _print_result(handle_command(line))
    speech.wait_until_quiet()
    return 0


if __name__ == "__main__":
    sys.exit(main())
