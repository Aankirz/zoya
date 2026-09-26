import base64
import json
import zipfile

import pytest

from zoya import config, diagnostics, first_run, permissions

OPENAI_KEY = "sk-proj-Ab3dEf9hIjK1mNoPq7RsTuVwXyZ0123456789abcdEF"
LICENSE = "zoya_Q2xpcGJvYXJkS2V5VGhhdE11c3ROZXZlckxlYWtIZXJl"
AWS_ACCESS_KEY = "AKIAIOSFODNN7EXAMPLE"
AWS_SECRET = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
PASSWORD = "Tr0ub4dor&3"
OTP = "482913"
CARD = "4111 1111 1111 1111"
SCREENSHOT = base64.b64encode(bytes(range(256)) * 12).decode()
MEMORY = "my sister's birthday is 12 March"
SECRETS = [OPENAI_KEY, LICENSE, AWS_ACCESS_KEY, AWS_SECRET, PASSWORD, OTP, CARD, SCREENSHOT, MEMORY]


@pytest.fixture
def seeded(tmp_path, monkeypatch):
    logs = tmp_path / "logs"
    logs.mkdir()
    (logs / "zoya.log").write_text(
        "\n".join(
            [
                f"ERROR zoya.models: OpenAI said Incorrect API key provided: {OPENAI_KEY}",
                f"WARNING zoya.speech: relay call with Authorization: Bearer {LICENSE}",
                f"ERROR zoya.aws: aws_access_key_id={AWS_ACCESS_KEY}",
                f"ERROR zoya.aws: aws_secret_access_key={AWS_SECRET}",
                f"INFO zoya.safety: the user said my password is {PASSWORD}",
                f"INFO zoya.safety: your OTP is {OTP}, card {CARD}",
                f'DEBUG zoya.screen: {{"image": "data:image/jpeg;base64,{SCREENSHOT}"}}',
                f"INFO zoya.tools.memory: saved {MEMORY}",
                "WARNING zoya.router: rules_ms=17 total_ms=95",
            ]
        ),
        encoding="utf-8",
    )
    command = {"route": "skill", "total_ms": 95, "command": f"remember that {MEMORY}"}
    spoken = {"route": "fast", "spoken": f"Your code is {OTP}", "heard": PASSWORD}
    timing = "\n".join(json.dumps(line) for line in (command, spoken))
    (logs / "timing.log").write_text(timing, encoding="utf-8")
    memory_file = tmp_path / "memory.json"
    memory_file.write_text(json.dumps([{"content": MEMORY}]), encoding="utf-8")
    monkeypatch.setattr(config, "LOG_DIR", logs)
    monkeypatch.setattr(config, "MEMORY_LOCAL_FILE", memory_file)
    monkeypatch.setattr(first_run, "STATE_FILE", tmp_path / "setup.json")
    monkeypatch.setattr(permissions, "status", lambda: {"microphone": True})
    monkeypatch.setenv("OPENAI_API_KEY", OPENAI_KEY)
    monkeypatch.setenv("ZOYA_LICENSE_KEY", LICENSE)
    return tmp_path


def _zip_text(path) -> str:
    with zipfile.ZipFile(path) as bundle:
        return "\n".join(bundle.read(name).decode("utf-8") for name in bundle.namelist())


def test_problem_report_holds_no_key_password_otp_card_screenshot_or_memory(seeded):
    report = diagnostics.make_report(seeded / "Desktop")

    text = _zip_text(report)

    leaked = [secret[:12] for secret in SECRETS if secret in text]
    assert leaked == []
    assert "total_ms" in text and '"license": "present"' in text


def test_problem_report_phrase_is_recognised():
    assert diagnostics.is_report_phrase("Zoya, send a problem report")
    assert not diagnostics.is_report_phrase("send the report to my sister")
