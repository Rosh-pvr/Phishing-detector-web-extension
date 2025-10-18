from typing import Optional
import uuid

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from .schemas import (
    AnalyzeRequest,
    AnalyzeResponse,
    ResultResponse,
    HistoryListResponse,
    HistoryItem,
)
from .tasks import analyze_url_task
from .database import get_db, engine
from . import models
from sqlalchemy.orm import Session
from .config import CORS_ALLOW_ORIGINS


models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Phish Detector API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOW_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

VERDICT_SAFE_THRESHOLD = 30
VERDICT_WARNING_THRESHOLD = 70

def compute_verdict(score: Optional[int]) -> str:
    if score is None:
        return "UNKNOWN"
    if score < VERDICT_SAFE_THRESHOLD:
        return "SAFE"
    if score < VERDICT_WARNING_THRESHOLD:
        return "WARNING"
    return "PHISHING"

def apply_verdict_filter(query, verdict: str):
    verdict = verdict.upper()
    if verdict == "UNKNOWN":
        return query.filter(models.AnalysisResult.risk_score.is_(None))
    if verdict == "SAFE":
        return query.filter(models.AnalysisResult.risk_score.isnot(None)).filter(
            models.AnalysisResult.risk_score < VERDICT_SAFE_THRESHOLD
        )
    if verdict == "WARNING":
        return query.filter(models.AnalysisResult.risk_score.isnot(None)).filter(
            models.AnalysisResult.risk_score >= VERDICT_SAFE_THRESHOLD,
            models.AnalysisResult.risk_score < VERDICT_WARNING_THRESHOLD,
        )
    if verdict == "PHISHING":
        return query.filter(models.AnalysisResult.risk_score.isnot(None)).filter(
            models.AnalysisResult.risk_score >= VERDICT_WARNING_THRESHOLD
        )
    raise HTTPException(status_code=400, detail="Invalid verdict filter")

@app.get("/", include_in_schema=False)
def root():
    """Redirect visitors to the interactive API documentation."""
    return RedirectResponse(url="/docs")

@app.get("/healthz", tags=["system"], include_in_schema=False)
def healthcheck():
    """Lightweight health endpoint that callers and load balancers can use."""
    return {"status": "ok", "message": "Phish Detector API. See /docs for details."}

@app.post("/api/analyze", response_model=AnalyzeResponse)
def analyze(req: AnalyzeRequest, db: Session = Depends(get_db)):
    url_value = str(req.url)
    task_id = uuid.uuid4().hex

    row = models.AnalysisResult(
        task_id=task_id,
        url=url_value,
        status="QUEUED",
        risk_score=None,
        details={},
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    analyze_url_task.apply_async(args=[url_value], task_id=task_id)

    return AnalyzeResponse(task_id=task_id, status=row.status)

@app.get("/api/result/{task_id}", response_model=ResultResponse)
def get_result(task_id: str, db: Session = Depends(get_db)):
    result = (
        db.query(models.AnalysisResult)
        .filter(models.AnalysisResult.task_id == task_id)
        .first()
    )
    if not result:
        raise HTTPException(status_code=404, detail="Task not found")
    return ResultResponse(
        task_id=result.task_id,
        status=result.status,
        url=result.url,
        risk_score=result.risk_score,
        details=result.details,
        verdict=compute_verdict(result.risk_score),
    )

@app.get("/api/history", response_model=HistoryListResponse)
def get_history(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    verdict: Optional[str] = Query(None, description="Filter by verdict"),
    db: Session = Depends(get_db),
):
    query = db.query(models.AnalysisResult)
    if verdict:
        query = apply_verdict_filter(query, verdict)
    total = query.count()
    rows = (
        query.order_by(models.AnalysisResult.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    items = [
        HistoryItem(
            task_id=row.task_id,
            url=row.url,
            status=row.status,
            risk_score=row.risk_score,
            verdict=compute_verdict(row.risk_score),
            created_at=row.created_at,
        )
        for row in rows
    ]
    return HistoryListResponse(total=total, items=items)
