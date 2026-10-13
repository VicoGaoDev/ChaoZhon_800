from __future__ import annotations

import logging
import json
import threading
from datetime import datetime, time, timedelta

from fastapi import HTTPException
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal, engine
from app.models.payment_order import PaymentOrder
from app.models.payment_reconcile_scan_run import PaymentReconcileScanRun
from app.services.payment_service import (
    ALIPAY_QUERYABLE_STATUSES,
    ALIPAY_TRADE_SUCCESS_STATUSES,
    get_payment_order_by_order_no,
    sync_payment_order_from_alipay,
)
from app.utils.datetime_utils import now_local

logger = logging.getLogger(__name__)

MAX_RECONCILE_BATCH_SIZE = 50
LOCK_NAME = "alipay_payment_reconcile"

_stop_event = threading.Event()
_wake_event = threading.Event()
_thread: threading.Thread | None = None
_thread_lock = threading.Lock()
_manual_until_at: datetime | None = None
_manual_run_id: int | None = None


def start_payment_reconcile_scheduler() -> None:
    if not settings.ALIPAY_RECONCILE_ENABLED:
        logger.info("Alipay payment reconcile scheduler disabled")
        return
    if not _has_alipay_query_config():
        logger.warning("Alipay payment reconcile scheduler disabled: Alipay query config is incomplete")
        return
    if not _is_schema_ready():
        logger.error(
            "Alipay payment reconcile scheduler disabled: run 2026-10-09-001__add-payment-order-reconcile-until.sql first"
        )
        return

    global _thread
    with _thread_lock:
        if _thread is not None and _thread.is_alive():
            return
        _stop_event.clear()
        _wake_event.set()
        _thread = threading.Thread(target=_loop, name="payment-reconcile-scheduler", daemon=True)
        _thread.start()
        logger.info("Alipay payment reconcile scheduler started")


def notify_payment_reconcile_scheduler() -> None:
    _wake_event.set()


def trigger_manual_payment_reconcile(duration_seconds: int = 60) -> dict:
    global _manual_until_at, _manual_run_id
    started_at = now_local()
    run_id = _create_manual_scan_run(started_at=started_at, active_until=started_at, duration_seconds=0)
    with _thread_lock:
        _manual_until_at = started_at + timedelta(seconds=1)
        _manual_run_id = run_id
    try:
        run_payment_reconcile_once(started_at)
    finally:
        _finish_manual_run(run_id, now_local())
        with _thread_lock:
            if _manual_run_id == run_id:
                _manual_run_id = None
                _manual_until_at = None
    return get_manual_payment_reconcile_status(run_id)


def stop_payment_reconcile_scheduler(timeout_seconds: float | None = None) -> None:
    _stop_event.set()
    _wake_event.set()
    thread = _thread
    if thread is not None and thread.is_alive():
        timeout = timeout_seconds
        if timeout is None:
            timeout = max(int(settings.ALIPAY_RECONCILE_INTERVAL_SECONDS or 0), 1) + 5
        thread.join(timeout=timeout)
        if thread.is_alive():
            logger.error("Alipay payment reconcile scheduler did not stop within %.1f seconds", timeout)


def _has_alipay_query_config() -> bool:
    return all(
        (
            (settings.ALIPAY_APP_ID or "").strip(),
            (settings.ALIPAY_GATEWAY or "").strip(),
            (settings.ALIPAY_PRIVATE_KEY or "").strip(),
            (settings.ALIPAY_SIGN_TYPE or "").strip(),
            (settings.ALIPAY_PUBLIC_KEY or "").strip(),
        )
    )


def _is_schema_ready() -> bool:
    try:
        inspector = inspect(engine)
        table_names = set(inspector.get_table_names())
        if "payment_orders" not in table_names or "payment_reconcile_scan_runs" not in table_names:
            return False
        columns = {column["name"] for column in inspector.get_columns("payment_orders")}
        run_columns = {column["name"] for column in inspector.get_columns("payment_reconcile_scan_runs")}
        return {"order_no", "status", "reconcile_until_at"}.issubset(columns) and {
            "id",
            "status",
            "scanned_count",
            "paid_detected_count",
            "credited_count",
            "event_payload",
            "active_until",
        }.issubset(run_columns)
    except Exception:
        logger.exception("Failed to validate payment_orders reconciliation schema")
        return False


def _loop() -> None:
    interval_seconds = max(int(settings.ALIPAY_RECONCILE_INTERVAL_SECONDS or 0), 1)
    wait_seconds: float | None = 0.0
    while not _stop_event.is_set():
        if wait_seconds is None:
            _wake_event.wait()
        elif wait_seconds > 0:
            _wake_event.wait(wait_seconds)
        _wake_event.clear()
        if _stop_event.is_set():
            break
        try:
            scanned_count = run_payment_reconcile_once()
        except Exception:
            logger.exception("Alipay payment reconcile tick failed")
            scanned_count = 0
        wait_seconds = interval_seconds if scanned_count > 0 else None


