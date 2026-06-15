"""Load parsed NSQ records (data/nsq_records.json) into the database.

Idempotent: upserts by record id and prunes records no longer present, so
re-running after ingesting a new monthly alert keeps the table in sync.

    python -m scripts.seed
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.exc import OperationalError  # noqa: E402

from app.db import Base, SessionLocal, engine  # noqa: E402
from app.models import NSQRow  # noqa: E402
from app.schemas import NSQRecord  # noqa: E402

DATA = Path(__file__).resolve().parents[1] / "data" / "nsq_records.json"


def load_records() -> list[NSQRecord]:
    raw = json.loads(DATA.read_text())
    return [NSQRecord.model_validate(r) for r in raw]  # validates the dataset


def wait_for_db(retries: int = 30, delay: float = 1.0) -> None:
    for attempt in range(retries):
        try:
            with engine.connect():
                return
        except OperationalError:
            if attempt == retries - 1:
                raise
            time.sleep(delay)


def seed() -> int:
    records = load_records()
    wait_for_db()
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        existing = {r.id for r in db.scalars(select(NSQRow))}
        for rec in records:
            db.merge(NSQRow.from_domain(rec))
        for stale in existing - {r.id for r in records}:
            db.delete(db.get(NSQRow, stale))
        db.commit()
    print(f"seeded {len(records)} NSQ records")
    return 0


if __name__ == "__main__":
    raise SystemExit(seed())
