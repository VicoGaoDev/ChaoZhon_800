from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.api.deps import require_admin, require_superadmin
from app.models.user import User
from app.schemas.admin import (
    CreateUserRequest, UserOut, UpdateStatusRequest, UpdateRoleRequest,
    UpdateWhitelistRequest, UpdateRemarkRequest, ResetPasswordRequest, StatsOut, AllocateCreditsRequest, ResetCreditsRequest, CreditLogOut,
    CreateRedeemKeysBatchRequest, RedeemKeyBatchOut, RedeemKeyOut, UpdateRedeemKeyStatusRequest, PaymentOrderAdminOut,
    AnalyticsSummaryOut, AnalyticsTimeseriesOut, AnalyticsBreakdownOut, AnalyticsRedeemRevenueOut,
    ErrorAnalyticsOut, ErrorCategoryTimeseriesOut, ErrorTaskListOut, DailyReportTestOut,
    AdminUserPromoDashboardOut,
)
from app.schemas.feedback import (
    FeedbackDetail,
    FeedbackListResponse,
    FeedbackUnresolvedCountResponse,
    FeedbackUpdateRequest,
)
from app.schemas.history import HistoryResponse, UserHistoryCardItem, UserHistoryResponse
from app.services.business_id_service import get_user_by_business_id
from app.services.admin_service import (
    create_user, list_users, list_user_options, get_user_detail, update_user_status, update_user_role,
    update_user_whitelist, update_user_remark, reset_user_password, get_stats, allocate_credits, reset_user_credits, get_credit_logs,
    list_payment_orders,
    get_analytics_summary, get_analytics_timeseries, get_analytics_breakdown, get_analytics_redeem_revenue,
    get_analytics_payment_revenue, get_error_analytics, get_error_category_timeseries, get_error_tasks,
)
from app.services.credit_redeem_service import create_redeem_key_batch, list_redeem_keys, update_redeem_key_status
from app.services.promo_service import get_user_promo_dashboard_for_admin
from app.services.referral_reward_service import (
    get_admin_invite_reward_dashboard as build_admin_invite_reward_dashboard,
    get_admin_invite_reward_user_detail as build_admin_invite_reward_user_detail,
    get_admin_promo_stats_dashboard as build_admin_promo_stats_dashboard,
    get_admin_promo_stats_user_detail as build_admin_promo_stats_user_detail,
)
from app.services.feedback_service import (
    count_unresolved_feedbacks,
    get_feedback_detail,
    list_feedbacks,
    update_feedback,
)
from app.services.history_service import get_admin_history_cards, get_admin_history_detail, get_all_history
from app.services.daily_report_service import send_previous_day_report

router = APIRouter(prefix="/api/admin", tags=["管理员"])


def _resolve_optional_user_id(db: Session, user_id: str | None) -> int | None:
    if not user_id:
        return None
    user = get_user_by_business_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    return user.id


