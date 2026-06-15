import datetime
import os
from collections import Counter

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import func, select

from .db import SessionLocal, engine
from .engine import check
from .models import NSQRow
from .schemas import CheckResult, NSQRecord, Stats

DISCLAIMER = (
    "SafeDose is an independent tool that surfaces CDSCO's published "
    "Not-of-Standard-Quality (NSQ) alerts. It is not a government service and "
    "is not medical advice. 'Not found' does not mean a medicine is safe — our "
    "dataset is a snapshot. Always confirm on cdsco.gov.in and consult a "
    "pharmacist or doctor."
)

CORS_ORIGINS = [
    o.strip() for o in os.environ.get(
        "CORS_ORIGINS", "http://localhost:5173,http://localhost:3000"
    ).split(",") if o.strip()
]


def load_records() -> list[NSQRecord]:
    with SessionLocal() as db:
        return [row.to_domain() for row in db.scalars(select(NSQRow))]


def create_app() -> FastAPI:
    app = FastAPI(title="SafeDose API", version="1.0.0")
    app.add_middleware(
        CORSMiddleware, allow_origins=CORS_ORIGINS,
        allow_methods=["*"], allow_headers=["*"],
    )

    @app.exception_handler(HTTPException)
    async def http_err(request: Request, exc: HTTPException):
        code = {404: "not_found", 422: "validation_error"}.get(
            exc.status_code, "request_error"
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": code, "message": str(exc.detail)}},
        )

    @app.exception_handler(RequestValidationError)
    async def val_err(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={"error": {"code": "validation_error", "message": "Invalid request",
                               "details": [
                                   {"loc": list(e.get("loc", [])), "msg": e.get("msg")}
                                   for e in exc.errors()
                               ]}},
        )

    @app.get("/api/health")
    def health():
        with SessionLocal() as db:
            n = db.scalar(select(func.count()).select_from(NSQRow))
        return {"status": "ok", "records": n}

    @app.get("/api/check", response_model=CheckResult)
    def check_endpoint(
        drug: str | None = Query(default=None, max_length=200),
        batch: str | None = Query(default=None, max_length=120),
    ):
        if not (drug or "").strip() and not (batch or "").strip():
            raise HTTPException(422, "Provide a medicine name and/or a batch number")
        records = load_records()
        periods = sorted({r.alert_period for r in records})
        label = _period_label(periods)
        return check(records, drug, batch, alerts_count=len(periods), dataset_period=label)

    @app.get("/api/alerts")
    def list_alerts(
        category: str | None = None,
        spurious: bool | None = None,
        q: str | None = Query(default=None, max_length=120),
        limit: int = Query(default=100, le=500),
    ):
        records = load_records()
        if category:
            records = [r for r in records if r.failure_category.value == category]
        if spurious is not None:
            records = [r for r in records if r.is_spurious == spurious]
        if q:
            needle = q.lower()
            records = [r for r in records
                       if needle in r.drug_name.lower()
                       or needle in (r.manufacturer or "").lower()]
        records.sort(key=lambda r: (not r.is_spurious, r.drug_name.lower()))
        return {"count": len(records), "records": records[:limit]}

    @app.get("/api/stats", response_model=Stats)
    def stats():
        records = load_records()
        periods = sorted({r.alert_period for r in records})
        return Stats(
            total_records=len(records),
            spurious_count=sum(1 for r in records if r.is_spurious),
            distinct_drugs=len({r.drug_name.lower() for r in records}),
            distinct_manufacturers=len({(r.manufacturer or "").lower() for r in records if r.manufacturer}),
            alerts_ingested=periods,
            last_alert_period=periods[-1] if periods else None,
            by_category=dict(Counter(r.failure_category.value for r in records)),
            generated_on=datetime.date.today(),
        )

    @app.get("/api/meta")
    def meta():
        return {"disclaimer": DISCLAIMER}

    return app


def _period_label(periods: list[str]) -> str:
    if not periods:
        return "no alerts loaded"
    if len(periods) == 1:
        return f"CDSCO NSQ alert {periods[0]}"
    return f"CDSCO NSQ alerts {periods[0]} to {periods[-1]}"


app = create_app()
