def chunk_text(text: str, chunk_size: int = 150, overlap: int = 40) -> list[str]:
    """Split text into overlapping word windows.

    The overlap means a sentence spanning a boundary still appears whole in one
    of the two chunks, so retrieval can't lose a fact to an unlucky cut.
    """
    # A step of zero or less would loop forever (or raise); catch the bad
    # configuration here rather than at the range() call.
    if overlap >= chunk_size:
        raise ValueError(
            f"overlap ({overlap}) must be smaller than chunk_size ({chunk_size})"
        )

    words = text.split()
    chunks = []
    for i in range(0, len(words), chunk_size - overlap):
        chunks.append(" ".join(words[i : i + chunk_size]))
    return chunks


def estimate_chunk_count(text: str, chunk_size: int = 150, overlap: int = 40) -> int:
    """How many chunks `text` would produce, without building them.

    Lets the upload route reject an oversized document before paying to embed it.
    """
    if overlap >= chunk_size:
        raise ValueError(
            f"overlap ({overlap}) must be smaller than chunk_size ({chunk_size})"
        )
    words = len(text.split())
    if words == 0:
        return 0
    step = chunk_size - overlap
    return (words + step - 1) // step
