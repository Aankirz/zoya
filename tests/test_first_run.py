import pytest

from zoya import config, first_run, supervisor

LICENSE = "zoya_Q2xpcGJvYXJkS2V5VGhhdE11c3ROZXZlckxlYWtIZXJl"


@pytest.fixture
def key_step(tmp_path, monkeypatch):
    spoken, saved, checked, cleared = [], [], [], []
    monkeypatch.setattr(first_run, "STATE_FILE", tmp_path / "setup.json")
    monkeypatch.setattr(first_run, "say", spoken.append)
    monkeypatch.setattr(config, "save_license_key", saved.append)
    monkeypatch.setattr(first_run, "_clear_clipboard", cleared.append)

    def validate(key: str) -> str:
        checked.append(key)
        return "valid" if key == LICENSE else "invalid"

    monkeypatch.setattr(first_run, "validate_license", validate)
    return {"spoken": spoken, "saved": saved, "checked": checked, "cleared": cleared}


def _clipboard(monkeypatch, text: str) -> None:
    monkeypatch.setattr(first_run, "_read_clipboard", lambda: (text, 7))


def test_a_valid_copied_key_goes_to_the_keychain_and_the_clipboard_is_cleared(
    key_step, monkeypatch, tmp_path
):
    _clipboard(monkeypatch, f"  {LICENSE}\n")

    assert first_run._try_clipboard()

    assert key_step["saved"] == [LICENSE] and key_step["cleared"] == [7]
    assert LICENSE not in " ".join(key_step["spoken"])
    assert (
        not (tmp_path / "setup.json").exists()
        or LICENSE not in (tmp_path / "setup.json").read_text()
    )


def test_clipboard_text_that_is_not_a_key_is_never_sent_anywhere(key_step, monkeypatch):
    _clipboard(monkeypatch, "my bank password is hunter2")

    assert not first_run._try_clipboard()

    assert key_step["checked"] == [] and key_step["saved"] == []
    assert "hunter2" not in " ".join(key_step["spoken"])


def test_an_invalid_key_is_not_saved(key_step, monkeypatch):
    _clipboard(monkeypatch, "zoya_" + "x" * 43)

    assert not first_run._try_clipboard()

    assert key_step["saved"] == [] and key_step["spoken"] == [first_run.KEY_INVALID]


def test_crash_loop_stops_at_the_cap_within_the_window():
    window = supervisor.CRASH_WINDOW_S

    assert supervisor.should_restart([0.0, 1.0], now=2.0)
    assert not supervisor.should_restart([0.0, 1.0, 2.0], now=3.0)
    assert supervisor.should_restart([0.0, 1.0, 2.0], now=window + 1.0)


def test_the_license_check_names_zoya_so_cloudflare_does_not_refuse_it(monkeypatch):
    sent = {}

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

    def urlopen(request, timeout):
        sent.update(request.header_items())
        return Response()

    monkeypatch.setattr(config, "RELAY_URL", "https://relay.example")
    monkeypatch.setattr(first_run.urllib.request, "urlopen", urlopen)
    assert first_run.validate_license("zoya_key") == "valid"
    assert sent["User-agent"].startswith("Zoya/")
    assert sent["Authorization"] == "Bearer zoya_key"
