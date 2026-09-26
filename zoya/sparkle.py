from __future__ import annotations

import sys
from collections.abc import Callable
from typing import Any

import objc
from Foundation import NSBundle, NSObject

from zoya.config import APP_BUNDLE

CHOICE_SKIP = 0
CHOICE_INSTALL = 1
CHOICE_DISMISS = 2
CHOICES = {"install": CHOICE_INSTALL, "later": CHOICE_DISMISS}
_NO_ARGUMENTS = {"retval": {"type": b"v"}, "arguments": {0: {"type": b"^v"}}}
_CHOICE_ARGUMENT = {"retval": {"type": b"v"}, "arguments": {0: {"type": b"^v"}, 1: {"type": b"q"}}}
_PERMISSION_ARGUMENT = {
    "retval": {"type": b"v"},
    "arguments": {0: {"type": b"^v"}, 1: {"type": b"@"}},
}
BLOCK_ARGUMENTS = {
    b"showUpdatePermissionRequest:reply:": {3: _PERMISSION_ARGUMENT},
    b"showUserInitiatedUpdateCheckWithCancellation:": {2: _NO_ARGUMENTS},
    b"showUpdateFoundWithAppcastItem:state:reply:": {4: _CHOICE_ARGUMENT},
    b"showUpdateNotFoundWithError:acknowledgement:": {3: _NO_ARGUMENTS},
    b"showUpdaterError:acknowledgement:": {3: _NO_ARGUMENTS},
    b"showDownloadInitiatedWithCancellation:": {2: _NO_ARGUMENTS},
    b"showReadyToInstallAndRelaunch:": {2: _CHOICE_ARGUMENT},
    b"showInstallingUpdateWithApplicationTerminated:retryTerminatingApplication:": {
        3: _NO_ARGUMENTS
    },
    b"showUpdateInstalledAndRelaunched:acknowledgement:": {3: _NO_ARGUMENTS},
}

_state: dict[str, Any] = {}


def _log(message: str) -> None:
    print(f"sparkle: {message}", file=sys.stderr, flush=True)


def _load_framework() -> Any:
    framework = APP_BUNDLE / "Contents" / "Frameworks" / "Sparkle.framework"
    objc.loadBundle("Sparkle", {}, bundle_path=str(framework))
    for selector, arguments in BLOCK_ARGUMENTS.items():
        objc.registerMetaDataForSelector(
            b"NSObject",
            selector,
            {"arguments": {index: {"callable": block} for index, block in arguments.items()}},
        )
    objc.registerMetaDataForSelector(
        b"SPUUpdater", b"startUpdater:", {"arguments": {2: {"type_modifier": b"o"}}}
    )
    return objc.protocolNamed("SPUUserDriver")


def _driver_class(protocol: Any, offer: Callable[[str], None]) -> Any:
    class SpokenUserDriver(NSObject, protocols=[protocol]):
        def showUpdatePermissionRequest_reply_(self, _request, reply):  # noqa: N802
            response = objc.lookUpClass("SUUpdatePermissionResponse").alloc()
            reply(response.initWithAutomaticUpdateChecks_sendSystemProfile_(True, False))

        def showUserInitiatedUpdateCheckWithCancellation_(self, _cancellation):  # noqa: N802
            pass

        def showUpdateFoundWithAppcastItem_state_reply_(self, item, _state, reply):  # noqa: N802
            _state_reply(reply)
            offer(str(item.displayVersionString()))

        def showUpdateReleaseNotesWithDownloadData_(self, _data):  # noqa: N802
            pass

        def showUpdateReleaseNotesFailedToDownloadWithError_(self, _error):  # noqa: N802
            pass

        def showUpdateNotFoundWithError_acknowledgement_(self, _error, acknowledge):  # noqa: N802
            acknowledge()

        def showUpdaterError_acknowledgement_(self, error, acknowledge):  # noqa: N802
            _log(f"update failed: {error.localizedDescription()}")
            acknowledge()

        def showDownloadInitiatedWithCancellation_(self, _cancellation):  # noqa: N802
            _log("downloading the update")

        def showDownloadDidReceiveExpectedContentLength_(self, _length):  # noqa: N802
            pass

        def showDownloadDidReceiveDataOfLength_(self, _length):  # noqa: N802
            pass

        def showDownloadDidStartExtractingUpdate(self):  # noqa: N802
            pass

        def showExtractionReceivedProgress_(self, _progress):  # noqa: N802
            pass

        def showReadyToInstallAndRelaunch_(self, reply):  # noqa: N802
            _log("installing and relaunching")
            reply(CHOICE_INSTALL)

        def showInstallingUpdateWithApplicationTerminated_retryTerminatingApplication_(  # noqa: N802
            self, _terminated, _retry
        ):
            pass

        def showUpdateInstalledAndRelaunched_acknowledgement_(  # noqa: N802
            self, _relaunched, acknowledge
        ):
            acknowledge()

        def showUpdateInFocus(self):  # noqa: N802
            pass

        def dismissUpdateInstallation(self):  # noqa: N802
            pass

    return SpokenUserDriver


def _state_reply(reply: Callable[[int], None]) -> None:
    _state["reply"] = reply


def answer(choice: str) -> None:
    reply = _state.pop("reply", None)
    if reply is None or choice not in CHOICES:
        return
    reply(CHOICES[choice])


def start(offer: Callable[[str], None]) -> str:
    if APP_BUNDLE is None:
        return "off (running from source)"
    driver = _driver_class(_load_framework(), offer).alloc().init()
    bundle = NSBundle.mainBundle()
    updater = objc.lookUpClass("SPUUpdater").alloc()
    updater = updater.initWithHostBundle_applicationBundle_userDriver_delegate_(
        bundle, bundle, driver, None
    )
    started, error = updater.startUpdater_(None)
    if not started:
        return f"off ({error.localizedDescription() if error else 'unknown error'})"
    _state.update(driver=driver, updater=updater)
    updater.checkForUpdatesInBackground()
    return f"on ({updater.feedURL()})"
