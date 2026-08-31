"""Rate limiting.

`/ask` spends real money on every call (an embedding, a rerank and two or three
Claude calls) and `/documents` spends on embeddings plus permanent storage.
Both are unauthenticated, so without a limit a single loop can run up an
unbounded bill. Limits are keyed by client IP and held in memory, which is
correct for a single-instance deployment; a multi-instance setup would need a
shared Redis backend (`storage_uri`).
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
