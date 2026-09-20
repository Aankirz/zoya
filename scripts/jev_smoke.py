"""Smoke-test the TypeSafe (Jev) key: one Noul question, printed with latency.

Run: python scripts/jev_smoke.py
Docs: https://docs.typesafe.ai/introduction/quickstart
"""

import os
import time

from dotenv import load_dotenv
from typesafe_sdk import Noul, TypeSafeClient

UTTERANCE = "Zoya, stop."


def main() -> None:
    load_dotenv()
    if not os.getenv("TYPESAFE_API_KEY"):
        raise SystemExit("TYPESAFE_API_KEY missing — add it to .env (see .env.example).")

    client = TypeSafeClient()
    started = time.perf_counter()
    response = client.system_one(
        state=UTTERANCE,
        questions={
            "is_stop": Noul(instructions="The speaker is telling the assistant to stop."),
        },
        model=os.getenv("JEV_MODEL") or None,
    )
    elapsed_ms = (time.perf_counter() - started) * 1000
    print(f"is_stop={response.answers['is_stop'].noul:.3f}  {elapsed_ms:.0f} ms")


if __name__ == "__main__":
    main()
