from __future__ import annotations

import json
import os
import plistlib
import subprocess
import sys
import time
from pathlib import Path

from zoya.config import APP_BUNDLE, LOG_DIR
from zoya.crash import RESTARTED_ENV, SUPERVISED_ENV, say_directly
from zoya.supervisor import EXIT_CANNOT_START, GAVE_UP, should_restart

LABEL = "app.zoya.Zoya"
AGENT_ARG = "--agent"
ZOYA_ARGS = ("--overlay",)
THROTTLE_S = 5
ZOYA_HOME = Path.home() / ".zoya"
AGENT_PLIST = ZOYA_HOME / "launchd" / f"{LABEL}.plist"
RUN_MARKER = ZOYA_HOME / "running"
CRASH_LOG = ZOYA_HOME / "crashes.json"
AGENT_LOG = LOG_DIR / "launchd.log"
LAUNCHCTL_TIMEOUT_S = 10
TRANSLOCATED = "/AppTranslocation/"
MOVE_ME = (
    "I can't run from the folder I was downloaded to. Move Zoya into your Applications folder, "
    "then open me again from there."
)
NOT_BUNDLED = "zoya.app runs inside Zoya.app. From source, use ./start.sh."


def agent_plist(executable: Path) -> dict:
    return {
        "Label": LABEL,
        "ProgramArguments": [str(executable), AGENT_ARG, *ZOYA_ARGS],
        "KeepAlive": {"SuccessfulExit": False},
        "ThrottleInterval": THROTTLE_S,
        "ProcessType": "Interactive",
        "EnvironmentVariables": {SUPERVISED_ENV: "1"},
        "StandardOutPath": str(AGENT_LOG),
        "StandardErrorPath": str(AGENT_LOG),
    }


def _launchctl(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["launchctl", *args],
        capture_output=True,
        text=True,
        timeout=LAUNCHCTL_TIMEOUT_S,
        check=False,
    )


def _domain() -> str:
    return f"gui/{os.getuid()}"


def agent_running() -> bool:
    printed = _launchctl("print", f"{_domain()}/{LABEL}")
    return printed.returncode == 0 and "state = running" in printed.stdout


def open_hub() -> None:
    from Foundation import NSDistributedNotificationCenter

    from zoya.hub_bridge import OPEN_HUB_NOTICE

    NSDistributedNotificationCenter.defaultCenter().postNotificationName_object_userInfo_deliverImmediately_(
        OPEN_HUB_NOTICE, None, None, True
    )


def launch(executable: Path) -> int:
    if TRANSLOCATED in str(executable):
        say_directly(MOVE_ME)
        return 0
    if agent_running():
        open_hub()
        return 0
    CRASH_LOG.unlink(missing_ok=True)
    RUN_MARKER.unlink(missing_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    AGENT_PLIST.parent.mkdir(parents=True, exist_ok=True)
    AGENT_PLIST.write_bytes(plistlib.dumps(agent_plist(executable)))
    _launchctl("bootout", f"{_domain()}/{LABEL}")
    loaded = _launchctl("bootstrap", _domain(), str(AGENT_PLIST))
    if loaded.returncode != 0:
        print(f"launchctl bootstrap failed: {loaded.stderr.strip()}", file=sys.stderr)
    return loaded.returncode


def _crash_times() -> list[float]:
    try:
        times = json.loads(CRASH_LOG.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return [float(at) for at in times] if isinstance(times, list) else []


def record_start(now: float, pid: int) -> tuple[bool, bool]:
    try:
        previous = RUN_MARKER.read_text(encoding="utf-8").strip()
    except OSError:
        previous = ""
    crashed = bool(previous) and previous != str(pid)
    crashes = _crash_times() + ([now] if crashed else [])
    ZOYA_HOME.mkdir(parents=True, exist_ok=True)
    CRASH_LOG.write_text(json.dumps(crashes), encoding="utf-8")
    if not should_restart(crashes, now):
        RUN_MARKER.unlink(missing_ok=True)
        return crashed, False
    RUN_MARKER.write_text(str(pid), encoding="utf-8")
    return crashed, True


def run_agent(args: list[str]) -> int:
    crashed, carry_on = record_start(time.time(), os.getpid())
    if not carry_on:
        print(GAVE_UP, flush=True)
        say_directly(GAVE_UP)
        return 0
    if crashed:
        os.environ[RESTARTED_ENV] = "1"
    from zoya import main

    code = main.main(args)
    RUN_MARKER.unlink(missing_ok=True)
    return 0 if code == EXIT_CANNOT_START else code


def run(argv: list[str]) -> int:
    if APP_BUNDLE is None:
        print(NOT_BUNDLED, file=sys.stderr)
        return 1
    if argv[:1] == [AGENT_ARG]:
        return run_agent(argv[1:])
    return launch(Path(sys.executable))


if __name__ == "__main__":
    sys.exit(run(sys.argv[1:]))
