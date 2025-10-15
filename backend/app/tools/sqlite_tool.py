from ..services.db import Database

class SQLiteTool:
    def __init__(self):
        self.db = Database()

    def query(self, sql: str):
        if not sql.lower().strip().startswith("select"):
            raise ValueError("Only read-only queries are allowed")
        return self.db.query(sql)
