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
from typing import Any

from zoya.config import (
    REKOGNITION_TIMEOUT_S,
    SCREEN_CAPTURE_TIMEOUT_S,
    SCREENSHOT_JPEG_QUALITY,
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
    import AppKit
    import ScreenCaptureKit as SCK

    scale = content_filter.pointPixelScale()  # per display (D23): 2.0 Retina, 1.0 external
    config = SCK.SCStreamConfiguration.alloc().init()
    config.setWidth_(int(size.width * scale))
    config.setHeight_(int(size.height * scale))
    config.setShowsCursor_(False)
    image, error = _await(
        lambda h: SCK.SCScreenshotManager.captureImageWithFilter_configuration_completionHandler_(
            content_filter, config, h
        )
    )
    if error is not None or image is None:
        raise ToolError("I couldn't take a screenshot to check the page.")
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
_client: Any = None


def _rekognition() -> Any:
    """Own client: aws.client's 2 s read timeout is too short for an image upload."""
    global _client
    with _client_lock:
        if _client is None:
            profile = os.environ.get("AWS_PROFILE")
            if not profile:
                raise RuntimeError("AWS_PROFILE not set (D35)")
            import boto3
            from botocore.config import Config

            config = Config(
                connect_timeout=REKOGNITION_TIMEOUT_S,
                read_timeout=REKOGNITION_TIMEOUT_S,
                retries={"max_attempts": 1},
            )
            session = boto3.Session(profile_name=profile)
            _client = session.client("rekognition", region_name=aws_region(), config=config)
        return _client


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
