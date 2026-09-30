from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.activity import Activity
from app.utils.business_id import normalize_business_id

VALID_ACTIVITY_STATUSES = {"enabled", "disabled"}
MAX_TITLE_LENGTH = 200
MAX_IMAGE_URL_LENGTH = 500
MAX_DESCRIPTION_LENGTH = 5000


def activity_external_id(item: Activity | None) -> str:
    if not item:
        return ""
    return (item.business_id or "").strip() or str(item.id)


def _normalize_title(value: str | None) -> str:
    normalized = (value or "").strip()
    if not normalized:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="活动标题不能为空")
    if len(normalized) > MAX_TITLE_LENGTH:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"活动标题不能超过 {MAX_TITLE_LENGTH} 个字符")
    return normalized


def _normalize_image_url(value: str | None) -> str:
    normalized = (value or "").strip()
    if not normalized:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请上传活动图片")
    if len(normalized) > MAX_IMAGE_URL_LENGTH:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"活动图片地址不能超过 {MAX_IMAGE_URL_LENGTH} 个字符")
    return normalized


def _normalize_description(value: str | None) -> str:
    normalized = (value or "").strip()
    if len(normalized) > MAX_DESCRIPTION_LENGTH:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"活动描述不能超过 {MAX_DESCRIPTION_LENGTH} 个字符")
    return normalized


def _normalize_status(value: str | None) -> str:
    normalized = (value or "enabled").strip()
    if normalized not in VALID_ACTIVITY_STATUSES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="活动状态不支持")
    return normalized


def _normalize_sort_order(value: int | None) -> int:
    try:
        return int(value if value is not None else 100)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="排序值无效") from exc


def _serialize_activity(item: Activity) -> dict:
    return {
        "activity_id": activity_external_id(item),
        "title": item.title or "",
        "image_url": item.image_url or "",
        "description": item.description or "",
        "status": item.status or "disabled",
        "sort_order": item.sort_order or 0,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


def _get_activity_or_404(db: Session, activity_id: str) -> Activity:
    normalized = normalize_business_id(activity_id)
    if not normalized:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="活动不存在")
    item = db.query(Activity).filter(Activity.business_id == normalized).first()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="活动不存在")
    return item


def list_admin_activities(db: Session, *, page: int = 1, page_size: int = 20) -> dict:
    query = db.query(Activity)
    total = query.count()
    rows = (
        query.order_by(Activity.sort_order.asc(), Activity.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {"total": total, "items": [_serialize_activity(item) for item in rows]}


def get_active_activity(db: Session) -> dict | None:
    item = (
        db.query(Activity)
        .filter(Activity.status == "enabled")
        .order_by(Activity.sort_order.asc(), Activity.id.desc())
        .first()
    )
    return _serialize_activity(item) if item else None


def create_activity(
    db: Session,
    *,
    title: str,
    image_url: str,
    description: str,
    status_value: str,
    sort_order: int,
) -> dict:
    item = Activity(
        title=_normalize_title(title),
        image_url=_normalize_image_url(image_url),
        description=_normalize_description(description),
        status=_normalize_status(status_value),
        sort_order=_normalize_sort_order(sort_order),
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return _serialize_activity(item)


def update_activity(
    db: Session,
    *,
    activity_id: str,
    title: str,
    image_url: str,
    description: str,
    status_value: str,
    sort_order: int,
) -> dict:
    item = _get_activity_or_404(db, activity_id)
    item.title = _normalize_title(title)
    item.image_url = _normalize_image_url(image_url)
    item.description = _normalize_description(description)
    item.status = _normalize_status(status_value)
    item.sort_order = _normalize_sort_order(sort_order)
    db.add(item)
    db.commit()
    db.refresh(item)
    return _serialize_activity(item)


def update_activity_status(db: Session, *, activity_id: str, status_value: str) -> dict:
    item = _get_activity_or_404(db, activity_id)
    item.status = _normalize_status(status_value)
    db.add(item)
    db.commit()
    db.refresh(item)
    return _serialize_activity(item)


def delete_activity(db: Session, *, activity_id: str) -> None:
    item = _get_activity_or_404(db, activity_id)
    db.delete(item)
    db.commit()
