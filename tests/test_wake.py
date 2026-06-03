"""Wake-phrase matching: it must fire on real wakes and stay quiet otherwise."""

import pytest

from hey_claude.wake import OpenWakeWordEngine, match_wake
from hey_claude.models import bundled_path


@pytest.mark.parametrize(
    "utterance,expected",
    [
        ("hey claude fix the failing tests", "fix the failing tests"),
        ("Hey, Claude — open the PR", "open the pr"),
        ("hi claude what's up", "what's up"),
        ("claude run the build", "run the build"),
        ("hey claude", ""),                     # wake only, command follows separately
        ("hey clyde deploy now", "deploy now"),  # tolerated mishearing
        ("hey cloud commit and push", "commit and push"),
    ],
)
def test_wake_fires(utterance, expected):
    assert match_wake(utterance) == expected


@pytest.mark.parametrize(
    "utterance",
    [
        "the weather is nice today",
        "okay so anyway",
        "let's grab lunch",
        "",
    ],
)
def test_wake_does_not_fire(utterance):
    assert match_wake(utterance) is None


def test_custom_phrase():
    assert match_wake("computer status report", "computer") == "status report"


# --- the re-trigger storm: openWakeWord's buffer keeps a wake activation alive
# across many frames, and dispatch takes seconds, so the refractory measured from
# detection expires mid-handling. reset() must clear the buffer and re-arm the
# clock so a still-elevated score can't fire again immediately. -----------------

class _FakeModel:
    """Stands in for openwakeword.model.Model: always scores a hot wake."""

    def __init__(self):
        self.reset_calls = 0

    def predict(self, frame):  # noqa: ARG002
        return {"wake": 0.99}  # every frame looks like a wake

    def reset(self):
        self.reset_calls += 1


def _engine_with_fake_model(**kw):
    # Construct against a real bundled model path (the ctor checks existence),
    # then swap in the fake so we never touch onnxruntime in a unit test.
    eng = OpenWakeWordEngine(bundled_path("hey_claude"), **kw)
    eng._model = _FakeModel()
    return eng


def test_refractory_debounces_a_hot_score():
    eng = _engine_with_fake_model(threshold=0.5, refractory_s=2.0)
    assert eng.process(None) is True        # first hot frame fires
    assert eng.process(None) is False       # within refractory: suppressed
    assert eng.process(None) is False


def test_reset_clears_buffer_and_rearms_refractory():
    eng = _engine_with_fake_model(threshold=0.5, refractory_s=2.0)
    assert eng.process(None) is True
    eng.reset()                              # what the listener does post-dispatch
    assert eng._model.reset_calls == 1       # buffer was cleared
    # And the refractory clock was restarted, so the next hot frame stays quiet
    # instead of storming a second dispatch.
    assert eng.process(None) is False
