"""Screen evidence for the safety gate (D23, §9.9): what is really on screen, not what the DOM
or the model says.

- ScreenCaptureKit window/display capture at the display's own pixel scale (no hard-coded 2×).
- Amazon Rekognition DetectText OCR (ap-south-1, zoya-app policy `rekognition:DetectText`).
- Accessibility (AX) label and secure-field reads for Guard 2 on native apps.

Screenshots stay in memory only and are never logged or written to disk (§12.3, AGENTS.md §6).

APIs (verified 2026-09-14 against pyobjc-framework-ScreenCaptureKit / ApplicationServices 12.2.2
and a live capture on this Mac):
- https://developer.apple.com/documentation/screencapturekit/scscreenshotmanager/captureimage(contentfilter:configuration:completionhandler:)
- https://developer.apple.com/documentation/screencapturekit/scshareablecontent
- https://docs.aws.amazon.com/rekognition/latest/APIReference/API_DetectText.html (≤ 5 MB image
  bytes; LINE detections with a relative BoundingBox; at most 100 words per image)
- https://developer.apple.com/documentation/applicationservices/1462077-axuielementcopyelementatposition
"""

from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass
from typing import Any

from zoya import aws
from zoya.config import (
    REKOGNITION_TIMEOUT_S,
    SCREEN_CAPTURE_TIMEOUT_S,
    SCREEN_CHANGED_FRACTION,
    SCREEN_PIXEL_DELTA,
    SCREENSHOT_JPEG_QUALITY,
    SCREENSHOT_MAX_WIDTH,
    aws_region,
)
from zoya.tools import ToolError

OcrLine = tuple[str, float, float, float]  # text, left, top, height (relative 0..1)
AX_LABEL_ATTRIBUTES = ("AXTitle", "AXDescription", "AXValue", "AXHelp")
AX_CLICKABLE_ROLES = {"AXButton", "AXLink", "AXMenuItem", "AXCheckBox", "AXRadioButton"}
AX_MAX_PARENTS = 4
WINDOW_LOOKUP_ATTEMPTS = 4
WINDOW_LOOKUP_RETRY_S = 0.3


def _await(start: Any) -> tuple:
    """Run an ObjC call that reports through a completion handler; wait a bounded time."""
    done, box = threading.Event(), {}

    def handler(*results: Any) -> None:
        box["results"] = results
        done.set()

    start(handler)
    if not done.wait(SCREEN_CAPTURE_TIMEOUT_S):
        raise ToolError("I couldn't take a screenshot in time.")
    return box["results"]


def capture_window_jpeg(app_substring: str, title: str) -> bytes:
    """JPEG of the one on-screen window of `app_substring` titled exactly `title`.

    Only that window: other apps' private content never goes to OCR. Fails closed (ToolError).
    """
    import Quartz
    import ScreenCaptureKit as SCK

    # A window filter aborts the process (CGS_REQUIRE_INIT assertion) unless CoreGraphics has a
    # window-server connection; this call opens one (found live on this Mac, 2026-09-14).
    Quartz.CGMainDisplayID()
    for _attempt in range(WINDOW_LOOKUP_ATTEMPTS):  # a new Chrome window publishes its title late
        windows = _windows(SCK, app_substring, title)
        if len(windows) == 1:
            break
        time.sleep(WINDOW_LOOKUP_RETRY_S)
    if len(windows) != 1:  # none yet, or two lookalike windows: never guess which one is real
        raise ToolError("I couldn't find the browser window on screen to check it.")
    window = windows[0]
    content_filter = SCK.SCContentFilter.alloc().initWithDesktopIndependentWindow_(window)
    return _capture(content_filter, window.frame().size)


def _windows(SCK: Any, app_substring: str, title: str) -> list[Any]:  # noqa: N803 — module
    content, error = _await(
        lambda h: SCK.SCShareableContent.getShareableContentExcludingDesktopWindows_onScreenWindowsOnly_completionHandler_(  # noqa: E501
            True, True, h
        )
    )
    if error is not None or content is None:
        raise ToolError("I need Screen Recording permission to check the page.")
    return [
        w
        for w in content.windows()
        if w.owningApplication()
        and app_substring in (w.owningApplication().applicationName() or "")
        and title
        and w.title() == title
    ]


