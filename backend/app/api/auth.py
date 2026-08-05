import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from sqlalchemy.orm import Session
from app.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.config import settings
from app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    RegisterRequest,
    UserBrief,
    ChangePasswordRequest,
    ForgotPasswordRequest,
    UpdateProfileRequest,
    RedeemCreditKeyRequest,
    RedeemCreditKeyResponse,
    CreatePromoCodeRequest,
    UpdatePromoCodeRequest,
    PromoCodeListResponse,
    PromoReferralListResponse,
    PromoReferralActivityListResponse,
    PromoCodeValidationResponse,
    InviteRewardOverviewResponse,
    InviteRewardReferralListResponse,
    InviteRewardLogListResponse,
)
from app.services.business_id_service import get_user_by_business_id, user_external_id
from app.services.auth_service import (
    authenticate_user,
    change_password,
    register_user,
    reset_password_with_email_code,
    update_username,
)
from app.services.promo_service import (
    create_promo_code,
    get_my_promo_codes,
    get_my_promo_referrals,
    get_my_promo_referral_activities,
    get_valid_promo_code,
    update_promo_code_platform,
)
from app.services.referral_reward_service import (
    get_invite_reward_overview,
    get_user_by_invite_code,
    is_personal_invite_code,
    list_invite_reward_logs,
    list_invite_reward_referrals,
    normalize_invite_code,
)
from app.services.credit_redeem_service import redeem_credit_key
from app.models.prompt_history import PromptHistory
from app.services.admin_service import get_credit_logs
from app.services.user_credit_service import get_user_credit_balance
from app.services.cos_service import normalize_upload_content_type

router = APIRouter(prefix="/api/auth", tags=["认证"])
audit_logger = logging.getLogger("app.audit")
ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif", "image/heic", "image/heif"}
AVATAR_MAX_SIZE = 1 * 1024 * 1024  # 1 MB


def _user_brief(db: Session, user: User) -> UserBrief:
    return UserBrief(
        id=user_external_id(user), business_id=user.business_id, username=user.username, email=user.email, role=user.role,
        avatar_url=user.avatar_url or "", credits=get_user_credit_balance(db, user.id), is_whitelisted=bool(user.is_whitelisted),
    )


@router.post("/register", response_model=LoginResponse)
def register(body: RegisterRequest, request: Request, db: Session = Depends(get_db)):
    token, user = register_user(db, body.username, body.email, body.password, body.promo_code)
    request.state.user_id = user_external_id(user)
    audit_logger.info(
        "user registered",
        extra={
            "event": "auth.register.success",
            "account": body.email.strip().lower(),
            "client_ip": request.client.host if request.client else "",
            "user_agent": request.headers.get("user-agent", ""),
            "user_id": user_external_id(user),
        },
    )
    return LoginResponse(token=token, user=_user_brief(db, user))


@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest, request: Request, db: Session = Depends(get_db)):
    normalized_account = (body.account or "").strip()
    try:
        token, user = authenticate_user(db, normalized_account, body.password)
    except HTTPException:
        audit_logger.warning(
            "login failed",
            extra={
                "event": "auth.login.failed",
                "account": normalized_account,
                "client_ip": request.client.host if request.client else "",
                "user_agent": request.headers.get("user-agent", ""),
            },
        )
        raise
    request.state.user_id = user_external_id(user)
    audit_logger.info(
        "login succeeded",
        extra={
            "event": "auth.login.success",
            "account": normalized_account,
            "client_ip": request.client.host if request.client else "",
            "user_agent": request.headers.get("user-agent", ""),
            "user_id": user_external_id(user),
        },
    )
    return LoginResponse(token=token, user=_user_brief(db, user))


