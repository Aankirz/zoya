"""Would one Jev question help listen.judge on hands-free speech? (coordinator addendum to L1)

Asks Jev, through zoya.decisions.ask, "is this speech addressed to the assistant as a request?"
for every hands-free utterance in the simulator's dev and held-out scenarios, and compares it
with listen.judge and with what each scenario expects. Answers to Zoya's own question and
push-to-talk are left out: they are trusted and never reach Jev. Calls the network (Jev).

Usage: .venv/bin/python -u -m tests.evals.jev_addressed
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from typesafe_sdk import Noul

from tests.voice.scenarios import DEV, HELDOUT, Case
from zoya import decisions
from zoya.config import JEV_STOP_NOUL, load_env
from zoya.listen import Channel, judge

QUESTION = "The speaker is addressing a voice assistant with a request or a question for it."
STATE = "A voice assistant's microphone heard, right after its name or its last reply: {text!r}"
WAKE_ONLY = {"hey zoya", "zoya"}
RESULTS = Path(__file__).parent / "results" / "jev_addressed.json"
MS_PER_S = 1000


def hands_free(case: Case) -> list[tuple[str, bool]]:
    if case.stops or any(s.ptt and s.cue is not None for s in case.sounds):
        return []
    if any(s.text == "help me with something" for s in case.sounds):
        return []
    picked = []
    for sound in case.sounds:
        if sound.ptt or sound.text.lower().strip(",.!") in WAKE_ONLY:
            continue
        meant = any(want.lower() in sound.text.lower() for want in case.dispatched)
        picked.append((sound.text, meant))
    return picked


def ask_jev(text: str) -> tuple[float | None, int]:
    started = time.monotonic()
    answers = decisions.ask(STATE.format(text=text), {"addressed": Noul(instructions=QUESTION)})
    elapsed = round((time.monotonic() - started) * MS_PER_S)
    return (answers.noul("addressed") if answers else None), elapsed


def main() -> int:
    load_env()
    rows = []
    for group, cases in (("dev", DEV), ("heldout", HELDOUT)):
        for case in cases:
            for text, meant in hands_free(case):
                noul, ms = ask_jev(text)
                rules = judge(text, Channel.AFTER_WAKE).act
                jev = noul is not None and noul >= JEV_STOP_NOUL
                rows.append(
                    {
                        "set": group,
                        "text": text,
                        "meant": meant,
                        "rules": rules,
                        "jev": jev,
                        "noul": noul,
                        "ms": ms,
                    }
                )
    for group in ("dev", "heldout"):
        picked = [r for r in rows if r["set"] == group]
        for name in ("rules", "jev"):
            wrong = [r["text"] for r in picked if r[name] != r["meant"]]
            print(group, name, f"{len(picked) - len(wrong)}/{len(picked)} right", wrong)
    latencies = sorted(r["ms"] for r in rows)
    print("jev p50 ms", latencies[len(latencies) // 2])
    RESULTS.write_text(json.dumps(rows, indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
