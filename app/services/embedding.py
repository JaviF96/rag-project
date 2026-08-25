import voyageai

client = voyageai.Client()

def embed_chunks(chunks:list[str]) -> list[list[float]]:
    result = client.embed(chunks, model="voyage-4", input_type="document")
    return result.embeddings

def embed_question(question:str) -> list[float]:
    result = client.embed([question], model="voyage-4", input_type="query")
    return result.embeddings[0]

