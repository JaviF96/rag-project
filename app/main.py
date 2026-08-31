import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app import config
from app.limiter import limiter
from app.routes.documents import router
from app.services.storage import check_connection, close_pool

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
)
log = logging.getLogger("rag")


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Crash on a misconfigured environment rather than serving traffic that
    # fails on every request. See config.require_env for the reasoning.
    config.require_env()
    log.info("Configuration validated; starting up.")
    yield
    close_pool()
    log.info("Connection pool closed.")


app = FastAPI(title="RAG Inspector", lifespan=lifespan)

app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(_, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"detail": f"Rate limit exceeded: {exc.detail}. Try again shortly."},
    )


# In development any localhost port is fine -- vite picks a new one whenever the
# default is taken. In production ALLOWED_ORIGINS is required (enforced by
# require_env), so this never silently falls back to localhost in a deploy.
origins = config.allowed_origins()
if origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
else:
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+",
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(router)


@app.get("/health")
def health_check():
    """Liveness: the process is up. Deliberately does no I/O."""
    return {"status": "ok"}


@app.get("/ready")
def readiness_check():
    """Readiness: the process can actually serve requests.

    The platform health check should point here, not at /health. A liveness
    ping that only proves the process started will happily report green while
    the database is unreachable and every request fails.
    """
    try:
        check_connection()
    except Exception as e:
        log.warning("Readiness check failed: %s", e)
        return JSONResponse(
            status_code=503, content={"status": "unavailable", "database": "unreachable"}
        )
    return {"status": "ready", "database": "ok"}
