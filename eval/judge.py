from typing import Literal

from pydantic import BaseModel

from app.services.generation import LLMError, call_claude_structured


class Judgement(BaseModel):
    verdict: Literal["correct", "partial", "incorrect"]
    reasoning: str


def build_judge_prompt(question: str, reference_answer: str, system_answer: str) -> str:
    return f"""You are evaluating whether a system's answer is correct, given a known correct reference answer.

    Question: {question}

    Reference (correct) answer: {reference_answer}

    System's answer: {system_answer}

    Determine whether the system's answer is correct, partially correct, or incorrect, compared to the reference answer."""


def judge_answer(question: str, reference_answer: str, system_answer: str) -> dict:
    prompt = build_judge_prompt(question, reference_answer, system_answer)
    try:
        return call_claude_structured(prompt, Judgement).model_dump()
    except LLMError as e:
        return {"verdict": "error", "reasoning": str(e)}
