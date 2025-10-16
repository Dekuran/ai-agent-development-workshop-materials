from pathlib import Path
import sqlite3

REPO_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = REPO_ROOT / "data" / "app.db"


class Database:
    def execute(self, sql: str):
        """
        Execute a write operation (INSERT, UPDATE, DELETE, CREATE TABLE, etc.)
        and return a structured result dict for tool consumption.
        """
        con = sqlite3.connect(self.path)
        try:
            cur = con.execute(sql)
            con.commit()

            sql_lower = sql.strip().lower()
            action = (
                "insert" if sql_lower.startswith("insert") else
                "update" if sql_lower.startswith("update") else
                "delete" if sql_lower.startswith("delete") else
                "create_table" if sql_lower.startswith("create table") else
                "drop_table" if sql_lower.startswith("drop table") else
                "statement"
            )
            return {
                "ok": True,
                "action": action,
                "last_row_id": getattr(cur, "lastrowid", None),
                "rowcount": getattr(cur, "rowcount", -1),
                "message": (
                    "Row inserted." if action == "insert" else
                    "Rows updated." if action == "update" else
                    "Rows deleted." if action == "delete" else
                    "Table created successfully." if action == "create_table" else
                    "Table dropped successfully." if action == "drop_table" else
                    "Statement executed."
                )
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}
        finally:
            con.close()

    def __init__(self, path: Path = DB_PATH):
        self.path = str(path.resolve())
        print(f"[Database] Using SQLite DB path: {self.path}")

    def query(self, sql: str):
        con = sqlite3.connect(self.path)
        con.row_factory = sqlite3.Row
        try:
            cur = con.execute(sql)
            rows = [dict(r) for r in cur.fetchall()]
            if not rows:
                return "No results found."

            # Pretty-print as markdown table if possible
            headers = rows[0].keys() if rows else []
            table = "| " + " | ".join(headers) + " |\n"
            table += "| " + "|".join(["---"] * len(headers)) + " |\n"
            for row in rows:
                table += "| " + " | ".join(str(row[h]) for h in headers) + " |\n"
            return table
        except Exception as e:
            return f"Error: {str(e)}"
        finally:
            con.close()