def run_payment_reconcile_once(reference_time: datetime | None = None) -> int:
    if not settings.ALIPAY_RECONCILE_ENABLED or not _has_alipay_query_config():
        return 0

    moment = reference_time or now_local()
    with engine.connect() as conn:
        acquired = conn.execute(text("SELECT GET_LOCK(:n, 0)"), {"n": LOCK_NAME}).scalar()
        if acquired != 1:
            logger.debug("Skip Alipay payment reconcile tick; another worker holds the lock")
            return 0
        try:
            return _run_payment_reconcile_locked(moment)
        finally:
            try:
                conn.execute(text("SELECT RELEASE_LOCK(:n)"), {"n": LOCK_NAME})
            except Exception:
                logger.exception("Failed to release Alipay payment reconcile lock")


def _run_payment_reconcile_locked(moment: datetime) -> int:
    day_start = datetime.combine(moment.date(), time.min)
    db = SessionLocal()
    try:
        query = db.query(PaymentOrder.order_no).filter(
            PaymentOrder.status.in_(tuple(ALIPAY_QUERYABLE_STATUSES)),
            PaymentOrder.reconcile_until_at.isnot(None),
            PaymentOrder.created_at >= day_start,
        )
        if not is_manual_payment_reconcile_active(moment):
            query = query.filter(PaymentOrder.reconcile_until_at >= moment)
        order_nos = [
            row[0]
            for row in (
                query
                .order_by(PaymentOrder.created_at.asc(), PaymentOrder.id.asc())
                .limit(MAX_RECONCILE_BATCH_SIZE)
                .all()
            )
        ]
    finally:
        db.close()

    events: list[dict] = []
    for order_no in order_nos:
        event = _sync_one_order(order_no, moment)
        if event:
            events.append(event)
    _append_manual_scan_events(events, scanned_count=len(order_nos), moment=moment)
    synced_count = sum(1 for event in events if event.get("credited"))
    if order_nos:
        logger.info("Alipay payment reconcile tick finished: scanned=%s synced=%s", len(order_nos), synced_count)
    return len(order_nos)


def is_manual_payment_reconcile_active(moment: datetime | None = None) -> bool:
    current = moment or now_local()
    with _thread_lock:
        return _manual_until_at is not None and _manual_until_at >= current


def _current_manual_run_id() -> int | None:
    with _thread_lock:
        return _manual_run_id


def _create_manual_scan_run(*, started_at: datetime, active_until: datetime, duration_seconds: int) -> int:
    db = SessionLocal()
    try:
        run = PaymentReconcileScanRun(
            status="running",
            duration_seconds=duration_seconds,
            scanned_count=0,
            paid_detected_count=0,
            credited_count=0,
            event_payload="[]",
            started_at=started_at,
            active_until=active_until,
        )
        db.add(run)
        db.commit()
        return int(run.id)
    finally:
        db.close()


def get_manual_payment_reconcile_status(run_id: int | None = None) -> dict:
    db = SessionLocal()
    try:
        query = db.query(PaymentReconcileScanRun)
        if run_id is not None:
            run = query.filter(PaymentReconcileScanRun.id == run_id).first()
        else:
            run = query.order_by(PaymentReconcileScanRun.id.desc()).first()
        if not run:
            return {
                "id": None,
                "status": "idle",
                "duration_seconds": 0,
                "scanned_count": 0,
                "paid_detected_count": 0,
                "credited_count": 0,
                "events": [],
            }
        _finish_run_if_expired(db, run, now_local())
        events = _parse_event_payload(run.event_payload)
        return {
            "id": int(run.id),
            "status": run.status,
            "duration_seconds": int(run.duration_seconds or 0),
            "scanned_count": int(run.scanned_count or 0),
            "paid_detected_count": int(run.paid_detected_count or 0),
            "credited_count": int(run.credited_count or 0),
            "started_at": run.started_at,
            "active_until": run.active_until,
            "finished_at": run.finished_at,
            "events": events,
        }
    finally:
        db.close()


def _append_manual_scan_events(events: list[dict], *, scanned_count: int, moment: datetime) -> None:
    run_id = _current_manual_run_id()
    if run_id is None or scanned_count <= 0:
        _finish_manual_run_if_expired(moment)
        return

    db = SessionLocal()
    try:
        run = db.query(PaymentReconcileScanRun).filter(PaymentReconcileScanRun.id == run_id).first()
        if not run:
            return
        existing_events = _parse_event_payload(run.event_payload)
        next_events = (existing_events + events)[-100:]
        run.scanned_count = int(run.scanned_count or 0) + scanned_count
        run.paid_detected_count = int(run.paid_detected_count or 0) + sum(
            1 for event in events if event.get("paid_detected")
        )
        run.credited_count = int(run.credited_count or 0) + sum(1 for event in events if event.get("credited"))
        run.event_payload = json.dumps(next_events, ensure_ascii=False, separators=(",", ":"))
        _finish_run_if_expired(db, run, moment)
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Failed to append manual payment reconcile scan events")
    finally:
        db.close()


