
def score_retrieval(retrieved_indexes: list, correct_indexes: list) -> dict:
    """Did retrieval surface the chunks the answer actually needs, and where?

    Reports full recall plus each correct chunk's 1-based position, and MRR so
    a near-miss (correct chunk at rank 3) scores differently from a total miss.
    """
    positions = {}
    for correct in correct_indexes:
        if correct in retrieved_indexes:
            positions[correct] = retrieved_indexes.index(correct) + 1
        else:
            positions[correct] = None

    hits = [p for p in positions.values() if p is not None]
    return {
        "full_recall": set(correct_indexes).issubset(set(retrieved_indexes)),
        "recall": len(hits) / len(correct_indexes) if correct_indexes else 0.0,
        "mrr": 1 / min(hits) if hits else 0.0,
        "positions": positions,
    }
