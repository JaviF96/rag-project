import uuid

import pytest

from app import config
from app.routes.documents import valid_session_id


# ------------------------------------------------------- session id checks --
# The header is client-supplied and written straight to the database, so it
# needs a bound on both shape and length. Anything malformed degrades to "no
# session" -- the caller sees only the shared demo corpus rather than an error.

def test_a_uuid_is_accepted_and_normalised():
    raw = str(uuid.uuid4())
    assert valid_session_id(raw.upper()) == raw


@pytest.mark.parametrize(
    "value",
    [
        None,
        "",
        "ephemeral",          # the old blocked-storage fallback
        "not-a-uuid",
        "../../etc/passwd",
        "' OR 1=1 --",
        "x" * 10_000,
    ],
)
def test_anything_that_is_not_a_uuid_is_rejected(value):
    assert valid_session_id(value) is None


# ------------------------------------------------------------ env checking --

REQUIRED = ("DATABASE_URL", "ANTHROPIC_API_KEY", "VOYAGE_API_KEY")


@pytest.fixture
def clean_env(monkeypatch):
    for name in REQUIRED + ("ALLOWED_ORIGINS", "ENVIRONMENT"):
        monkeypatch.delenv(name, raising=False)
    return monkeypatch


@pytest.mark.parametrize("missing", REQUIRED)
def test_startup_fails_and_names_the_missing_variable(clean_env, missing):
    """A misconfigured deploy must crash, not serve traffic that always fails."""
    for name in REQUIRED:
        clean_env.setenv(name, "set")
    clean_env.delenv(missing)

    with pytest.raises(config.ConfigError, match=missing):
        config.require_env()


def test_complete_development_env_passes(clean_env):
    for name in REQUIRED:
        clean_env.setenv(name, "set")
    config.require_env()  # must not raise


def test_production_requires_explicit_allowed_origins(clean_env):
    """Otherwise CORS silently falls back to localhost and the frontend breaks."""
    for name in REQUIRED:
        clean_env.setenv(name, "set")
    clean_env.setenv("ENVIRONMENT", "production")

    with pytest.raises(config.ConfigError, match="ALLOWED_ORIGINS"):
        config.require_env()

    clean_env.setenv("ALLOWED_ORIGINS", "https://example.com")
    config.require_env()


def test_allowed_origins_splits_and_trims(clean_env):
    clean_env.setenv("ALLOWED_ORIGINS", " https://a.com , https://b.com ")
    assert config.allowed_origins() == ["https://a.com", "https://b.com"]


def test_allowed_origins_is_none_when_unset(clean_env):
    assert config.allowed_origins() is None
