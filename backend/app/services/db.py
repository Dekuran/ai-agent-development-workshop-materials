from pathlib import Path
import sqlite3

REPO_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = REPO_ROOT / "backend" / "data" / "app.db"

class Database:
    def __init__(self, path: Path = DB_PATH):
        self.path = str(path)

    def query(self, sql: str):
        con = sqlite3.connect(self.path)
        con.row_factory = sqlite3.Row
        try:
            cur = con.execute(sql)
            rows = [dict(r) for r in cur.fetchall()]
            return rows
        finally:
            con.close()
