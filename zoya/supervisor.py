from __future__ import annotations

import os
import signal
import subprocess
import sys
import time

from zoya.crash import RESTARTED_ENV, SUPERVISED_ENV, say_directly

MAX_CRASHES = 3
CRASH_WINDOW_S = 10 * 60
EXIT_CANNOT_START = 3
GAVE_UP = (
    f"I've stopped unexpectedly {MAX_CRASHES} times in {CRASH_WINDOW_S // 60} minutes, "
    "so I won't restart again. Start me again later. If it keeps happening, "
    "start me and say: Zoya, send a problem report."
)


def should_restart(crash_times: list[float], now: float) -> bool:
    recent = [at for at in crash_times if now - at < CRASH_WINDOW_S]
    return len(recent) < MAX_CRASHES


def run(command: list[str]) -> int:
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    signal.signal(signal.SIGHUP, signal.SIG_IGN)
    crashes: list[float] = []
    restarted = False
    while True:
        env = {**os.environ, SUPERVISED_ENV: "1"}
        if restarted:
            env[RESTARTED_ENV] = "1"
        child = subprocess.Popen(command, env=env)
        signal.signal(signal.SIGTERM, lambda *_, child=child: child.terminate())
        code = child.wait()
        if code in (0, EXIT_CANNOT_START):
            return code
        crashes.append(time.monotonic())
        print(f"Zoya exited with code {code}.", flush=True)
        if not should_restart(crashes, time.monotonic()):
            print(GAVE_UP, flush=True)
            say_directly(GAVE_UP)
            return code
        restarted = True


def main() -> int:
    return run([sys.executable, "-m", "zoya.main", *sys.argv[1:]])


if __name__ == "__main__":
    sys.exit(main())
