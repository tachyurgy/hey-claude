"""Wake-phrase matching: it must fire on real wakes and stay quiet otherwise."""

import pytest

from hey_claude.wake import match_wake


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
