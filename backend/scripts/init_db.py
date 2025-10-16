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

# New: ensure employment_offers table exists for workshop demos
cur.execute("""
CREATE TABLE IF NOT EXISTS employment_offers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_name TEXT,
    position TEXT,
    company TEXT,
    start_date DATE,
    end_date DATE,
    annual_salary INTEGER,
    currency TEXT,
    place_of_work TEXT,
    paid_leave_days INTEGER,
    governing_law TEXT,
    jurisdiction TEXT
)
""")

# Seed one row if empty
cur.execute("SELECT COUNT(*) FROM notes")
if cur.fetchone()[0] == 0:
    cur.execute("INSERT INTO notes (title, content) VALUES (?, ?)", ("Welcome", "Hello from the workshop DB"))

# Seed example employment_offers row if table is empty
cur.execute("SELECT COUNT(*) FROM employment_offers")
if cur.fetchone()[0] == 0:
    cur.execute(
        """
        INSERT INTO employment_offers (
            employee_name, position, company, start_date, end_date, annual_salary,
            currency, place_of_work, paid_leave_days, governing_law, jurisdiction
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "Demo Employee",
            "CTO",
            "Foundry Labs K.K.",
            "2025-11-01",
            "2026-04-30",
            6000000,
            "JPY",
            "Setagaya-ku, Tokyo (Remote)",
            10,
            "Japan",
            "Tokyo District Court",
        ),
    )

con.commit()
con.close()
print(f"Initialized DB at {DB_PATH}")
