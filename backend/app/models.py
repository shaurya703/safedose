from sqlalchemy import Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base
from .schemas import NSQRecord


class NSQRow(Base):
    __tablename__ = "nsq_records"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    drug_name: Mapped[str] = mapped_column(Text, nullable=False)
    batch_no: Mapped[str] = mapped_column(String(120), nullable=False)
    batch_no_normalized: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    manufacturer: Mapped[str | None] = mapped_column(Text, nullable=True)
    mfg_date: Mapped[str | None] = mapped_column(String(20), nullable=True)
    expiry_date: Mapped[str | None] = mapped_column(String(20), nullable=True)
    failure_reason: Mapped[str] = mapped_column(Text, nullable=False)
    failure_category: Mapped[str] = mapped_column(String(20), index=True, nullable=False)
    is_spurious: Mapped[bool] = mapped_column(Boolean, index=True, nullable=False)
    tested_by: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_alert: Mapped[str] = mapped_column(String(80), nullable=False)
    source_url: Mapped[str] = mapped_column(String(500), nullable=False)
    alert_period: Mapped[str] = mapped_column(String(10), index=True, nullable=False)

    def to_domain(self) -> NSQRecord:
        return NSQRecord.model_validate(
            {c.name: getattr(self, c.name) for c in self.__table__.columns}
        )

    @classmethod
    def from_domain(cls, r: NSQRecord) -> "NSQRow":
        return cls(**r.model_dump())
