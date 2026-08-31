"""Every failure of the verification step must be survivable.

The original audit found that a malformed verifier response took down the whole
request. That was fixed by moving to structured outputs -- but structured
outputs only guarantee the *shape* of a completed response. If generation stops
at max_tokens the JSON is truncated and `messages.parse` raises a pydantic
ValidationError, which reintroduced the same 500 by a different route (observed
live: the verifier ran to the token limit emitting repeated `]}`).

These tests pin every failure mode to "the answer still gets returned".
"""

from typing import Literal

import pytest
from pydantic import BaseModel, ValidationError

from app.services import generation, verification
from app.services.generation import LLMError


class Shape(BaseModel):
    grounded: bool
    issue: Literal["unsupported_claim", "missed_information", "none"]
    reasoning: str


def test_truncated_json_becomes_llmerror_not_a_crash(monkeypatch):
    def boom(**kwargs):
        raise ValidationError.from_exception_data("Shape", [])

    monkeypatch.setattr(generation.client.messages, "parse", boom)
    with pytest.raises(LLMError, match="truncated or unparseable"):
        generation.call_claude_structured("prompt", Shape)


def test_hitting_max_tokens_becomes_llmerror(monkeypatch):
    class Response:
        parsed_output = Shape(grounded=True, issue="none", reasoning="x")
        stop_reason = "max_tokens"

    monkeypatch.setattr(generation.client.messages, "parse", lambda **k: Response())
    with pytest.raises(LLMError, match="cut off at max_tokens"):
        generation.call_claude_structured("prompt", Shape)


def test_missing_structured_output_becomes_llmerror(monkeypatch):
    class Response:
        parsed_output = None
        stop_reason = "refusal"

    monkeypatch.setattr(generation.client.messages, "parse", lambda **k: Response())
    with pytest.raises(LLMError, match="no structured output"):
        generation.call_claude_structured("prompt", Shape)


def test_verification_fails_open_so_the_answer_still_reaches_the_user(monkeypatch):
    """Verification is a safety net over an answer we already have.

    If the net cannot be checked, returning the answer beats returning nothing --
    and the trace says so explicitly rather than implying the check passed.
    """
    def fail(*a, **k):
        raise LLMError("Claude's structured response was truncated.")

    monkeypatch.setattr(verification, "call_claude_structured", fail)
    result = verification.verify_answer(["some context"], "an answer")

    assert result["grounded"] is True
    assert result["issue"] == "none"
    assert "could not run" in result["reasoning"].lower()


def test_a_successful_verification_passes_through(monkeypatch):
    monkeypatch.setattr(
        verification,
        "call_claude_structured",
        lambda *a, **k: verification.Verification(
            grounded=False, issue="unsupported_claim", reasoning="made it up"
        ),
    )
    result = verification.verify_answer(["ctx"], "ans")

    assert result == {
        "grounded": False,
        "issue": "unsupported_claim",
        "reasoning": "made it up",
    }
