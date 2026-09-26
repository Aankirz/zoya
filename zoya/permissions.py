from __future__ import annotations

import ctypes
import os
import subprocess
import sys
import threading
import time
from functools import cache

import objc

PERMISSIONS = ("accessibility", "screen", "microphone", "automation")
PANE_URL = "x-apple.systempreferences:com.apple.preference.security?Privacy_{anchor}"
PANE_ANCHORS = {
    "accessibility": "Accessibility",
    "screen": "ScreenCapture",
    "microphone": "Microphone",
    "automation": "Automation",
}
AUTOMATION_TARGET_ID = "com.apple.Notes"
AUTOMATION_TARGET_NAME = "Notes"
AV_AUTHORIZED = 3
AV_DENIED = 2
AE_GRANTED = 0
AE_DENIED = -1743
AE_NOT_RUNNING = -600
PROBE_TIMEOUT_S = 10.0
PS_TIMEOUT_S = 2.0
OPEN_TIMEOUT_S = 10.0
LAUNCH_WAIT_S = 5.0
LAUNCH_POLL_S = 0.1
MIC_REQUEST_S = 0.2
CORE_SERVICES = "/System/Library/Frameworks/CoreServices.framework/CoreServices"
AV_FOUNDATION = "/System/Library/Frameworks/AVFoundation.framework"
HOST_FALLBACK = "your terminal app"
_launched = None


class _AEDesc(ctypes.Structure):
    _fields_ = [("descriptorType", ctypes.c_uint32), ("dataHandle", ctypes.c_void_p)]


def _fourcc(code: str) -> int:
    return int.from_bytes(code.encode("ascii"), "big")


@cache
def _core_services() -> ctypes.CDLL:
    lib = ctypes.CDLL(CORE_SERVICES)
    desc = ctypes.POINTER(_AEDesc)
    lib.AECreateDesc.argtypes = [ctypes.c_uint32, ctypes.c_void_p, ctypes.c_long, desc]
    lib.AEDisposeDesc.argtypes = [desc]
    lib.AEDeterminePermissionToAutomateTarget.argtypes = [
        desc,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.c_ubyte,
    ]
    lib.AEDeterminePermissionToAutomateTarget.restype = ctypes.c_int32
    return lib


def automation_status(ask: bool = False) -> int:
    lib = _core_services()
    target = AUTOMATION_TARGET_ID.encode()
    desc = _AEDesc()
    lib.AECreateDesc(_fourcc("bund"), target, len(target), ctypes.byref(desc))
    try:
        wildcard = _fourcc("****")
        return lib.AEDeterminePermissionToAutomateTarget(
            ctypes.byref(desc), wildcard, wildcard, int(ask)
        )
    finally:
        lib.AEDisposeDesc(ctypes.byref(desc))


@cache
def _audio_media_type() -> object:
    bundle = objc.loadBundle("AVFoundation", {}, bundle_path=AV_FOUNDATION)
    found: dict[str, object] = {}
    objc.loadBundleVariables(bundle, found, [("AVMediaTypeAudio", b"@")])
    return found["AVMediaTypeAudio"]


def microphone_status() -> int:
    media_type = _audio_media_type()
    return objc.lookUpClass("AVCaptureDevice").authorizationStatusForMediaType_(media_type)


def granted(name: str) -> bool:
    if name == "accessibility":
        from ApplicationServices import AXIsProcessTrusted

        return bool(AXIsProcessTrusted())
    if name == "screen":
        from Quartz import CGPreflightScreenCaptureAccess

        return bool(CGPreflightScreenCaptureAccess())
    if name == "microphone":
        return microphone_status() == AV_AUTHORIZED
    status = automation_status()
    if status != AE_NOT_RUNNING:
        return status == AE_GRANTED
    _launch_automation_target()
    try:
        return automation_status() == AE_GRANTED
    finally:
        release_automation_target()


def granted_fresh(name: str) -> bool:
    command = [sys.executable, "-m", "zoya.permissions", name]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=PROBE_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        return False
    return result.stdout.strip() == "1"


