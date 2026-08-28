import anthropic 
import json

client = anthropic.Anthropic()


def build_prompt(chunks: list[str], question: str) -> str:
    context = "\n\n".join(chunks)
    prompt = f"""
        Answer the question using only the context below.
        If the context doesn't contain enough information to answer, say so — don't guess.

        \n\n Context:\n{context}\n\nQuestion: {question}\nAnswer:"""
    
    return prompt

def call_claude(prompt: str) -> str:
    response = client.messages.create(
        model="claude-sonnet-5",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}]
    )
    for block in response.content:
        if block.type == "text":
            return block.text
    return ""

def parse_json_response(response_text: str) -> dict:
    cleaned_text = response_text.strip()
    if cleaned_text.startswith("```"):
        lines = cleaned_text.split("\n")
        cleaned_text = "\n".join(lines[1:-1])
    try:
        return json.loads(cleaned_text)
    except json.JSONDecodeError:
        return {"error": f"Failed to parse response as JSON. Raw response: {response_text}"}