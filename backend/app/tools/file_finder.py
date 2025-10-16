from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
UPLOAD_DIR = REPO_ROOT / "uploaded_files"

class FileFinder:
    def search(self) -> list:
        try:
            files = [str(f.name) for f in UPLOAD_DIR.iterdir() if f.is_file()]
            return files
        except Exception as e:
            return [f"Effor: {e}"]