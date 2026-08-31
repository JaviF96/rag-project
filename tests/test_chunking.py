import pytest

from app.services.chunking import chunk_text, estimate_chunk_count


def test_chunks_overlap_so_a_boundary_sentence_survives_whole():
    words = [f"w{i}" for i in range(300)]
    chunks = chunk_text(" ".join(words), chunk_size=150, overlap=40)

    # Step is chunk_size - overlap, so chunk 2 restarts 110 words in.
    assert chunks[0].split()[0] == "w0"
    assert chunks[1].split()[0] == "w110"
    # The overlap region appears in both neighbours.
    assert "w120" in chunks[0].split() and "w120" in chunks[1].split()


def test_short_text_is_a_single_chunk():
    assert len(chunk_text("only a few words here")) == 1


def test_empty_text_produces_no_chunks():
    assert chunk_text("") == []


@pytest.mark.parametrize("overlap", [150, 200])
def test_overlap_at_or_above_chunk_size_is_rejected(overlap):
    """A step of zero would loop forever; the guard turns it into a clear error."""
    with pytest.raises(ValueError, match="must be smaller than chunk_size"):
        chunk_text("some text", chunk_size=150, overlap=overlap)


def test_estimate_matches_actual_chunk_count():
    """The upload route rejects on the estimate, so it must not under-count."""
    for word_count in (0, 1, 109, 110, 111, 500, 1500):
        text = " ".join("w" for _ in range(word_count))
        assert estimate_chunk_count(text) == len(chunk_text(text)), word_count