def _capture(content_filter: Any, size: Any) -> bytes:
    scale = content_filter.pointPixelScale()  # per display (D23): 2.0 Retina, 1.0 external
    return _jpeg(_capture_image(content_filter, size.width * scale, size.height * scale))


def _capture_image(
    content_filter: Any, width: float, height: float, source: Frame | None = None
) -> Any:
    import ScreenCaptureKit as SCK

    config = SCK.SCStreamConfiguration.alloc().init()
    if source is not None:  # display-local points; SCStreamConfiguration.sourceRect (macOS 14+)
        config.setSourceRect_(((source[0], source[1]), (source[2], source[3])))
    config.setWidth_(int(width))
    config.setHeight_(int(height))
    config.setShowsCursor_(False)
    image, error = _await(
        lambda h: SCK.SCScreenshotManager.captureImageWithFilter_configuration_completionHandler_(
            content_filter, config, h
        )
    )
    if error is not None or image is None:
        raise ToolError("I couldn't take a screenshot to check the page.")
    return image


def _jpeg(image: Any) -> bytes:
    import AppKit

    bitmap = AppKit.NSBitmapImageRep.alloc().initWithCGImage_(image)
    jpeg = bitmap.representationUsingType_properties_(
        AppKit.NSBitmapImageFileTypeJPEG,
        {AppKit.NSImageCompressionFactor: SCREENSHOT_JPEG_QUALITY},
    )
    return bytes(jpeg)


def detect_text(jpeg: bytes) -> list[OcrLine]:
    """Rekognition DetectText LINEs. Any failure is a ToolError: the gate then never confirms."""
    try:
        response = _rekognition().detect_text(Image={"Bytes": jpeg})
    except Exception as error:  # noqa: BLE001 — OCR failure must fail closed, politely
        raise ToolError("I couldn't read the screen to double-check the amount.") from error
    lines = []
    for item in response.get("TextDetections", []):
        if item.get("Type") != "LINE":
            continue
        box = item["Geometry"]["BoundingBox"]
        lines.append((item["DetectedText"], box["Left"], box["Top"], box["Height"]))
    return lines


_client_lock = threading.Lock()
_clients: dict[str, Any] = {}


def _rekognition() -> Any:
    return aws_client("rekognition", REKOGNITION_TIMEOUT_S)


def aws_client(service: str, timeout_s: float) -> Any:
    """Own clients: aws.client's 2 s read timeout is too short for an image upload."""
    with _client_lock:
        if service not in _clients:
            profile = os.environ.get("AWS_PROFILE")
            if not profile:
                raise RuntimeError("AWS_PROFILE not set (D35)")
            import boto3
            from botocore.config import Config

            config = Config(
                connect_timeout=timeout_s, read_timeout=timeout_s, retries={"max_attempts": 1}
            )
            session = boto3.Session(profile_name=profile)
            client = session.client(service, region_name=aws_region(), config=config)
            _clients[service] = aws.traced(client)
        return _clients[service]


# --- Accessibility (native apps; Phase 5 click tools call these) --------------------------------


def _ax(element: Any, attribute: str) -> Any:
    import ApplicationServices as AS

    error, value = AS.AXUIElementCopyAttributeValue(element, attribute, None)
    return value if error == 0 else None


def ax_labels_at(x: float, y: float) -> list[str]:
    """Every label of the element under screen point (x, y) and its clickable ancestors.

    Guard 2 for AX clicks: pass these to safety.risky_label before pressing anything.
    """
    import ApplicationServices as AS

    error, element = AS.AXUIElementCopyElementAtPosition(
        AS.AXUIElementCreateSystemWide(), x, y, None
    )
    if error != 0 or element is None:
        raise ToolError("I can't tell what is at that spot, so I won't click it.")
    labels: list[str] = []
    for _ in range(AX_MAX_PARENTS):
        labels += [str(v) for a in AX_LABEL_ATTRIBUTES if isinstance(v := _ax(element, a), str)]
        if _ax(element, "AXRole") in AX_CLICKABLE_ROLES:
            break
        element = _ax(element, "AXParent")
        if element is None:
            break
    return labels


