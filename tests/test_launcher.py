from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
APP = REPO / "dist" / "Zoya.app"
EXIT_REFUSED = 2

spec = importlib.util.spec_from_file_location("build_app", REPO / "packaging" / "build_app.py")
build_app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build_app)

pytestmark = pytest.mark.skipif(not APP.exists(), reason="build Zoya.app first: ./build")


def test_the_launcher_refuses_code_that_is_not_zoyas(tmp_path):
    marker = tmp_path / "ran"
    for arguments in build_app.refused_launches(marker):
        result = subprocess.run(
            [str(APP / "Contents" / "MacOS" / "Zoya"), *arguments],
            input=f"open({str(marker)!r}, 'w').write('ran')\n",
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        assert result.returncode == EXIT_REFUSED, arguments
        assert not marker.exists(), arguments


def test_the_launcher_still_runs_an_allowlisted_module():
    result = subprocess.run(
        [str(APP / "Contents" / "MacOS" / "Zoya"), "-m", "zoya.permissions", "accessibility"],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0
    assert result.stdout.strip() in {"0", "1"}
