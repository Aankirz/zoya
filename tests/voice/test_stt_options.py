"""L4: turbo keeps its language guard and gets the Hinglish prompt; the spotter does not."""

from zoya import voice


def test_turbo_gets_the_hinglish_prompt_and_base_en_keeps_its_own(monkeypatch):
    calls = {}

    def fake_load(repo, allowed_languages=None, min_avg_logprob=None, **options):
        calls[repo] = (allowed_languages, min_avg_logprob, options)
        return lambda samples: ""

    monkeypatch.setattr(voice, "load_whisper", fake_load)
    monkeypatch.setattr(voice, "load_smart_turn", lambda: None)
    monkeypatch.setattr(voice, "StreamingVad", lambda: None)
    voice.load_models()

    languages, logprob, options = calls[voice.STT_MODEL_REPO]
    assert languages == voice.STT_LANGUAGES and logprob == voice.MIN_AVG_LOGPROB
    assert options == {"initial_prompt": voice.HINGLISH_PROMPT}
    assert calls[voice.WAKE_MODEL][2] == {"language": "en", "initial_prompt": "Zoya"}