def denied(name: str) -> bool:
    if name == "microphone":
        return microphone_status() == AV_DENIED
    if name == "automation":
        return automation_status() == AE_DENIED
    return False


def status() -> dict[str, bool]:
    return {name: granted(name) for name in PERMISSIONS}


def _ask_microphone() -> None:
    import sounddevice as sd

    with sd.InputStream(channels=1):
        sd.sleep(round(MIC_REQUEST_S * 1000))


def _running_targets() -> list:
    from AppKit import NSRunningApplication

    return list(NSRunningApplication.runningApplicationsWithBundleIdentifier_(AUTOMATION_TARGET_ID))


def _launch_automation_target() -> None:
    global _launched
    before = {app.processIdentifier() for app in _running_targets()}
    command = ["open", "-g", "-j", "-b", AUTOMATION_TARGET_ID]
    subprocess.run(command, capture_output=True, timeout=OPEN_TIMEOUT_S, check=False)
    deadline = time.monotonic() + LAUNCH_WAIT_S
    ours: list[int] = []
    while time.monotonic() < deadline:
        ours = [pid for app in _running_targets() if (pid := app.processIdentifier()) not in before]
        if ours and automation_status() != AE_NOT_RUNNING:
            break
        time.sleep(LAUNCH_POLL_S)
    if ours:
        _launched = ours[0]


def _instance(pid: int):  # noqa: ANN202
    from AppKit import NSRunningApplication

    return NSRunningApplication.runningApplicationWithProcessIdentifier_(pid)


def release_automation_target() -> None:
    global _launched
    pid, _launched = _launched, None
    app = _instance(pid) if pid is not None else None
    if app is None or app.isActive():
        return
    app.terminate()
    deadline = time.monotonic() + LAUNCH_WAIT_S
    while _instance(pid) is not None and time.monotonic() < deadline:
        time.sleep(LAUNCH_POLL_S)


def request(name: str) -> None:
    if name == "accessibility":
        from ApplicationServices import AXIsProcessTrustedWithOptions, kAXTrustedCheckOptionPrompt

        AXIsProcessTrustedWithOptions({kAXTrustedCheckOptionPrompt: True})
    elif name == "screen":
        from Quartz import CGRequestScreenCaptureAccess

        CGRequestScreenCaptureAccess()
    elif name == "microphone":
        threading.Thread(target=_ask_microphone, name="zoya-mic-ask", daemon=True).start()
    else:
        if automation_status() == AE_NOT_RUNNING:
            _launch_automation_target()
        ask = threading.Thread(
            target=automation_status, args=(True,), name="zoya-automation-ask", daemon=True
        )
        ask.start()


def open_pane(name: str) -> None:
    url = PANE_URL.format(anchor=PANE_ANCHORS[name])
    subprocess.run(["open", url], capture_output=True, timeout=OPEN_TIMEOUT_S, check=False)


def _parent_and_command(pid: int) -> tuple[int, str]:
    result = subprocess.run(
        ["ps", "-o", "ppid=,comm=", "-p", str(pid)],
        capture_output=True,
        text=True,
        timeout=PS_TIMEOUT_S,
        check=False,
    )
    parent, _, command = result.stdout.strip().partition(" ")
    return (int(parent), command.strip()) if parent.isdigit() else (0, "")


@cache
def host_app() -> str:
    from AppKit import NSRunningApplication

    from zoya.config import APP_BUNDLE

    if APP_BUNDLE:
        return APP_BUNDLE.stem
    pid = os.getppid()
    while pid > 1:
        parent, command = _parent_and_command(pid)
        if ".app/" in command and "Python.app" not in command:
            app = NSRunningApplication.runningApplicationWithProcessIdentifier_(pid)
            return str(app.localizedName()) if app is not None else HOST_FALLBACK
        pid = parent
    return HOST_FALLBACK


if __name__ == "__main__":
    print(int(granted(sys.argv[1])))
