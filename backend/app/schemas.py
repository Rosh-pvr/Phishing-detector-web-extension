from datetime import datetime
from typing import Optional, Any, Dict, List
from pydantic import BaseModel, HttpUrl

class AnalyzeRequest(BaseModel):
    url: HttpUrl

class AnalyzeResponse(BaseModel):
    task_id: str
    status: str

class ResultResponse(BaseModel):
    task_id: str
    status: str
    url: Optional[str]
    risk_score: Optional[int]
    details: Optional[Dict[str, Any]]
    verdict: str

class HistoryItem(BaseModel):
    task_id: str
    url: str
    status: str
    risk_score: Optional[int]
    verdict: str
    created_at: Optional[datetime]

class HistoryListResponse(BaseModel):
    total: int
    items: List[HistoryItem]
