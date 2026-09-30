from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.database import get_db
from app.models.user import User
from app.schemas.activity import (
    ActivityCreateRequest,
    ActivityListResponse,
    ActivityOut,
    ActivityStatusUpdateRequest,
    ActivityUpdateRequest,
)
from app.services.activity_service import (
    create_activity,
    delete_activity,
    get_active_activity,
    list_admin_activities,
    update_activity,
    update_activity_status,
)

router = APIRouter(prefix="/api/activities", tags=["活动"])
admin_router = APIRouter(prefix="/api/admin/activities", tags=["管理员活动"])


@router.get("/active", response_model=ActivityOut | None)
def get_public_active_activity(db: Session = Depends(get_db)):
    return get_active_activity(db)


@admin_router.get("", response_model=ActivityListResponse)
def admin_list_activities(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return list_admin_activities(db, page=page, page_size=page_size)


@admin_router.post("", response_model=ActivityOut, status_code=status.HTTP_201_CREATED)
def admin_create_activity(
    body: ActivityCreateRequest,
    _user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return create_activity(
        db,
        title=body.title,
        image_url=body.image_url,
        description=body.description,
        status_value=body.status,
        sort_order=body.sort_order,
    )


@admin_router.put("/{activity_id}", response_model=ActivityOut)
def admin_update_activity(
    activity_id: str,
    body: ActivityUpdateRequest,
    _user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return update_activity(
        db,
        activity_id=activity_id,
        title=body.title,
        image_url=body.image_url,
        description=body.description,
        status_value=body.status,
        sort_order=body.sort_order,
    )


@admin_router.patch("/{activity_id}/status", response_model=ActivityOut)
def admin_update_activity_status(
    activity_id: str,
    body: ActivityStatusUpdateRequest,
    _user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return update_activity_status(db, activity_id=activity_id, status_value=body.status)


@admin_router.delete("/{activity_id}", status_code=status.HTTP_204_NO_CONTENT)
def admin_delete_activity(
    activity_id: str,
    _user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    delete_activity(db, activity_id=activity_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
