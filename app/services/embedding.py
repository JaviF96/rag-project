import voyageai

client = voyageai.Client()

def embed_chunks(chunks:list[str]) -> list[list[float]]:
    result = client.embed(chunks, model="voyage-4", input_type="document")
    return result.embeddings

def embed_question(question:str) -> list[float]:
    result = client.embed([question], model="voyage-4", input_type="query")
    return result.embeddings[0]

def rerank_chunks(question: str, chunks: list[tuple], top_k: int = 3) -> list[tuple]:
    chunk_texts = [text for _, text in chunks]
    result = client.rerank(question, chunk_texts, model="rerank-2.5", top_k=top_k)
    return [chunks[r.index] for r in result.results]

