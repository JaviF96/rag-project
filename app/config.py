"""Environment and limits, resolved once at import.

Every knob the deployment needs lives here so a misconfigured environment fails
at startup with a named variable rather than at request time with a 500.
"""

import os

# --- required credentials --------------------------------------------------

REQUIRED_ENV = ("DATABASE_URL", "ANTHROPIC_API_KEY", "VOYAGE_API_KEY")


class ConfigError(RuntimeError):
    """The process cannot serve traffic with the environment as configured."""


def require_env() -> None:
    """Fail fast on a misconfigured deploy.

    Without this the app boots happily with no credentials: /health returns ok,
    the platform's health check goes green, and every real request then fails.
    Crashing at startup makes a bad deploy obvious instead of silently broken.
    """
    missing = [name for name in REQUIRED_ENV if not os.environ.get(name)]
    if missing:
        raise ConfigError(
            "Missing required environment variable(s): "
            + ", ".join(missing)
            + ". See .env.example."
        )

    # In production the browser origin must be declared explicitly. The dev
    # fallback allows any localhost port, which would silently block the real
    # frontend and surface only as an opaque CORS error in the browser.
    if is_production() and not os.environ.get("ALLOWED_ORIGINS"):
        raise ConfigError(
            "ALLOWED_ORIGINS must be set when ENVIRONMENT=production "
            "(comma-separated origins, e.g. https://example.com)."
        )


def is_production() -> bool:
    return os.environ.get("ENVIRONMENT", "development").lower() == "production"


def allowed_origins() -> list[str] | None:
    raw = os.environ.get("ALLOWED_ORIGINS")
    return [o.strip() for o in raw.split(",") if o.strip()] if raw else None


# --- ingest limits ---------------------------------------------------------

def _int_env(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


# 5 MB rather than the previous 20 MB: a 20 MB PDF is roughly 17,000 chunks and
# ~68 MB of vectors, which would exhaust a free-tier database in a few uploads.
MAX_UPLOAD_BYTES = _int_env("MAX_UPLOAD_MB", 5) * 1024 * 1024

# Checked before embedding, so an oversized document costs nothing.
MAX_CHUNKS_PER_DOCUMENT = _int_env("MAX_CHUNKS_PER_DOCUMENT", 1200)

# Ceilings per browser session, so one visitor cannot fill the database.
MAX_DOCUMENTS_PER_SESSION = _int_env("MAX_DOCUMENTS_PER_SESSION", 5)
MAX_CHUNKS_PER_SESSION = _int_env("MAX_CHUNKS_PER_SESSION", 3000)

# How long an uploaded document survives before the cleanup job removes it.
SESSION_TTL_DAYS = _int_env("SESSION_TTL_DAYS", 7)

# --- rate limits (slowapi syntax) ------------------------------------------

# /ask spends money on every call: an embedding, a rerank and two or three
# Claude calls, roughly a cent a time. /documents is rarer but heavier.
ASK_RATE_LIMIT = os.environ.get("ASK_RATE_LIMIT", "10/minute;100/day")
UPLOAD_RATE_LIMIT = os.environ.get("UPLOAD_RATE_LIMIT", "3/minute;20/day")
