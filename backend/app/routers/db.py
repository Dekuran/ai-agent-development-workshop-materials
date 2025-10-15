from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from ..services.db import Database

router = APIRouter(prefix="/db", tags=["database"])
db = Database()

class SQLRequest(BaseModel):
    sql: str

@router.post("/query")
def query(req: SQLRequest):
    sql = req.sql.strip()
    if not sql.lower().startswith("select"):
        raise HTTPException(status_code=400, detail="Only SELECT queries are allowed")
    try:
        rows = db.query(sql)
        return {"rows": rows}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
