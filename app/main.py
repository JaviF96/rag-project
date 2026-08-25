from fastapi import FastAPI
from app.routes.documents import router

app = FastAPI()
app.include_router(router)

@app.get("/health")
def health_check():
    return {"status": "ok"}
