from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from repo root .env for local runs
# This complements backend/run_backend.sh which also exports .env before launching.
load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=True)
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import chat, upload, db, health

def get_cors_origins():
    origins = os.getenv("BACKEND_CORS_ORIGINS", "")
    if not origins:
        return ["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:8501"]
    return [o.strip() for o in origins.split(",") if o.strip()]

app = FastAPI(title="Multi-Agent Workshop API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(upload.router)
app.include_router(db.router)
app.include_router(chat.router)
