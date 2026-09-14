"""Phase 4 Done-when #10 (and the confirmation path of any skill) through the REAL safety gate.

Real: router (rules, triggers, router model), harness direct actions, brain when needed, Chrome on
the Zoya profile, `safety.require_confirmation` with a claimed voice channel and live-page summary.
Simulated: only the voice. `speech.say_and_wait` records the spoken summary instead of playing it,
and the user's answer is handed to the channel (`_VoiceChannel.reply`) after the echo window, as the
voice loop does. Real-voice checks stay with the owner (tests/evals/safety_replay.py covers audio).

Prints, per command: time to the confirmation question, the exact summary, the reply, whether a
confirmed click was logged, and the timing record. An eval, not a pytest.
Usage: .venv/bin/python -u tests/evals/phase4_gate_replay.py cancel "comment 'great video'"
"""

from __future__ import annotations

import os

os.environ["HF_HUB_OFFLINE"] = "1"

import faulthandler  # noqa: E402
import json  # noqa: E402
import sys  # noqa: E402
import threading  # noqa: E402
import time  # noqa: E402

from zoya import audio, aws, safety, speech  # noqa: E402
from zoya.config import ECHO_TAIL_S, TIMING_LOG, load_env  # noqa: E402

HANG_DUMP_S = 180
REPLY_AFTER_S = ECHO_TAIL_S + 0.3
ASK_WAIT_S = 120.0


def _answer(channel: safety._VoiceChannel, reply: str, asked: list[float]) -> None:
    deadline = time.monotonic() + ASK_WAIT_S
    while not safety.awaiting_reply() and time.monotonic() < deadline:
        time.sleep(0.05)
    if not safety.awaiting_reply():
        return
    asked.append(time.monotonic())
    time.sleep(REPLY_AFTER_S)
    channel.reply(reply, heard_from=time.monotonic())


def main(reply: str, commands: list[str]) -> int:
    faulthandler.dump_traceback_later(HANG_DUMP_S, repeat=True)
    load_env()
    aws.load_provider_secrets()
    spoken: list[str] = []
    speech.narrate = spoken.append
    speech.say_and_wait = lambda text, _timeout: spoken.append(f"[ASK] {text}") or True
    audio.earcon = lambda _kind: None
    channel = safety.claim_voice_channel()
    from zoya import orchestrator

    for command in commands:
        spoken.clear()
        before = TIMING_LOG.stat().st_size if TIMING_LOG.exists() else 0
        asked: list[float] = []
        threading.Thread(target=_answer, args=(channel, reply, asked), daemon=True).start()
        started = time.monotonic()
        result = orchestrator.handle_command(command)
        with TIMING_LOG.open(encoding="utf-8") as log:
            log.seek(before)
            events = [json.loads(line) for line in log if line.strip()]
        confirmed = [e for e in events if str(e.get("event", "")).endswith("confirmed")]
        ask_ms = round((asked[0] - started) * 1000) if asked else None
        print(f"\n> {command}  (reply {reply!r})")
        print(f"  command → question: {ask_ms} ms; confirmed clicks logged: {len(confirmed)}")
        print(f"  route={result.decision.route} source={result.decision.source} ok={result.ok}")
        print(f"  timings {json.dumps(result.timings_ms)}")
        print(f"  said: {' | '.join(spoken)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2:]))
