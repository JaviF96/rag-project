
def score_retrieval(retrieved_ids: list, correct_ids: list) -> dict:
    positions = {}
    for correct_id in correct_ids:
        if correct_id in retrieved_ids:
            positions[correct_id] = retrieved_ids.index(correct_id) + 1
        else:
            positions[correct_id] = None

    full_recall = set(correct_ids).issubset(set(retrieved_ids))

    return {
        "full_recall": full_recall,
        "positions": positions
    }