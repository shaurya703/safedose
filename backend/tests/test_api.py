import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import main as main_module
from app.db import Base
from app.models import NSQRow
from app.schemas import NSQRecord
from scripts.seed import load_records


@pytest.fixture(scope="module")
def client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine)
    with TestSession() as db:
        for rec in load_records():
            db.add(NSQRow.from_domain(rec))
        db.commit()

    # point the app's session factory at the in-memory test DB
    main_module.SessionLocal = TestSession
    app = main_module.create_app()
    with TestClient(app) as c:
        yield c


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200 and r.json()["records"] >= 50


def test_check_requires_input(client):
    r = client.get("/api/check")
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_error"


def test_check_real_flagged_batch(client):
    r = client.get("/api/check", params={"drug": "Adrenaline", "batch": "AD-204"})
    assert r.status_code == 200
    body = r.json()
    assert body["match_type"] == "batch_flagged"
    assert body["severity"] == "danger"
    assert body["batch_matches"]


def test_check_unknown_is_clear_but_hedged(client):
    r = client.get("/api/check", params={"drug": "Metformin XYZ", "batch": "QQ000111"})
    body = r.json()
    assert body["match_type"] == "clear"
    assert "not a guarantee" in body["detail"].lower()


def test_alerts_filter_by_category(client):
    r = client.get("/api/alerts", params={"category": "dissolution"})
    assert r.status_code == 200
    assert all(rec["failure_category"] == "dissolution" for rec in r.json()["records"])


def test_stats(client):
    r = client.get("/api/stats")
    body = r.json()
    assert body["total_records"] >= 50
    assert body["alerts_ingested"] == ["2025-03"]
    assert "dissolution" in body["by_category"]


def test_meta_has_disclaimer(client):
    assert client.get("/api/meta").json()["disclaimer"]
