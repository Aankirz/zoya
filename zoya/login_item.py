"""Open Zoya at login, through Apple's SMAppService (macOS 13+)."""

from __future__ import annotations

from functools import cache
from typing import Any

import objc

from zoya.config import APP_BUNDLE

FRAMEWORK = "/System/Library/Frameworks/ServiceManagement.framework"
ENABLED = 1


@cache
def _service() -> Any:
    objc.loadBundle("ServiceManagement", {}, bundle_path=FRAMEWORK)
    for selector in (b"registerAndReturnError:", b"unregisterAndReturnError:"):
        objc.registerMetaDataForSelector(
            b"SMAppService", selector, {"arguments": {2: {"type_modifier": b"o"}}}
        )
    return objc.lookUpClass("SMAppService").mainAppService()


def enabled() -> bool:
    return APP_BUNDLE is not None and _service().status() == ENABLED


def set_enabled(wanted: bool) -> bool:
    if APP_BUNDLE is None:
        return False
    service = _service()
    change = service.registerAndReturnError_ if wanted else service.unregisterAndReturnError_
    change(None)
    return enabled()
