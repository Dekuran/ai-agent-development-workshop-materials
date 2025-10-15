import os
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException

router = APIRouter(tags=["upload"])

REPO_ROOT = Path(__file__).resolve().parents[2]
UPLOAD_DIR = REPO_ROOT / "uploaded_files"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

@router.post("/upload")
async def upload(file: UploadFile = File(...)):
    dest = UPLOAD_DIR / file.filename
    try:
        with dest.open("wb") as f:
            f.write(await file.read())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"filename": file.filename, "path": str(dest)}