def ax_focused_subrole() -> str:
    """Subrole of the focused element ("AXSecureTextField" for passwords), "" if unknown."""
    import ApplicationServices as AS

    focused = _ax(AS.AXUIElementCreateSystemWide(), "AXFocusedUIElement")
    return str(_ax(focused, "AXSubrole") or "") if focused is not None else ""


# --- Whole-display screenshots for computer use (Phase 5, §9.6, D23) ---------------------------
#
# Captured at the display's POINT size (or smaller, ≤ SCREENSHOT_MAX_WIDTH), never pixel size,
# so image coordinates map to click coordinates by one ratio whatever the backing scale (AUDIT B10).
# Zoya's own windows are excluded by the content filter, not NSWindowSharingNone (AUDIT B11).
# SCDisplay.frame is in global display points, top-left origin: the space CGEvent and AX use.
# https://developer.apple.com/documentation/screencapturekit/scdisplay/frame
# https://developer.apple.com/documentation/screencapturekit/sccontentfilter/init(display:excludingapplications:exceptingwindows:)

Frame = tuple[float, float, float, float]  # x, y, width, height in global points


@dataclass(frozen=True)
class Shot:
    jpeg: bytes
    width: int  # image pixels, the space the model answers in
    height: int
    frame: Frame  # the display this image shows
    app: str  # frontmost app name (from the system, not the screen)
    pixel_scale: float  # that display's backing scale, logged only: clicks never need it
    raw: bytes  # BGRA rows, for `screen_changed`; memory only, like the JPEG
    bytes_per_row: int


def capture_size(width_pt: float, height_pt: float, max_width: int) -> tuple[int, int]:
    """Point size, scaled down to at most `max_width` wide, aspect ratio kept."""
    ratio = min(1.0, max_width / width_pt)
    return round(width_pt * ratio), round(height_pt * ratio)


def image_to_screen(
    x: float, y: float, width: int, height: int, frame: Frame
) -> tuple[float, float]:
    """Model coordinates on a `width`×`height` screenshot → global click point on that display.

    Outside the image is refused: a click must never land on another display or off screen.
    """
    if not (0 <= x < width and 0 <= y < height):
        raise ToolError("That spot is outside the screenshot, so I won't click there.")
    left, top, frame_width, frame_height = frame
    return left + x * frame_width / width, top + y * frame_height / height


Box = tuple[int, int, int, int]  # left, top, right, bottom in image pixels


