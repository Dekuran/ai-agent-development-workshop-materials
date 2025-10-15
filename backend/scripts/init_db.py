from pathlib import Path
import sqlite3

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "app.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

con = sqlite3.connect(DB_PATH)
cur = con.cursor()
cur.execute("""
CREATE TABLE IF NOT EXISTS notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    content TEXT NOT NULL
)
""")
# Seed one row if empty
cur.execute("SELECT COUNT(*) FROM notes")
if cur.fetchone()[0] == 0:
    cur.execute("INSERT INTO notes (title, content) VALUES (?, ?)", ("Welcome", "Hello from the workshop DB"))
con.commit()
con.close()
print(f"Initialized DB at {DB_PATH}")
