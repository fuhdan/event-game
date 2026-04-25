"""Event Game Framework API — FastAPI application entry point."""

from fastapi import FastAPI

app: FastAPI = FastAPI(title="Event Game Framework", version="2.0.0")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
