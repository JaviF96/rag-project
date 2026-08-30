import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes.documents import router

app = FastAPI(title="RAG Inspector")

# In development any localhost port is fine -- vite picks a new one whenever the
# default is taken. In production set ALLOWED_ORIGINS to the real origin(s).
allowed = os.environ.get("ALLOWED_ORIGINS")
if allowed:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in allowed.split(",")],
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
    return {"status": "ok"}
