"""The spotter and turbo share mlx-whisper's one-model holder from two threads (L3)."""

from zoya import voice


def test_interleaved_calls_never_reload_a_model(monkeypatch):
    loads = []

    class Holder:
        model, model_path = None, None

        @classmethod
        def get_model(cls, path, dtype):
            loads.append(path)
            return f"loaded {path}"

    monkeypatch.setattr(voice, "_LOADED_WHISPERS", {"base": "BASE", "turbo": "TURBO"})
    voice._hold_every_model(Holder)
    voice._hold_every_model(Holder)

    got = [Holder.get_model(path, None) for path in ("base", "turbo", "base", "turbo")]

    assert got == ["BASE", "TURBO", "BASE", "TURBO"]
    assert loads == []
    assert Holder.get_model("other", None) == "loaded other"
