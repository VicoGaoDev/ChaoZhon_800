from sqlalchemy import Column, DateTime, Integer, String, Text, func

from app.database import Base


class PaymentReconcileScanRun(Base):
    __tablename__ = "payment_reconcile_scan_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    status = Column(String(20), nullable=False, default="running", server_default="running", index=True)
    duration_seconds = Column(Integer, nullable=False, default=60, server_default="60")
    scanned_count = Column(Integer, nullable=False, default=0, server_default="0")
    paid_detected_count = Column(Integer, nullable=False, default=0, server_default="0")
    credited_count = Column(Integer, nullable=False, default=0, server_default="0")
    event_payload = Column(Text, nullable=True)
    started_at = Column(DateTime, nullable=False)
    active_until = Column(DateTime, nullable=False, index=True)
    finished_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
