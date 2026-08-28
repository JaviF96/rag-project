from app.services.generation import call_claude, parse_json_response

from app.services.generation import call_claude, parse_json_response

def build_verification_prompt(context: str, answer: str) -> str:
    return f"""You are checking whether a generated answer is properly grounded in the given context. This is not about whether the answer is correct in some absolute sense — it's specifically about whether every claim in the answer is actually supported by the context, and whether the answer correctly identifies what the context does or doesn't contain.

    Context:
    {context}

    Generated answer:
    {answer}

    Check for two distinct problems:
    1. Unsupported claims: does the answer state anything as fact that is NOT actually present in or supported by the context?
    2. Missed information: does the answer claim the context lacks information that is actually present in the context?

    Respond with ONLY a JSON object, no other text, no markdown code fences, in exactly this format:
    {{"grounded": true, "issue": "none", "reasoning": "brief explanation"}}

    The "issue" field must be exactly one of: "unsupported_claim", "missed_information", "none\""""

def verify_answer(chunks: list[str], answer:str) -> dict:
    context = "\n\n".join(chunks)
    prompt = build_verification_prompt(context, answer)
    response_text = call_claude(prompt)
    cleaned_text = parse_json_response(response_text)
    return cleaned_text