@router.post("/users", response_model=UserOut)
def admin_create_user(
    body: CreateUserRequest,
    _user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return create_user(db, body.username, body.password, body.role, operator=_user)


@router.get("/users", response_model=list[UserOut])
def admin_list_users(
    _user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return list_users(db)


@router.get("/user-options", response_model=list[UserOut])
def admin_list_user_options(
    keyword: Optional[str] = Query(None),
    limit: int = Query(2000, ge=1, le=5000),
    _user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return list_user_options(db, keyword=keyword, limit=limit)


@router.get("/users/{user_id}", response_model=UserOut)
def admin_get_user_detail(
    user_id: str,
    _user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return get_user_detail(db, user_id)


@router.put("/users/{user_id}/status", response_model=UserOut)
def admin_update_status(
    user_id: str,
    body: UpdateStatusRequest,
    _user: User = Depends(require_superadmin),
    db: Session = Depends(get_db),
):
    return update_user_status(db, user_id, body.status)


@router.put("/users/{user_id}/role", response_model=UserOut)
def admin_update_role(
    user_id: str,
    body: UpdateRoleRequest,
    _user: User = Depends(require_superadmin),
    db: Session = Depends(get_db),
):
    return update_user_role(db, user_id, body.role)


@router.put("/users/{user_id}/whitelist", response_model=UserOut)
def admin_update_whitelist(
    user_id: str,
    body: UpdateWhitelistRequest,
    _user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return update_user_whitelist(db, user_id, body.is_whitelisted)


@router.put("/users/{user_id}/remark", response_model=UserOut)
def admin_update_remark(
    user_id: str,
    body: UpdateRemarkRequest,
    _user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return update_user_remark(db, user_id, body.remark)


@router.put("/users/{user_id}/reset-password", response_model=UserOut)
def admin_reset_password(
    user_id: str,
    body: ResetPasswordRequest,
    _user: User = Depends(require_superadmin),
    db: Session = Depends(get_db),
):
    return reset_user_password(db, user_id, body.new_password)


@router.post("/users/{user_id}/credits", response_model=UserOut)
def admin_allocate_credits(
    user_id: str,
    body: AllocateCreditsRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return allocate_credits(db, user_id, body.amount, body.description, admin.id)


@router.post("/users/{user_id}/credits/reset", response_model=UserOut)
def admin_reset_credits(
    user_id: str,
    body: ResetCreditsRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return reset_user_credits(db, user_id, body.description, admin.id)


@router.get("/users/{user_id}/promo-dashboard", response_model=AdminUserPromoDashboardOut)
def admin_user_promo_dashboard(
    user_id: str,
    _user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    target_user = get_user_by_business_id(db, user_id)
    if not target_user:
        raise HTTPException(status_code=404, detail="用户不存在")
    return get_user_promo_dashboard_for_admin(db, target_user)


@router.post("/redeem-keys/batch", response_model=RedeemKeyBatchOut)
def admin_create_redeem_keys_batch(
    body: CreateRedeemKeysBatchRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return create_redeem_key_batch(db, count=body.count, credit_amount=body.credit_amount, admin_user=admin)


@router.get("/redeem-keys", response_model=dict)
def admin_list_redeem_keys(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    batch_no: Optional[str] = Query(None),
    redeem_key: Optional[str] = Query(None),
    credit_amount: Optional[int] = Query(None, ge=1),
    status_filter: Optional[str] = Query(None, alias="status", pattern="^(enabled|disabled)$"),
    is_used: Optional[bool] = Query(None),
    used_by: Optional[str] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    _user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return list_redeem_keys(
        db,
        page=page,
        page_size=page_size,
        batch_no=batch_no,
        redeem_key=redeem_key,
        credit_amount=credit_amount,
        status_filter=status_filter,
        is_used=is_used,
        used_by=used_by,
        start_date=start_date,
        end_date=end_date,
    )


@router.post("/redeem-keys/{key_id}/status", response_model=RedeemKeyOut)
def admin_update_redeem_key_status(
    key_id: int,
    body: UpdateRedeemKeyStatusRequest,
    _user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return update_redeem_key_status(db, key_id=key_id, new_status=body.status)


@router.get("/credit-logs", response_model=dict)
def admin_credit_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user_id: Optional[str] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    direction: Optional[str] = Query(None, pattern="^(increase|decrease)$"),
    mode: Optional[str] = Query(None, pattern="^(text_generate|image_edit|inpaint|promptReverse|promptOptimize|manual|redeem|purchase)$"),
    _user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return get_credit_logs(db, user_id=_resolve_optional_user_id(db, user_id), page=page, page_size=page_size,
                           start_date=start_date, end_date=end_date, direction=direction, mode=mode)


@router.get("/payment-orders", response_model=dict)
def admin_payment_orders(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status", pattern="^(created|pending_pay|paid|credited|closed|failed)$"),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    _user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return list_payment_orders(
        db,
        page=page,
        page_size=page_size,
        user_keyword=user,
        status_filter=status_filter,
        start_date=start_date,
        end_date=end_date,
    )


@router.get("/stats", response_model=StatsOut)
def admin_stats(
    _user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return get_stats(db)


@router.get("/invite-rewards", response_model=dict)
def admin_invite_rewards(
    _user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return build_admin_invite_reward_dashboard(db)


@router.get("/invite-rewards/users/{user_id}", response_model=dict)
def admin_invite_reward_user_detail(
    user_id: str,
    _user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return build_admin_invite_reward_user_detail(db, user_id)


@router.get("/promo-stats", response_model=dict)
def admin_promo_stats(
    _user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return build_admin_promo_stats_dashboard(db)


@router.get("/promo-stats/users/{user_id}", response_model=dict)
def admin_promo_stats_user_detail(
    user_id: str,
    _user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return build_admin_promo_stats_user_detail(db, user_id)


@router.get("/analytics/summary", response_model=AnalyticsSummaryOut)
def admin_analytics_summary(
    granularity: str = Query("day", pattern="^(day|week|month)$"),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    user_id: Optional[str] = Query(None),
    source: Optional[str] = Query(None, pattern="^(web|app|api)$"),
    model: Optional[str] = Query(None),
    mode: Optional[str] = Query(None, pattern="^(text_generate|image_edit|inpaint|promptReverse|promptOptimize)$"),
    status: Optional[str] = Query(None),
    _user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    resolved_user_id = _resolve_optional_user_id(db, user_id)
    return get_analytics_summary(
        db,
        granularity=granularity,
        start_date=start_date,
        end_date=end_date,
        user_id=resolved_user_id,
        source=source,
        model=model,
        mode=mode,
        status_filter=status,
    )


@router.get("/analytics/timeseries", response_model=AnalyticsTimeseriesOut)
def admin_analytics_timeseries(
    granularity: str = Query("day", pattern="^(day|week|month)$"),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    user_id: Optional[str] = Query(None),
    source: Optional[str] = Query(None, pattern="^(web|app|api)$"),
    model: Optional[str] = Query(None),
    mode: Optional[str] = Query(None, pattern="^(text_generate|image_edit|inpaint|promptReverse|promptOptimize)$"),
    status: Optional[str] = Query(None),
    _user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    resolved_user_id = _resolve_optional_user_id(db, user_id)
    return get_analytics_timeseries(
        db,
        granularity=granularity,
        start_date=start_date,
        end_date=end_date,
        user_id=resolved_user_id,
        source=source,
        model=model,
        mode=mode,
        status_filter=status,
    )


@router.get("/analytics/breakdown", response_model=AnalyticsBreakdownOut)
def admin_analytics_breakdown(
    granularity: str = Query("day", pattern="^(day|week|month)$"),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    user_id: Optional[str] = Query(None),
    source: Optional[str] = Query(None, pattern="^(web|app|api)$"),
    model: Optional[str] = Query(None),
    mode: Optional[str] = Query(None, pattern="^(text_generate|image_edit|inpaint|promptReverse|promptOptimize)$"),
    status: Optional[str] = Query(None),
    _user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    resolved_user_id = _resolve_optional_user_id(db, user_id)
    return get_analytics_breakdown(
        db,
        granularity=granularity,
        start_date=start_date,
        end_date=end_date,
        user_id=resolved_user_id,
        source=source,
        model=model,
        mode=mode,
        status_filter=status,
    )


@router.get("/analytics/redeem-revenue", response_model=AnalyticsRedeemRevenueOut)
def admin_analytics_redeem_revenue(
    granularity: str = Query("day", pattern="^(day|week|month)$"),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    _user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return get_analytics_redeem_revenue(
        db,
        granularity=granularity,
        start_date=start_date,
        end_date=end_date,
    )


@router.get("/analytics/payment-revenue", response_model=AnalyticsRedeemRevenueOut)
def admin_analytics_payment_revenue(
    granularity: str = Query("day", pattern="^(day|week|month)$"),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    _user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return get_analytics_payment_revenue(
        db,
        granularity=granularity,
        start_date=start_date,
        end_date=end_date,
    )


@router.get("/analytics/errors", response_model=ErrorAnalyticsOut)
def admin_error_analytics(
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    model: Optional[str] = Query(None),
    error_category: Optional[str] = Query(None),
    used_fallback_api: Optional[bool] = Query(None),
    _user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return get_error_analytics(
        db,
        start_date=start_date,
        end_date=end_date,
        model=model,
        error_category=error_category,
        used_fallback_api=used_fallback_api,
    )


@router.get("/analytics/errors/timeseries", response_model=ErrorCategoryTimeseriesOut)
def admin_error_category_timeseries(
    granularity: str = Query("3hour", pattern="^(1hour|3hour|6hour)$"),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    model: Optional[str] = Query(None),
    used_fallback_api: Optional[bool] = Query(None),
    limit: int = Query(6, ge=1, le=12),
    _user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return get_error_category_timeseries(
        db,
        granularity=granularity,
        start_date=start_date,
        end_date=end_date,
        model=model,
        used_fallback_api=used_fallback_api,
        limit=limit,
    )


@router.get("/analytics/errors/tasks", response_model=ErrorTaskListOut)
def admin_error_tasks(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    model: Optional[str] = Query(None),
    error_category: Optional[str] = Query(None),
    used_fallback_api: Optional[bool] = Query(None),
    _user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return get_error_tasks(
        db,
        page=page,
        page_size=page_size,
        start_date=start_date,
        end_date=end_date,
        model=model,
        error_category=error_category,
        used_fallback_api=used_fallback_api,
    )


@router.get("/history", response_model=HistoryResponse)
def admin_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None),
    user_id: Optional[str] = Query(None),
    source: Optional[str] = Query(None, pattern="^(web|app|api)$"),
    model: Optional[str] = Query(None),
    mode: Optional[str] = Query(None, pattern="^(text_generate|image_edit|inpaint|promptReverse|promptOptimize)$"),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    _user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    resolved_user_id = _resolve_optional_user_id(db, user_id)
    return get_all_history(
        db, page, page_size,
        status=status, user_id=resolved_user_id,
        source=source,
        model=model, mode=mode,
        start_date=start_date, end_date=end_date,
    )


@router.get("/history/detail", response_model=UserHistoryCardItem)
def admin_history_detail(
    item_type: str = Query(..., pattern="^(task|prompt_history|prompt_optimize_task)$"),
    task_id: Optional[str] = Query(None),
    history_id: Optional[int] = Query(None),
    _user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    try:
        return get_admin_history_detail(
            db,
            item_type=item_type,
            task_id=task_id,
            history_id=history_id,
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="无效的历史记录标识")
    except LookupError:
        raise HTTPException(status_code=404, detail="历史记录不存在")


@router.get("/history/cards", response_model=UserHistoryResponse)
def admin_history_cards(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    include_prompt_reverse: bool = Query(True),
    mode: Optional[str] = Query(None, pattern="^(text_generate|image_edit|inpaint|promptReverse|promptOptimize)$"),
    source: Optional[str] = Query(None, pattern="^(web|app|api)$"),
    model: Optional[str] = Query(None),
    prompt: Optional[str] = Query(None),
    status: Optional[str] = Query(None, pattern="^(pending|processing|success|failed)$"),
    user_id: Optional[str] = Query(None),
    used_fallback_api: Optional[bool] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    _user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return get_admin_history_cards(
        db,
        page,
        page_size,
        include_prompt_reverse=include_prompt_reverse,
        user_id=_resolve_optional_user_id(db, user_id),
        mode=mode,
        source=source,
        model=model,
        prompt=prompt,
        status=status,
        used_fallback_api=used_fallback_api,
        start_date=start_date,
        end_date=end_date,
    )


@router.get("/feedback", response_model=FeedbackListResponse)
def admin_feedback_list(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    feedback_id: Optional[str] = Query(None),
    user_id: Optional[str] = Query(None),
    task_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None, pattern="^(pending|processing|completed)$"),
    _user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return list_feedbacks(
        db,
        feedback_id=feedback_id,
        user_id=_resolve_optional_user_id(db, user_id),
        task_id=task_id,
        status_filter=status,
        page=page,
        page_size=page_size,
    )


@router.get("/feedback/unresolved-count", response_model=FeedbackUnresolvedCountResponse)
def admin_feedback_unresolved_count(
    _user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return {"count": count_unresolved_feedbacks(db)}


@router.get("/feedback/{feedback_id}", response_model=FeedbackDetail)
def admin_feedback_detail(
    feedback_id: str,
    _user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return get_feedback_detail(db, feedback_id)


@router.patch("/feedback/{feedback_id}", response_model=FeedbackDetail)
def admin_feedback_update(
    feedback_id: str,
    body: FeedbackUpdateRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return update_feedback(
        db,
        feedback_id,
        admin=admin,
        status_value=body.status,
        process_note=body.process_note,
        result_note=body.result_note,
    )


@router.post("/notify/daily-report/test", response_model=DailyReportTestOut)
def admin_test_daily_report_notify(
    _user: User = Depends(require_superadmin),
    db: Session = Depends(get_db),
):
    result = send_previous_day_report(db)
    stats = result.stats
    return {
        "sent": result.sent,
        "report_date": stats.start_at.strftime("%Y-%m-%d"),
        "range_start": stats.start_at,
        "range_end": stats.end_at,
        "revenue_fen": stats.revenue_fen,
        "revenue_yuan": stats.revenue_fen / 100,
        "paid_order_count": stats.paid_order_count,
        "redeem_revenue_yuan": stats.redeem_revenue_yuan,
        "redeem_used_count": stats.redeem_used_count,
        "task_total_count": stats.task_total_count,
        "task_success_count": stats.task_success_count,
        "task_failed_count": stats.task_failed_count,
        "credit_consumed": stats.credit_consumed,
    }
