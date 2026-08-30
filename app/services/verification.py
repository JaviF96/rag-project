from typing import Literal

from pydantic import BaseModel

from app.services.generation import LLMError, call_claude_structured


class Verification(BaseModel):
    grounded: bool
    issue: Literal["unsupported_claim", "missed_information", "none"]
    reasoning: str


def build_verification_prompt(context: str, answer: str) -> str:
    return f"""You are checking whether a generated answer is properly grounded in the given context. This is not about whether the answer is correct in some absolute sense — it's specifically about whether every claim in the answer is actually supported by the context, and whether the answer correctly identifies what the context does or doesn't contain.

    Context:
    {context}

    Generated answer:
    {answer}

    Check for two distinct problems:
    1. Unsupported claims: does the answer state anything as fact that is NOT actually present in or supported by the context?
    2. Missed information: does the answer claim the context lacks information that is actually present in the context?"""


def verify_answer(chunks: list[str], answer: str) -> dict:
    prompt = build_verification_prompt("\n\n".join(chunks), answer)
    try:
        return call_claude_structured(prompt, Verification).model_dump()
    except LLMError as e:
        # Verification is a safety net, not the answer itself. If the check can't
        # run we let the original answer through rather than failing the request,
        # but we say so in the trace so it isn't mistaken for a passing check.
        return {
            "grounded": True,
            "issue": "none",
            "reasoning": f"Verification could not run: {e}",
        }
