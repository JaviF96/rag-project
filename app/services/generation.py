import anthropic
from pydantic import BaseModel

MODEL = "claude-sonnet-5"

# The SDK default timeout is 10 minutes, which is far too long to leave a user
# waiting on an interactive request. max_retries covers 429/5xx/connection errors
# with exponential backoff.
client = anthropic.Anthropic(timeout=60.0, max_retries=3)


class LLMError(RuntimeError):
    """Claude could not be reached, or returned an unusable response."""


def build_prompt(chunks: list[str], question: str) -> str:
    context = "\n\n".join(chunks)
    return f"""Answer the question using only the context below.
If the context doesn't contain enough information to answer, say so — don't guess.

Context:
{context}

Question: {question}
Answer:"""


def _call(create, **kwargs):
    """Run an SDK call, translating API failures into LLMError."""
    try:
        return create(model=MODEL, max_tokens=1024, **kwargs)
    except anthropic.AuthenticationError as e:
        raise LLMError("Claude rejected the API key — check ANTHROPIC_API_KEY.") from e
    except anthropic.RateLimitError as e:
        raise LLMError("Rate limited by the Claude API; try again shortly.") from e
    except anthropic.APIStatusError as e:
        raise LLMError(f"Claude returned {e.status_code}: {e.message}") from e
    except anthropic.APIConnectionError as e:
        raise LLMError("Could not reach the Claude API.") from e


def call_claude(prompt: str) -> str:
    return call_claude_detailed(prompt)["text"]


def call_claude_detailed(prompt: str) -> dict:
    """Generate, returning the text alongside the token usage.

    The input token count comes back on the response for free. Calling
    count_tokens separately would be a second network round trip -- about 250ms
    on a 5s request -- purely to display a number the response already carries,
    and this count is the one actually billed.
    """
    response = _call(client.messages.create, messages=[{"role": "user", "content": prompt}])
    text = next((b.text for b in response.content if b.type == "text"), "")
    return {
        "text": text,
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
    }


def call_claude_structured(prompt: str, output_format: type[BaseModel]) -> BaseModel:
    """Ask Claude for a response constrained to output_format's schema.

    The API enforces the schema server-side, so the result is always a valid
    instance of output_format — there is no parse step that can fail.
    """
    response = _call(
        client.messages.parse,
        messages=[{"role": "user", "content": prompt}],
        output_format=output_format,
    )
    if response.parsed_output is None:
        raise LLMError(f"Claude returned no structured output (stop_reason={response.stop_reason}).")
    return response.parsed_output
