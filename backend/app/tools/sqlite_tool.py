from ..services.db import Database

class SQLiteTool:
    def __init__(self):
        self.db = Database()

    def query(self, sql: str):
        """
        Execute a read-only SELECT or PRAGMA statement and return results.
        """
        sql_lower = sql.lower().strip()
        if not (sql_lower.startswith("select") or sql_lower.startswith("pragma")):
            print(f"[SQLiteTool] query called with non-SELECT/PRAGMA sql: {sql}")
            raise ValueError("Only SELECT or PRAGMA queries are allowed in query(). Use execute() for write operations.")
        return self.db.query(sql)
    
    def exeucte(self, sql: str):
        """
        Execute a write operation (INSERT, UPDATE, DELETE, CREATE, etc.) and return a user-friendly result.
        """
        if sql.lower().strip().startswith("select"):
            print(f"[SQLiteTool] execute called with SELECT sql: {sql}")
            raise ValueError("Use query() for SELECT statements.")
        return self.db.execute(sql)

    # Backwards/forwards compatibility alias
    def execute(self, sql: str):
        """
        Alias for exeucte(sql) to tolerate name mismatches.
        """
        return self.exeucte(sql)

    def tables(self):
        """
        List all table names in the main and temp schemas.
        """
        sql = "SELECT name FROM sqlite_master WHERE type='table' UNION ALL SELECT name FROM sqlite_temp_master WHERE type='table';"
        return self.db.query(sql)