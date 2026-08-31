"""Regression tests for the embedding batcher.

Before this fix `embed_chunks` forwarded the whole list to Voyage in one call.
The API caps a request at 128 texts, so any document longer than ~128 chunks
(roughly 25 pages) failed -- and because the upload route had no error handling
it surfaced as a bare 500. The bug went unnoticed because every document ever
ingested in testing was 1 or 13 chunks.
"""

import math

import pytest

from app.services import embedding


class FakeEmbedResult:
    def __init__(self, n):
        self.embeddings = [[0.1, 0.2, 0.3] for _ in range(n)]


class FakeVoyage:
    """Records each call and enforces the real API's batch ceiling."""

    def __init__(self, limit=embedding.EMBED_BATCH_SIZE):
        self.limit = limit
        self.batch_sizes = []

    def embed(self, texts, model=None, input_type=None):
        if len(texts) > self.limit:
            raise ValueError(f"too many texts: {len(texts)} > {self.limit}")
        self.batch_sizes.append(len(texts))
        return FakeEmbedResult(len(texts))


@pytest.fixture
def fake_client(monkeypatch):
    client = FakeVoyage()
    monkeypatch.setattr(embedding, "client", client)
    return client


@pytest.mark.parametrize("n", [0, 1, 127, 128, 129, 300, 1200])
def test_returns_one_embedding_per_chunk(fake_client, n):
    chunks = [f"chunk {i}" for i in range(n)]
    assert len(embedding.embed_chunks(chunks)) == n


@pytest.mark.parametrize("n", [1, 128, 129, 300, 1200])
def test_splits_into_batches_the_api_accepts(fake_client, n):
    embedding.embed_chunks([f"chunk {i}" for i in range(n)])
    assert len(fake_client.batch_sizes) == math.ceil(n / embedding.EMBED_BATCH_SIZE)
    assert max(fake_client.batch_sizes) <= embedding.EMBED_BATCH_SIZE


def test_a_long_document_would_have_failed_before_batching(fake_client):
    """Guards the exact shape of the original bug."""
    with pytest.raises(ValueError, match="too many texts"):
        fake_client.embed([f"chunk {i}" for i in range(300)])


def test_no_api_call_for_an_empty_document(fake_client):
    assert embedding.embed_chunks([]) == []
    assert fake_client.batch_sizes == []
