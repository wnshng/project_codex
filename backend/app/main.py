from __future__ import annotations

import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.analyze import router as ai_router

load_dotenv()

app = FastAPI(title="AI Smart Closet API", version="0.1.0")

origins = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:8081").split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(ai_router)