def _finish_manual_run_if_expired(moment: datetime) -> None:
    run_id = _current_manual_run_id()
    if run_id is None or is_manual_payment_reconcile_active(moment):
        return
    _finish_manual_run(run_id, moment)


def _finish_manual_run(run_id: int, moment: datetime) -> None:
    db = SessionLocal()
    try:
        run = db.query(PaymentReconcileScanRun).filter(PaymentReconcileScanRun.id == run_id).first()
        if run:
            run.status = "finished"
            run.finished_at = run.finished_at or moment
            db.add(run)
            db.commit()
    finally:
        db.close()


def _finish_run_if_expired(db: Session, run: PaymentReconcileScanRun, moment: datetime) -> None:
    if run.status == "running" and run.active_until <= moment:
        run.status = "finished"
        run.finished_at = run.finished_at or moment
        db.add(run)


def _parse_event_payload(raw_payload: str | None) -> list[dict]:
    if not raw_payload:
        return []
    try:
        payload = json.loads(raw_payload)
    except (TypeError, ValueError):
        return []
    return payload if isinstance(payload, list) else []


def _build_scan_event(
    *,
    order: PaymentOrder,
    previous_status: str,
    previous_trade_status: str,
    changed: bool,
    moment: datetime,
) -> dict:
    trade_status_after = order.trade_status or ""
    paid_detected = trade_status_after in ALIPAY_TRADE_SUCCESS_STATUSES
    credited = order.status == "credited" and previous_status != "credited"
    if credited:
        message = "发现已支付，已完成发放积分"
    elif paid_detected:
        message = "发现已支付，积分发放处理中"
    elif trade_status_after == "WAIT_BUYER_PAY":
        message = "支付宝返回待支付"
    elif order.status == "closed":
        message = "支付宝订单已关闭"
    elif changed:
        message = "订单状态已同步"
    else:
        message = "未发现状态变化"
    return {
        "time": moment.isoformat(sep=" "),
        "order_no": order.order_no,
        "status_before": previous_status,
        "status_after": order.status,
        "trade_status_before": previous_trade_status or "",
        "trade_status_after": trade_status_after,
        "paid_detected": paid_detected,
        "credited": credited,
        "message": message,
    }


def _sync_one_order(order_no: str, moment: datetime) -> dict | None:
    day_start = datetime.combine(moment.date(), time.min)
    db = SessionLocal()
    try:
        order = get_payment_order_by_order_no(db, order_no=order_no, for_update=True)
        if not order:
            db.rollback()
            return None
        if order.status not in ALIPAY_QUERYABLE_STATUSES:
            db.rollback()
            return None
        if order.reconcile_until_at is None:
            db.rollback()
            return None
        if order.created_at is not None and order.created_at < day_start:
            db.rollback()
            return None
        if order.reconcile_until_at < moment and not is_manual_payment_reconcile_active(moment):
            db.rollback()
            return None

        previous_status = order.status
        previous_trade_status = order.trade_status
        sync_payment_order_from_alipay(
            db,
            order=order,
            alipay_app_id=settings.ALIPAY_APP_ID,
            gateway=settings.ALIPAY_GATEWAY,
            private_key=settings.ALIPAY_PRIVATE_KEY,
            sign_type=settings.ALIPAY_SIGN_TYPE,
            alipay_public_key=settings.ALIPAY_PUBLIC_KEY,
        )
        changed = order.status != previous_status or order.trade_status != previous_trade_status
        event = _build_scan_event(
            order=order,
            previous_status=previous_status,
            previous_trade_status=previous_trade_status,
            changed=changed,
            moment=moment,
        )
        db.commit()
        return event
    except HTTPException as exc:
        db.rollback()
        logger.warning("Skip Alipay payment reconcile for %s: %s", order_no, exc.detail)
        return {
            "time": moment.isoformat(sep=" "),
            "order_no": order_no,
            "status_before": "",
            "status_after": "",
            "trade_status_before": "",
            "trade_status_after": "",
            "paid_detected": False,
            "credited": False,
            "message": str(exc.detail),
        }
    except Exception:
        db.rollback()
        logger.exception("Failed to reconcile Alipay payment order %s", order_no)
        return {
            "time": moment.isoformat(sep=" "),
            "order_no": order_no,
            "status_before": "",
            "status_after": "",
            "trade_status_before": "",
            "trade_status_after": "",
            "paid_detected": False,
            "credited": False,
            "message": "扫描失败",
        }
    finally:
        db.close()
