"""Event Game Framework API — FastAPI application entry point."""

from fastapi import FastAPI

from app.api.v1.router import router as v1_router

app: FastAPI = FastAPI(title="Event Game Framework", version="2.0.0")
app.include_router(v1_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
