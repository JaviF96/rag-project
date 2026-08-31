from app.services.storage import _VISIBLE, _scope, combine_with_rrf
from eval.scoring import score_retrieval


def chunk(chunk_id, rank, **extra):
    return {
        "chunk_id": chunk_id,
        "document_id": "doc",
        "chunk_index": chunk_id,
        "text": f"text {chunk_id}",
        "rank": rank,
        **extra,
    }


# --------------------------------------------------------------- RRF fusion --

def test_a_chunk_found_by_both_searches_outranks_one_found_by_either():
    """The whole point of fusion: agreement between the two searches wins."""
    vector = [chunk(1, 1), chunk(2, 2)]
    keyword = [chunk(2, 1), chunk(3, 2)]

    fused = combine_with_rrf(vector, keyword, k=60)
    by_id = {c["chunk_id"]: c for c in fused}

    assert by_id[2]["found_by_both"] is True
    assert by_id[1]["found_by_both"] is False
    assert fused[0]["chunk_id"] == 2


def test_contributions_are_one_over_k_plus_rank():
    fused = combine_with_rrf([chunk(1, 1)], [chunk(1, 3)], k=60)
    entry = fused[0]

    assert entry["vector_contribution"] == 1 / 61
    assert entry["keyword_contribution"] == 1 / 63
    assert entry["score"] == 1 / 61 + 1 / 63


def test_a_chunk_missing_from_a_list_contributes_nothing_from_it():
    fused = combine_with_rrf([chunk(1, 1)], [], k=60)
    entry = fused[0]

    assert entry["keyword_rank"] is None
    assert entry["keyword_contribution"] == 0.0
    assert entry["found_by_both"] is False


def test_empty_inputs_produce_no_candidates():
    assert combine_with_rrf([], [], k=60) == []


def test_results_are_truncated_and_ranked():
    vector = [chunk(i, i) for i in range(1, 11)]
    fused = combine_with_rrf(vector, [], k=60, top_k=3)

    assert len(fused) == 3
    assert [c["rank"] for c in fused] == [1, 2, 3]


# ------------------------------------------------------------ scope clause --

def test_scope_without_a_document_only_checks_session_visibility():
    where, params = _scope(None)
    assert where == _VISIBLE
    assert params == []


def test_scope_with_a_document_still_enforces_session_visibility():
    """Passing someone else's document_id must match nothing, not leak it."""
    where, params = _scope("doc-123")
    assert _VISIBLE in where
    assert "document_id = %s" in where
    assert params == ["doc-123"]


# ---------------------------------------------------------------- scoring --

def test_full_recall_and_positions():
    result = score_retrieval([10, 3, 7], [3, 10])
    assert result["full_recall"] is True
    assert result["recall"] == 1.0
    assert result["mrr"] == 1.0
    assert result["positions"] == {3: 2, 10: 1}


def test_partial_recall_scores_between_zero_and_one():
    result = score_retrieval([10, 5], [3, 10])
    assert result["full_recall"] is False
    assert result["recall"] == 0.5
    assert result["mrr"] == 1.0


def test_total_miss_scores_zero():
    result = score_retrieval([1, 2], [3, 10])
    assert result["recall"] == 0.0
    assert result["mrr"] == 0.0
    assert result["positions"] == {3: None, 10: None}
