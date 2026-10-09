"""Record a screen rect frame by frame for the motion pass: every frame ScreenCaptureKit delivers
goes to an H.264 file (ffmpeg, near-lossless) and its host-clock timestamp to a .times file, so a
frame lines up with the overlay probe's display-link log.

    uv run python scripts/motion_recorder.py OUT.mp4 X Y WIDTH HEIGHT SECONDS PID [PID ...]

X/Y/WIDTH/HEIGHT are display points, top-left origin. Frames are 1 px per point. Only the
windows of the given processes are recorded: nothing else on the screen reaches the file.

APIs: https://developer.apple.com/documentation/screencapturekit/scstream
https://developer.apple.com/documentation/screencapturekit/scstreamoutput
https://developer.apple.com/documentation/screencapturekit/scstreamframeinfo/status
"""

from __future__ import annotations

import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

import CoreMedia
import objc
import Quartz
import ScreenCaptureKit as SCK

FPS = 60
COMPLETE = 0
SCREEN_OUTPUT = 0
WAIT_S = 10.0


def _content() -> Any:
    done, box = threading.Event(), {}

    def handler(content: Any, error: Any) -> None:
        box["content"], box["error"] = content, error
        done.set()

    SCK.SCShareableContent.getShareableContentExcludingDesktopWindows_onScreenWindowsOnly_completionHandler_(
        False, True, handler
    )
    done.wait(WAIT_S)
    if box.get("content") is None:
        sys.exit(f"no screen content: {box.get('error')}")
    return box["content"]


def _complete(sample: Any) -> bool:
    infos = CoreMedia.CMSampleBufferGetSampleAttachmentsArray(sample, False)
    if not infos:
        return False
    status = infos[0].get(SCK.SCStreamFrameInfoStatus)
    return status is not None and int(status) == COMPLETE


def _write(output: Any, pixels: Any) -> None:
    row = Quartz.CVPixelBufferGetBytesPerRow(pixels)
    height = Quartz.CVPixelBufferGetHeight(pixels)
    data = Quartz.CVPixelBufferGetBaseAddress(pixels).as_buffer(row * height)
    width_bytes = output.width * 4
    if row == width_bytes:
        output.sink.write(bytes(data))
        return
    for index in range(height):
        output.sink.write(bytes(data[index * row : index * row + width_bytes]))


class Output(objc.lookUpClass("NSObject"), protocols=[objc.protocolNamed("SCStreamOutput")]):
    def stream_didOutputSampleBuffer_ofType_(
        self, _stream: Any, sample: Any, kind: int
    ) -> None:  # noqa: N802
        if kind != SCREEN_OUTPUT or not _complete(sample):
            return
        pixels = CoreMedia.CMSampleBufferGetImageBuffer(sample)
        stamp = CoreMedia.CMSampleBufferGetPresentationTimeStamp(sample)
        Quartz.CVPixelBufferLockBaseAddress(pixels, 1)
        try:
            _write(self, pixels)
        finally:
            Quartz.CVPixelBufferUnlockBaseAddress(pixels, 1)
        self.times.append(stamp.value / stamp.timescale)


def _ffmpeg(out: Path, width: int, height: int) -> subprocess.Popen:
    command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo"]
    command += ["-pix_fmt", "bgra", "-s", f"{width}x{height}", "-r", str(FPS), "-i", "-"]
    command += ["-c:v", "libx264", "-preset", "ultrafast", "-crf", "8", "-pix_fmt", "yuv444p"]
    return subprocess.Popen([*command, str(out)], stdin=subprocess.PIPE)


def _only(pids: set[int]) -> Any:
    content = _content()
    apps = [app for app in content.applications() if app.processID() in pids]
    if len(apps) != len(pids):
        sys.exit(f"not every process has a window yet: {sorted(pids)}")
    display = content.displays()[0]
    return SCK.SCContentFilter.alloc().initWithDisplay_includingApplications_exceptingWindows_(
        display, apps, []
    )


def record(out: Path, rect: tuple[int, int, int, int], seconds: float, pids: set[int]) -> int:
    x, y, width, height = rect
    content_filter = _only(pids)
    config = SCK.SCStreamConfiguration.alloc().init()
    config.setSourceRect_(((x, y), (width, height)))
    config.setWidth_(width)
    config.setHeight_(height)
    config.setShowsCursor_(False)
    config.setPixelFormat_(int.from_bytes(b"BGRA", "big"))
    config.setMinimumFrameInterval_(CoreMedia.CMTimeMake(1, FPS))
    config.setQueueDepth_(8)
    encoder = _ffmpeg(out, width, height)
    output = Output.alloc().init()
    output.sink, output.width, output.times = encoder.stdin, width, []
    stream = SCK.SCStream.alloc().initWithFilter_configuration_delegate_(
        content_filter, config, None
    )
    stream.addStreamOutput_type_sampleHandlerQueue_error_(output, SCREEN_OUTPUT, None, None)
    started = threading.Event()
    stream.startCaptureWithCompletionHandler_(lambda _error: started.set())
    started.wait(WAIT_S)
    print("recording", flush=True)
    time.sleep(seconds)
    stopped = threading.Event()
    stream.stopCaptureWithCompletionHandler_(lambda _error: stopped.set())
    stopped.wait(WAIT_S)
    encoder.stdin.close()
    encoder.wait()
    out.with_suffix(".times").write_text("\n".join(f"{t:.6f}" for t in output.times) + "\n")
    print(f"{len(output.times)} frames", flush=True)
    return 0


def main() -> int:
    out, *numbers = sys.argv[1:6]
    seconds, pids = float(sys.argv[6]), {int(pid) for pid in sys.argv[7:]}
    rect = tuple(int(float(n)) for n in numbers)
    return record(Path(out), rect, seconds, pids)


if __name__ == "__main__":
    sys.exit(main())
