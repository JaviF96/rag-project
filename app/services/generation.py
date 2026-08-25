import anthropic 

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
    return response.content[0].text