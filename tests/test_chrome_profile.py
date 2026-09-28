"""D150: Zoya never launches Chrome into a profile another Chrome holds.

Chrome started on a profile in use hands its command line to the running Chrome, which opens an
empty window, and exits. Every browser call then launched again: one empty tab per call, on
whichever Zoya's Chrome held the profile, while this Zoya did nothing.
"""

import os
import socket
import sys

import pytest

from zoya.tools import ToolError, browser


class Exited:
    pid = 4242

    def poll(self) -> int:
        return 0


class Running:
    pid = 4243

    def poll(self) -> None:
        return None


@pytest.fixture
def launches(tmp_path, monkeypatch) -> list[list[str]]:
    binary = tmp_path / "Chrome"
    binary.touch()
    profile = tmp_path / "profile"
    profile.mkdir()
    launched: list[list[str]] = []
    monkeypatch.setattr(browser, "CHROME_BINARY", binary)
    monkeypatch.setattr(browser, "BROWSER_PROFILE_DIR", profile)
    monkeypatch.setattr(browser, "CHROME_PID_FILE", tmp_path / "chrome.pid")
    monkeypatch.setattr(browser, "_state", {})
    monkeypatch.setattr(browser.atexit, "register", lambda _close: None)
    monkeypatch.setattr(browser.subprocess, "Popen", lambda argv, **_k: launched.append(argv))
    return launched


def hold(profile_owner: str) -> None:
    (browser.BROWSER_PROFILE_DIR / "SingletonLock").symlink_to(profile_owner)


def test_a_profile_held_by_a_live_chrome_is_never_launched_into(launches, monkeypatch):
    hold(f"{socket.gethostname()}-{os.getpid()}")
    monkeypatch.setattr(browser, "_is_zoya_chrome", lambda pid: pid == os.getpid())
    monkeypatch.setattr(
        browser.subprocess, "Popen", lambda argv, **_k: launches.append(argv) or Exited()
    )

    for _ in range(3):
        with pytest.raises(ToolError, match="already in use"):
            browser._chrome()

    assert launches == []


@pytest.mark.parametrize("owner", ["{host}-999999999", "another-mac.local-{pid}", "junk"])
def test_a_stale_lock_does_not_block_the_launch(launches, monkeypatch, owner):
    hold(owner.format(host=socket.gethostname(), pid=os.getpid()))
    monkeypatch.setattr(
        browser.subprocess, "Popen", lambda argv, **_k: launches.append(argv) or Running()
    )
    monkeypatch.setattr(browser, "_cdp_ready", lambda _process, _port: None)

    browser._chrome()

    assert len(launches) == 1


def test_the_harness_counts_blank_tabs_without_launching_chrome(monkeypatch):
    import importlib.util
    from pathlib import Path

    path = Path(__file__).resolve().parents[1] / "evals" / "harness" / "run.py"
    spec = importlib.util.spec_from_file_location("harness_run", path)
    harness = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, harness)
    spec.loader.exec_module(harness)
    targets = [{"url": "https://shop.example/p/1"}, {"url": "about:blank"}]
    targets.append({"url": "chrome://newtab/"})
    monkeypatch.setattr(browser, "running", lambda: True)
    monkeypatch.setattr(browser, "_on_browser", lambda call: call())
    monkeypatch.setattr(browser, "_page_targets", lambda: targets)

    assert harness.page_tabs() == (3, 2)

    monkeypatch.setattr(browser, "running", lambda: False)
    assert harness.page_tabs() == (0, 0)
