import json
from app.services.generation import call_claude, parse_json_response


def build_judge_prompt(question: str, reference_answer: str, system_answer: str) -> str:
    return f"""You are evaluating whether a system's answer is correct, given a known correct reference answer.

    Question: {question}

    Reference (correct) answer: {reference_answer}

    System's answer: {system_answer}

    Determine whether the system's answer is correct, partially correct, or incorrect, compared to the reference answer. Respond with ONLY a JSON object, no other text, no markdown code fences, in exactly this format:
    {{"verdict": "correct", "reasoning": "brief explanation"}}

    The verdict must be exactly one of: "correct", "partial", "incorrect\""""

def judge_answer(question: str, reference_answer: str, system_answer: str) -> dict:
    prompt = build_judge_prompt(question, reference_answer, system_answer)
    response_text = call_claude(prompt)
    
    cleaned_text = parse_json_response(response_text)

    try:
        return json.loads(cleaned_text)
    except json.JSONDecodeError:
        return {"verdict": "error", "reasoning": f"Failed to parse JSON from the model's response. Raw response: {cleaned_text}"}