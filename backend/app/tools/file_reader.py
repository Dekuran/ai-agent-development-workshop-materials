from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
UPLOAD_DIR = REPO_ROOT / "uploaded_files"

class FileReader:
    def read(self, relative_path: str) -> str:
        p = (UPLOAD_DIR / relative_path).resolve()
        if UPLOAD_DIR not in p.parents and p != UPLOAD_DIR:
            raise ValueError("Access denied")
        return p.read_text(encoding="utf-8")