def screen_changed(before: Shot, after: Shot, box: Box | None = None) -> bool:
    """Did the region an action aimed at visibly change? Elsewhere on screen doesn't count: other
    apps animate (a clock, a video), so only the neighbourhood of the click or field is compared."""
    import numpy as np

    if (before.width, before.height, before.frame) != (after.width, after.height, after.frame):
        return True
    left, top, right, bottom = box or (0, 0, before.width, before.height)
    left, top = max(0, left), max(0, top)
    right, bottom = min(before.width, right), min(before.height, bottom)
    if right <= left or bottom <= top:
        return True

    def region(shot: Shot) -> Any:
        rows = np.frombuffer(shot.raw, np.uint8)[: shot.bytes_per_row * shot.height]
        pixels = rows.reshape(shot.height, shot.bytes_per_row // 4, 4)
        return pixels[top:bottom, left:right, :3].astype(np.int16)

    moved = np.abs(region(before) - region(after)).max(axis=2) > SCREEN_PIXEL_DELTA
    return float(moved.mean()) > SCREEN_CHANGED_FRACTION


def capture_display() -> Shot:
    """The display under the frontmost window, Zoya's own windows left out."""
    import AppKit
    import Quartz
    import ScreenCaptureKit as SCK

    Quartz.CGMainDisplayID()  # opens the window-server connection (see capture_window_jpeg)
    content, error = _await(
        lambda h: SCK.SCShareableContent.getShareableContentExcludingDesktopWindows_onScreenWindowsOnly_completionHandler_(  # noqa: E501
            True, True, h
        )
    )
    if error is not None or content is None:
        raise ToolError("I need Screen Recording permission to see the screen.")
    front = AppKit.NSWorkspace.sharedWorkspace().frontmostApplication()
    display = _front_display(content, front.processIdentifier() if front else -1)
    content_filter = display_filter(content, display)
    rect = display.frame()
    frame = (rect.origin.x, rect.origin.y, rect.size.width, rect.size.height)
    width, height = capture_size(frame[2], frame[3], SCREENSHOT_MAX_WIDTH)
    image = _capture_image(content_filter, width, height)
    return Shot(
        jpeg=_jpeg(image),
        width=Quartz.CGImageGetWidth(image),
        height=Quartz.CGImageGetHeight(image),
        frame=frame,
        app=str(front.localizedName()) if front else "",
        pixel_scale=float(content_filter.pointPixelScale()),
        raw=bytes(Quartz.CGDataProviderCopyData(Quartz.CGImageGetDataProvider(image))),
        bytes_per_row=Quartz.CGImageGetBytesPerRow(image),
    )


def capture_region_jpeg(x: float, y: float, half_width: float, half_height: float) -> bytes:
    """A JPEG of the screen around global point (x, y), at pixel scale, Zoya's windows left out.
    For OCR of what is drawn next to a native control (Guard 2 backstop)."""
    import Quartz
    import ScreenCaptureKit as SCK

    Quartz.CGMainDisplayID()
    content, error = _await(
        lambda h: SCK.SCShareableContent.getShareableContentExcludingDesktopWindows_onScreenWindowsOnly_completionHandler_(  # noqa: E501
            True, True, h
        )
    )
    if error is not None or content is None:
        raise ToolError("I need Screen Recording permission to see the screen.")
    display = next(
        (d for d in content.displays() if Quartz.CGRectContainsPoint(d.frame(), (x, y))), None
    )
    if display is None:
        raise ToolError("That spot isn't on any screen.")
    rect = display.frame()
    left = max(0.0, x - rect.origin.x - half_width)
    top = max(0.0, y - rect.origin.y - half_height)
    width = min(rect.size.width - left, 2 * half_width)
    height = min(rect.size.height - top, 2 * half_height)
    content_filter = display_filter(content, display)
    scale = content_filter.pointPixelScale()
    image = _capture_image(
        content_filter, width * scale, height * scale, (left, top, width, height)
    )
    return _jpeg(image)


def own_pids() -> set[int]:
    """Zoya and its stage overlay (Phase 7): never in a screenshot a model or OCR reads."""
    from zoya import overlay

    return {os.getpid(), *overlay.pids()}


def display_filter(content: Any, display: Any) -> Any:
    """The ONLY way screen.py builds a display filter: Zoya's apps (overlay, ring) left out.

    Window captures (`capture_window_jpeg`) need no exclusion: a desktop-independent window filter
    renders that one window only, whatever floats above it.
    """
    import ScreenCaptureKit as SCK

    pids = own_pids()
    mine = [a for a in content.applications() if a.processID() in pids]
    return SCK.SCContentFilter.alloc().initWithDisplay_excludingApplications_exceptingWindows_(
        display, mine, []
    )


def _front_display(content: Any, pid: int) -> Any:
    """The display holding the centre of the frontmost app's biggest normal window, else main."""
    import Quartz

    displays = list(content.displays())
    windows = [
        w
        for w in content.windows()
        if w.owningApplication()
        and w.owningApplication().processID() == pid
        and w.windowLayer() == 0
    ]
    if windows:
        rect = max(windows, key=lambda w: w.frame().size.width * w.frame().size.height).frame()
        cx, cy = rect.origin.x + rect.size.width / 2, rect.origin.y + rect.size.height / 2
        for display in displays:
            if Quartz.CGRectContainsPoint(display.frame(), (cx, cy)):
                return display
    main = Quartz.CGMainDisplayID()
    return next((d for d in displays if d.displayID() == main), displays[0])