@router.post("/change-password")
def change_pwd(
    body: ChangePasswordRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    change_password(db, user, body.old_password, body.new_password)
    audit_logger.info(
        "password changed",
        extra={
            "event": "auth.password.changed",
            "client_ip": request.client.host if request.client else "",
            "user_agent": request.headers.get("user-agent", ""),
            "user_id": user_external_id(user),
        },
    )
    return {"message": "密码修改成功"}


@router.post("/forgot-password")
async def forgot_password(
    body: ForgotPasswordRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    user = await reset_password_with_email_code(
        db,
        body.email,
        body.verification_id,
        body.verification_code,
        body.new_password,
    )
    request.state.user_id = user_external_id(user)
    audit_logger.info(
        "password reset by email code",
        extra={
            "event": "auth.password.reset",
            "account": body.email.strip().lower(),
            "client_ip": request.client.host if request.client else "",
            "user_agent": request.headers.get("user-agent", ""),
            "user_id": user_external_id(user),
        },
    )
    return {"message": "密码重置成功"}


@router.get("/me", response_model=UserBrief)
def get_me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _user_brief(db, user)


@router.post("/redeem-key", response_model=RedeemCreditKeyResponse)
def redeem_key(
    body: RedeemCreditKeyRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return redeem_credit_key(db, redeem_key=body.key, user=user)


@router.put("/profile", response_model=UserBrief)
def update_profile(
    body: UpdateProfileRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = update_username(db, user, body.username)
    audit_logger.info(
        "profile updated",
        extra={
            "event": "auth.profile.updated",
            "client_ip": request.client.host if request.client else "",
            "user_agent": request.headers.get("user-agent", ""),
            "user_id": user_external_id(user),
        },
    )
    return _user_brief(db, user)


@router.get("/promo-codes/me", response_model=PromoCodeListResponse)
def list_my_promo_codes(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return get_my_promo_codes(db, user)


@router.post("/promo-codes", response_model=PromoCodeListResponse)
def create_my_promo_code(
    body: CreatePromoCodeRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    create_promo_code(db, user, body.platform_name)
    return get_my_promo_codes(db, user)


@router.patch("/promo-codes/{promo_code_id}", response_model=PromoCodeListResponse)
def update_my_promo_code(
    promo_code_id: int,
    body: UpdatePromoCodeRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    update_promo_code_platform(db, user, promo_code_id, body.platform_name)
    return get_my_promo_codes(db, user)


@router.get("/promo-referrals", response_model=PromoReferralListResponse)
def list_my_promo_referrals(
    keyword: Optional[str] = Query(None),
    platform_name: Optional[str] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return get_my_promo_referrals(
        db,
        user,
        keyword=keyword,
        platform_name=platform_name,
        start_date=start_date,
        end_date=end_date,
    )


@router.get("/promo-referral-activities", response_model=PromoReferralActivityListResponse)
def list_my_promo_referral_activities(
    keyword: Optional[str] = Query(None),
    platform_name: Optional[str] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return get_my_promo_referral_activities(
        db,
        user,
        keyword=keyword,
        platform_name=platform_name,
        start_date=start_date,
        end_date=end_date,
    )


def _validate_registration_invite_code(db: Session, code: str) -> PromoCodeValidationResponse:
    normalized_code = normalize_invite_code(code)
    if is_personal_invite_code(normalized_code):
        invite_owner = get_user_by_invite_code(db, normalized_code)
        if invite_owner:
            return PromoCodeValidationResponse(valid=True, code=normalized_code, platform_name="个人邀请")
    promo = get_valid_promo_code(db, normalized_code)
    return PromoCodeValidationResponse(valid=True, code=promo.code, platform_name=promo.platform_name)


@router.get("/promo-codes/validate", response_model=PromoCodeValidationResponse)
def validate_promo_code(
    code: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
):
    return _validate_registration_invite_code(db, code)


@router.get("/invite-codes/validate", response_model=PromoCodeValidationResponse)
def validate_invite_code(
    code: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
):
    return _validate_registration_invite_code(db, code)


@router.get("/invite-rewards/me", response_model=InviteRewardOverviewResponse)
def get_my_invite_reward_overview(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    base_url = (request.headers.get("origin") or "").strip()
    if not base_url:
        base_url = f"{request.url.scheme}://{request.url.netloc}"
    payload = get_invite_reward_overview(db, user, base_url=base_url)
    db.commit()
    return payload


@router.get("/invite-rewards/referrals", response_model=InviteRewardReferralListResponse)
def get_my_invite_reward_referrals(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return list_invite_reward_referrals(db, user)


@router.get("/invite-rewards/logs", response_model=InviteRewardLogListResponse)
def get_my_invite_reward_logs(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return list_invite_reward_logs(db, user)


@router.get("/credit-logs")
def my_credit_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user_id: Optional[str] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    direction: Optional[str] = Query(None, pattern="^(increase|decrease)$"),
    mode: Optional[str] = Query(None, pattern="^(text_generate|image_edit|inpaint|promptReverse|manual|redeem|purchase)$"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    is_admin = user.role in ("admin", "superadmin")
    effective_user_id = user.id
    if is_admin and user_id:
        target_user = get_user_by_business_id(db, user_id)
        if not target_user:
            raise HTTPException(status_code=404, detail="用户不存在")
        effective_user_id = target_user.id
    return get_credit_logs(db, user_id=effective_user_id, page=page, page_size=page_size,
                           start_date=start_date, end_date=end_date, direction=direction, mode=mode)


@router.get("/prompt-history")
def list_prompt_history(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(PromptHistory)
        .filter(PromptHistory.user_id == user.id)
        .order_by(PromptHistory.created_at.desc())
        .limit(10)
        .all()
    )
    return [
        {
            "id": r.id,
            "prompt": r.prompt,
            "mode": r.mode or "generate",
            "source_image": r.source_image or "",
            "created_at": r.created_at,
        }
        for r in rows
    ]


@router.delete("/prompt-history/{item_id}")
def delete_prompt_history(
    item_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = db.query(PromptHistory).filter(
        PromptHistory.id == item_id, PromptHistory.user_id == user.id
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="记录不存在")
    db.delete(row)
    db.commit()
    return {"message": "已删除"}


@router.post("/avatar", response_model=UserBrief)
async def upload_avatar(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    content_type = normalize_upload_content_type(file.filename or "", file.content_type or "")
    if content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail="仅支持 JPG/PNG/WEBP/GIF/HEIC/HEIF 格式")

    data = await file.read()
    if len(data) > AVATAR_MAX_SIZE:
        raise HTTPException(status_code=400, detail="头像图片不能超过 1 MB")

    ext = Path(file.filename or "avatar.jpg").suffix or ".jpg"
    filename = f"{uuid.uuid4().hex}{ext}"
    dest = Path(settings.UPLOAD_DIR) / "avatar" / filename
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)

    user.avatar_url = f"/uploads/avatar/{filename}"
    db.add(user)
    db.commit()
    db.refresh(user)
    return _user_brief(db, user)
