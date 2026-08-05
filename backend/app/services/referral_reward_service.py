from __future__ import annotations

import logging
import secrets
from datetime import datetime, timedelta
from urllib.parse import urlencode

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session, aliased

from app.models.credit_redeem_key import CreditRedeemKey
from app.models.payment_order import PaymentOrder
from app.models.referral_reward_grant import ReferralRewardGrant
from app.models.user import User
from app.models.user_promo_code import UserPromoCode
from app.services.business_id_service import get_user_by_business_id, user_external_id
from app.services.promo_service import PROMO_CODE_REWARD_CREDITS, get_user_promo_dashboard_for_admin
from app.services.user_credit_service import change_user_credit_balance, get_user_credit_account
from app.services.wecom_notify_service import send_wecom_markdown
from app.utils.datetime_utils import now_local

INVITE_CODE_PREFIX = "U"
INVITE_CODE_LENGTH = 8
INVITE_CODE_RANDOM_LENGTH = INVITE_CODE_LENGTH - len(INVITE_CODE_PREFIX)
INVITE_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
REFERRAL_REWARD_RATE = 15
REFERRAL_REWARD_MAX_GRANTS_PER_INVITEE = 3
REFERRAL_SOURCE_PAYMENT = "payment"
REFERRAL_SOURCE_REDEEM = "redeem"
logger = logging.getLogger(__name__)


def _today_window() -> tuple[datetime, datetime]:
    today_start = now_local().replace(hour=0, minute=0, second=0, microsecond=0)
    return today_start, today_start + timedelta(days=1)


def normalize_invite_code(code: str | None) -> str:
    return "".join((code or "").strip().upper().split())


def is_personal_invite_code(code: str | None) -> bool:
    normalized = normalize_invite_code(code)
    return (
        len(normalized) == INVITE_CODE_LENGTH
        and normalized.startswith(INVITE_CODE_PREFIX)
        and all(char in INVITE_CODE_ALPHABET for char in normalized[1:])
    )


def _generate_candidate_invite_code() -> str:
    suffix = "".join(secrets.choice(INVITE_CODE_ALPHABET) for _ in range(INVITE_CODE_RANDOM_LENGTH))
    return f"{INVITE_CODE_PREFIX}{suffix}"


def _promo_code_exists(db: Session, code: str) -> bool:
    return db.query(UserPromoCode.id).filter(UserPromoCode.code == code).first() is not None


def _invite_code_exists(db: Session, code: str) -> bool:
    return (
        db.query(User.id).filter(User.invite_code == code).first() is not None
        or _promo_code_exists(db, code)
    )


def generate_unique_invite_code(db: Session) -> str:
    while True:
        code = _generate_candidate_invite_code()
        if not _invite_code_exists(db, code):
            return code


def ensure_user_invite_code(db: Session, user: User) -> str:
    existing_code = normalize_invite_code(user.invite_code)
    if is_personal_invite_code(existing_code) and not _promo_code_exists(db, existing_code):
        return existing_code
    user.invite_code = generate_unique_invite_code(db)
    db.add(user)
    db.flush()
    return user.invite_code


def backfill_user_invite_codes(db: Session) -> int:
    changed = 0
    users = db.query(User).order_by(User.id.asc()).all()
    for user in users:
        existing_code = normalize_invite_code(user.invite_code)
        if is_personal_invite_code(existing_code) and not _promo_code_exists(db, existing_code):
            continue
        user.invite_code = generate_unique_invite_code(db)
        db.add(user)
        db.flush()
        changed += 1
    return changed


def get_user_by_invite_code(db: Session, raw_code: str | None) -> User | None:
    code = normalize_invite_code(raw_code)
    if not is_personal_invite_code(code):
        return None
    return db.query(User).filter(User.invite_code == code, User.status == "active").first()


def _mask_email(email: str | None) -> str:
    normalized = (email or "").strip()
    if not normalized or "@" not in normalized:
        return "-"
    name, domain = normalized.split("@", 1)
    if len(name) <= 2:
        return f"{name[:1]}***@{domain}"
    return f"{name[:2]}***@{domain}"


def build_invite_link(base_url: str, invite_code: str) -> str:
    normalized_base = (base_url or "").strip().rstrip("/")
    if not normalized_base:
        normalized_base = "/"
    separator = "&" if "?" in normalized_base else "?"
    return f"{normalized_base}{separator}{urlencode({'invite': invite_code})}"


def get_invite_reward_overview(db: Session, user: User, *, base_url: str) -> dict:
    invite_code = ensure_user_invite_code(db, user)
    today_start, tomorrow_start = _today_window()
    total_referrals = (
        db.query(func.count(User.id))
        .filter(User.referrer_id == user.id, User.used_promo_code_id.is_(None))
        .scalar()
        or 0
    )
    today_referrals = (
        db.query(func.count(User.id))
        .filter(
            User.referrer_id == user.id,
            User.used_promo_code_id.is_(None),
            User.created_at >= today_start,
            User.created_at < tomorrow_start,
        )
        .scalar()
        or 0
    )
    total_reward_credits = (
        db.query(func.coalesce(func.sum(ReferralRewardGrant.reward_credits), 0))
        .join(User, User.id == ReferralRewardGrant.invitee_id)
        .filter(ReferralRewardGrant.referrer_id == user.id, User.used_promo_code_id.is_(None))
        .scalar()
        or 0
    )
    today_reward_credits = (
        db.query(func.coalesce(func.sum(ReferralRewardGrant.reward_credits), 0))
        .join(User, User.id == ReferralRewardGrant.invitee_id)
        .filter(
            ReferralRewardGrant.referrer_id == user.id,
            User.used_promo_code_id.is_(None),
            ReferralRewardGrant.created_at >= today_start,
            ReferralRewardGrant.created_at < tomorrow_start,
        )
        .scalar()
        or 0
    )
    reward_grant_count = (
        db.query(func.count(ReferralRewardGrant.id))
        .join(User, User.id == ReferralRewardGrant.invitee_id)
        .filter(ReferralRewardGrant.referrer_id == user.id, User.used_promo_code_id.is_(None))
        .scalar()
        or 0
    )
    rewarded_invitee_count = (
        db.query(func.count(func.distinct(ReferralRewardGrant.invitee_id)))
        .join(User, User.id == ReferralRewardGrant.invitee_id)
        .filter(ReferralRewardGrant.referrer_id == user.id, User.used_promo_code_id.is_(None))
        .scalar()
        or 0
    )
    return {
        "invite_code": invite_code,
        "invite_link": build_invite_link(base_url, invite_code),
        "reward_rate": REFERRAL_REWARD_RATE,
        "max_reward_count": REFERRAL_REWARD_MAX_GRANTS_PER_INVITEE,
        "summary": {
            "total_referrals": int(total_referrals),
            "today_referrals": int(today_referrals),
            "rewarded_invitees": int(rewarded_invitee_count),
            "reward_grant_count": int(reward_grant_count),
            "total_reward_credits": int(total_reward_credits),
            "today_reward_credits": int(today_reward_credits),
        },
    }


def list_invite_reward_referrals(db: Session, user: User) -> dict:
    rows = (
        db.query(User)
        .filter(User.referrer_id == user.id, User.used_promo_code_id.is_(None))
        .order_by(User.created_at.desc(), User.id.desc())
        .all()
    )
    invitee_ids = [row.id for row in rows]
    reward_map: dict[int, dict] = {}
    if invitee_ids:
        reward_rows = (
            db.query(
                ReferralRewardGrant.invitee_id,
                func.count(ReferralRewardGrant.id),
                func.coalesce(func.sum(ReferralRewardGrant.reward_credits), 0),
                func.max(ReferralRewardGrant.created_at),
            )
            .filter(
                ReferralRewardGrant.referrer_id == user.id,
                ReferralRewardGrant.invitee_id.in_(invitee_ids),
            )
            .group_by(ReferralRewardGrant.invitee_id)
            .all()
        )
        reward_map = {
            int(invitee_id): {
                "reward_count": int(reward_count or 0),
                "total_reward_credits": int(total_reward_credits or 0),
                "last_reward_at": last_reward_at,
            }
            for invitee_id, reward_count, total_reward_credits, last_reward_at in reward_rows
        }

    items = []
    for row in rows:
        rewards = reward_map.get(row.id, {})
        items.append(
            {
                "user_id": user_external_id(row),
                "username": row.username,
                "email_masked": _mask_email(row.email),
                "reward_count": int(rewards.get("reward_count") or 0),
                "total_reward_credits": int(rewards.get("total_reward_credits") or 0),
                "last_reward_at": rewards.get("last_reward_at"),
                "registered_at": row.created_at,
            }
        )
    return {"total": len(items), "items": items}


def list_invite_reward_logs(db: Session, user: User) -> dict:
    rows = (
        db.query(ReferralRewardGrant, User)
        .join(User, User.id == ReferralRewardGrant.invitee_id)
        .filter(ReferralRewardGrant.referrer_id == user.id, User.used_promo_code_id.is_(None))
        .order_by(ReferralRewardGrant.created_at.desc(), ReferralRewardGrant.id.desc())
        .all()
    )
    items = []
    for grant, invitee in rows:
        items.append(
            {
                "id": grant.id,
                "invitee_user_id": user_external_id(invitee),
                "invitee_username": invitee.username,
                "invitee_email_masked": _mask_email(invitee.email),
                "source_type": grant.source_type,
                "source_id": grant.source_id,
                "source_credits": int(grant.source_credits or 0),
                "reward_rate": int(grant.reward_rate or 0),
                "reward_credits": int(grant.reward_credits or 0),
                "reward_index": int(grant.reward_index or 0),
                "created_at": grant.created_at,
            }
        )
    return {"total": len(items), "items": items}


def apply_referral_reward(
    db: Session,
    *,
    invitee_id: int,
    source_type: str,
    source_id: str,
    source_credits: int,
) -> ReferralRewardGrant | None:
    normalized_source_type = (source_type or "").strip()
    normalized_source_id = (source_id or "").strip()
    credits = int(source_credits or 0)
    if normalized_source_type != REFERRAL_SOURCE_PAYMENT:
        return None
    if not normalized_source_id or credits <= 0:
        return None

    invitee = (
        db.query(User)
        .filter(User.id == invitee_id)
        .with_for_update()
        .populate_existing()
        .first()
    )
    if not invitee or not invitee.referrer_id or int(invitee.referrer_id) == int(invitee.id):
        return None
    if invitee.used_promo_code_id:
        return None

    referrer = db.query(User).filter(User.id == invitee.referrer_id, User.status == "active").first()
    if not referrer:
        return None

    existing_source = (
        db.query(ReferralRewardGrant)
        .filter(
            ReferralRewardGrant.referrer_id == referrer.id,
            ReferralRewardGrant.source_type == normalized_source_type,
            ReferralRewardGrant.source_id == normalized_source_id,
        )
        .first()
    )
    if existing_source:
        return None

    rewarded_count = (
        db.query(func.count(ReferralRewardGrant.id))
        .filter(
            ReferralRewardGrant.referrer_id == referrer.id,
            ReferralRewardGrant.invitee_id == invitee.id,
        )
        .scalar()
        or 0
    )
    if int(rewarded_count) >= REFERRAL_REWARD_MAX_GRANTS_PER_INVITEE:
        return None

    reward_credits = credits * REFERRAL_REWARD_RATE // 100
    if reward_credits <= 0:
        return None

    reward_index = int(rewarded_count) + 1
    grant = ReferralRewardGrant(
        referrer_id=referrer.id,
        invitee_id=invitee.id,
        source_type=normalized_source_type,
        source_id=normalized_source_id,
        source_credits=credits,
        reward_rate=REFERRAL_REWARD_RATE,
        reward_credits=reward_credits,
        reward_index=reward_index,
    )
    db.add(grant)
    db.flush()
    change_user_credit_balance(
        db,
        referrer.id,
        delta=reward_credits,
        log_type="allocate",
        description=_build_reward_description(invitee, normalized_source_type, normalized_source_id, reward_index),
    )
    _send_referral_reward_notification(
        db,
        referrer=referrer,
        invitee=invitee,
        grant=grant,
    )
    return grant


def apply_referral_reward_safely(
    db: Session,
    *,
    invitee_id: int,
    source_type: str,
    source_id: str,
    source_credits: int,
) -> ReferralRewardGrant | None:
    try:
        with db.begin_nested():
            return apply_referral_reward(
                db,
                invitee_id=invitee_id,
                source_type=source_type,
                source_id=source_id,
                source_credits=source_credits,
            )
    except Exception:
        logger.exception(
            "failed to apply referral reward",
            extra={
                "event": "referral_reward.apply_failed",
                "invitee_id": invitee_id,
                "source_type": source_type,
                "source_id": source_id,
            },
        )
        return None


def get_admin_invite_reward_dashboard(db: Session) -> dict:
    invitee_alias = aliased(User)
    summary_row = (
        db.query(
            func.count(ReferralRewardGrant.id),
            func.count(func.distinct(ReferralRewardGrant.referrer_id)),
            func.count(func.distinct(ReferralRewardGrant.invitee_id)),
            func.coalesce(func.sum(ReferralRewardGrant.source_credits), 0),
            func.coalesce(func.sum(ReferralRewardGrant.reward_credits), 0),
        )
        .join(invitee_alias, invitee_alias.id == ReferralRewardGrant.invitee_id)
        .filter(invitee_alias.used_promo_code_id.is_(None))
        .first()
    )
    total_referrals = (
        db.query(func.count(User.id))
        .filter(User.referrer_id.is_not(None), User.used_promo_code_id.is_(None))
        .scalar()
        or 0
    )
    payment_reward_count = (
        db.query(func.count(ReferralRewardGrant.id))
        .join(invitee_alias, invitee_alias.id == ReferralRewardGrant.invitee_id)
        .filter(ReferralRewardGrant.source_type == REFERRAL_SOURCE_PAYMENT, invitee_alias.used_promo_code_id.is_(None))
        .scalar()
        or 0
    )
    redeem_reward_count = (
        db.query(func.count(ReferralRewardGrant.id))
        .join(invitee_alias, invitee_alias.id == ReferralRewardGrant.invitee_id)
        .filter(ReferralRewardGrant.source_type == REFERRAL_SOURCE_REDEEM, invitee_alias.used_promo_code_id.is_(None))
        .scalar()
        or 0
    )
    referral_rows = (
        db.query(User.referrer_id, func.count(User.id))
        .filter(User.referrer_id.is_not(None), User.used_promo_code_id.is_(None))
        .group_by(User.referrer_id)
        .all()
    )
    referral_count_map = {int(referrer_id): int(count or 0) for referrer_id, count in referral_rows if referrer_id}
    reward_rows = (
        db.query(
            ReferralRewardGrant.referrer_id,
            func.count(ReferralRewardGrant.id),
            func.count(func.distinct(ReferralRewardGrant.invitee_id)),
            func.coalesce(func.sum(ReferralRewardGrant.source_credits), 0),
            func.coalesce(func.sum(ReferralRewardGrant.reward_credits), 0),
            func.max(ReferralRewardGrant.created_at),
        )
        .join(invitee_alias, invitee_alias.id == ReferralRewardGrant.invitee_id)
        .filter(invitee_alias.used_promo_code_id.is_(None))
        .group_by(ReferralRewardGrant.referrer_id)
        .all()
    )
    reward_map = {
        int(referrer_id): {
            "reward_grant_count": int(reward_grant_count or 0),
            "rewarded_invitees": int(rewarded_invitees or 0),
            "source_credits": int(source_credits or 0),
            "reward_credits": int(reward_credits or 0),
            "last_reward_at": last_reward_at,
        }
        for referrer_id, reward_grant_count, rewarded_invitees, source_credits, reward_credits, last_reward_at in reward_rows
        if referrer_id
    }
    referrer_ids = sorted(set(referral_count_map) | set(reward_map))
    users = db.query(User).filter(User.id.in_(referrer_ids)).all() if referrer_ids else []
    user_map = {user.id: user for user in users}
    user_items = []
    for referrer_id in referrer_ids:
        user = user_map.get(referrer_id)
        if not user:
            continue
        rewards = reward_map.get(referrer_id, {})
        user_items.append({
            "user_id": user_external_id(user),
            "username": user.username,
            "email": user.email or "",
            "invite_code": user.invite_code or "",
            "total_referrals": referral_count_map.get(referrer_id, 0),
            "rewarded_invitees": int(rewards.get("rewarded_invitees") or 0),
            "reward_grant_count": int(rewards.get("reward_grant_count") or 0),
            "source_credits": int(rewards.get("source_credits") or 0),
            "reward_credits": int(rewards.get("reward_credits") or 0),
            "last_reward_at": rewards.get("last_reward_at"),
            "created_at": user.created_at,
        })
    user_items.sort(key=lambda item: (item["reward_credits"], item["total_referrals"]), reverse=True)

    recent_rows = (
        db.query(ReferralRewardGrant, User, invitee_alias)
        .join(User, User.id == ReferralRewardGrant.referrer_id)
        .join(invitee_alias, invitee_alias.id == ReferralRewardGrant.invitee_id)
        .filter(invitee_alias.used_promo_code_id.is_(None))
        .order_by(ReferralRewardGrant.created_at.desc(), ReferralRewardGrant.id.desc())
        .limit(100)
        .all()
    )
    recent_logs = [
        {
            "id": grant.id,
            "referrer_user_id": user_external_id(referrer),
            "referrer_username": referrer.username,
            "invitee_user_id": user_external_id(invitee),
            "invitee_username": invitee.username,
            "source_type": grant.source_type,
            "source_id": grant.source_id,
            "source_credits": int(grant.source_credits or 0),
            "reward_rate": int(grant.reward_rate or 0),
            "reward_credits": int(grant.reward_credits or 0),
            "reward_index": int(grant.reward_index or 0),
            "created_at": grant.created_at,
        }
        for grant, referrer, invitee in recent_rows
    ]
    reward_grant_count, rewarded_referrers, rewarded_invitees, source_credits, reward_credits = summary_row
    return {
        "summary": {
            "total_referrals": int(total_referrals),
            "rewarded_referrers": int(rewarded_referrers or 0),
            "rewarded_invitees": int(rewarded_invitees or 0),
            "reward_grant_count": int(reward_grant_count or 0),
            "source_credits": int(source_credits or 0),
            "reward_credits": int(reward_credits or 0),
            "payment_reward_count": int(payment_reward_count),
            "redeem_reward_count": int(redeem_reward_count),
        },
        "users": user_items,
        "recent_logs": recent_logs,
    }


def get_admin_invite_reward_user_detail(db: Session, user_id: str) -> dict:
    target_user = get_user_by_business_id(db, user_id)
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")

    referrals = (
        db.query(User)
        .filter(User.referrer_id == target_user.id, User.used_promo_code_id.is_(None))
        .order_by(User.created_at.desc(), User.id.desc())
        .all()
    )
    invitee_ids = [row.id for row in referrals]
    reward_map: dict[int, dict] = {}
    if invitee_ids:
        reward_rows = (
            db.query(
                ReferralRewardGrant.invitee_id,
                func.count(ReferralRewardGrant.id),
                func.coalesce(func.sum(ReferralRewardGrant.reward_credits), 0),
                func.max(ReferralRewardGrant.created_at),
            )
            .filter(
                ReferralRewardGrant.referrer_id == target_user.id,
                ReferralRewardGrant.invitee_id.in_(invitee_ids),
            )
            .group_by(ReferralRewardGrant.invitee_id)
            .all()
        )
        reward_map = {
            int(invitee_id): {
                "reward_count": int(reward_count or 0),
                "reward_credits": int(reward_credits or 0),
                "last_reward_at": last_reward_at,
            }
            for invitee_id, reward_count, reward_credits, last_reward_at in reward_rows
        }

    referral_items = []
    for invitee in referrals:
        rewards = reward_map.get(invitee.id, {})
        referral_items.append({
            "user_id": user_external_id(invitee),
            "username": invitee.username,
            "email": invitee.email or "",
            "reward_count": int(rewards.get("reward_count") or 0),
            "reward_credits": int(rewards.get("reward_credits") or 0),
            "last_reward_at": rewards.get("last_reward_at"),
            "registered_at": invitee.created_at,
        })

    invitee_alias = aliased(User)
    reward_rows = (
        db.query(ReferralRewardGrant, invitee_alias)
        .join(invitee_alias, invitee_alias.id == ReferralRewardGrant.invitee_id)
        .filter(
            ReferralRewardGrant.referrer_id == target_user.id,
            invitee_alias.used_promo_code_id.is_(None),
        )
        .order_by(ReferralRewardGrant.created_at.desc(), ReferralRewardGrant.id.desc())
        .all()
    )
    reward_logs = [
        {
            "id": grant.id,
            "invitee_user_id": user_external_id(invitee),
            "invitee_username": invitee.username,
            "invitee_email": invitee.email or "",
            "source_type": grant.source_type,
            "source_id": grant.source_id,
            "source_credits": int(grant.source_credits or 0),
            "reward_rate": int(grant.reward_rate or 0),
            "reward_credits": int(grant.reward_credits or 0),
            "reward_index": int(grant.reward_index or 0),
            "created_at": grant.created_at,
        }
        for grant, invitee in reward_rows
    ]
    total_reward_credits = sum(item["reward_credits"] for item in reward_logs)
    total_source_credits = sum(item["source_credits"] for item in reward_logs)
    rewarded_invitees = len({item["invitee_user_id"] for item in reward_logs})
    return {
        "user": {
            "user_id": user_external_id(target_user),
            "username": target_user.username,
            "email": target_user.email or "",
            "invite_code": target_user.invite_code or "",
            "created_at": target_user.created_at,
        },
        "summary": {
            "total_referrals": len(referral_items),
            "rewarded_invitees": rewarded_invitees,
            "reward_grant_count": len(reward_logs),
            "source_credits": int(total_source_credits),
            "reward_credits": int(total_reward_credits),
        },
        "referrals": referral_items,
        "reward_logs": reward_logs,
    }


def get_admin_promo_stats_dashboard(db: Session) -> dict:
    total_promo_codes = int(db.query(func.count(UserPromoCode.id)).scalar() or 0)
    whitelisted_users = int(db.query(func.count(User.id)).filter(User.is_whitelisted.is_(True)).scalar() or 0)

    promo_codes = db.query(UserPromoCode).all()
    promo_id_to_owner = {int(promo.id): int(promo.user_id) for promo in promo_codes}
    owner_to_promo_ids: dict[int, list[int]] = {}
    for promo in promo_codes:
        owner_to_promo_ids.setdefault(int(promo.user_id), []).append(int(promo.id))

    referral_rows = (
        db.query(User.used_promo_code_id, func.count(User.id))
        .filter(User.used_promo_code_id.is_not(None))
        .group_by(User.used_promo_code_id)
        .all()
    )
    promo_referral_map = {int(promo_id): int(count or 0) for promo_id, count in referral_rows if promo_id}
    used_promo_codes = sum(1 for count in promo_referral_map.values() if count > 0)

    invitees = (
        db.query(User)
        .filter(User.used_promo_code_id.is_not(None))
        .order_by(User.created_at.desc(), User.id.desc())
        .all()
    )

    purchase_rows = (
        db.query(PaymentOrder)
        .filter(
            PaymentOrder.user_id.in_([invitee.id for invitee in invitees]),
            PaymentOrder.credited_at.is_not(None),
        )
        .all()
        if invitees else []
    )
    redeem_rows = (
        db.query(CreditRedeemKey)
        .filter(
            CreditRedeemKey.used_by_user_id.in_([invitee.id for invitee in invitees]),
            CreditRedeemKey.used_at.is_not(None),
        )
        .all()
        if invitees else []
    )

    purchase_count = len(purchase_rows)
    purchase_credits = sum(int(row.credits or 0) for row in purchase_rows)
    redeem_count = len(redeem_rows)
    redeem_credits = sum(int(row.credit_amount or 0) for row in redeem_rows)

    user_map = {user.id: user for user in db.query(User).filter(User.id.in_(list(owner_to_promo_ids.keys()))).all()} if owner_to_promo_ids else {}
    users_payload = []
    owner_invitees: dict[int, list[User]] = {}
    for invitee in invitees:
        owner_id = promo_id_to_owner.get(int(invitee.used_promo_code_id or 0)) or (int(invitee.referrer_id) if invitee.referrer_id else None)
        if not owner_id:
            continue
        owner_invitees.setdefault(owner_id, []).append(invitee)
    purchase_by_owner: dict[int, int] = {}
    redeem_by_owner: dict[int, int] = {}
    for invitee in invitees:
        owner_id = promo_id_to_owner.get(int(invitee.used_promo_code_id or 0)) or (int(invitee.referrer_id) if invitee.referrer_id else None)
        if not owner_id:
            continue
        user_purchase_credits = sum(int(row.credits or 0) for row in purchase_rows if int(row.user_id) == int(invitee.id))
        user_redeem_credits = sum(int(row.credit_amount or 0) for row in redeem_rows if int(row.used_by_user_id or 0) == int(invitee.id))
        purchase_by_owner[owner_id] = purchase_by_owner.get(owner_id, 0) + user_purchase_credits
        redeem_by_owner[owner_id] = redeem_by_owner.get(owner_id, 0) + user_redeem_credits

    for owner_id, promo_ids in owner_to_promo_ids.items():
        owner = user_map.get(owner_id)
        if not owner:
            continue
        referrals = owner_invitees.get(owner_id, [])
        users_payload.append({
            "user_id": user_external_id(owner),
            "username": owner.username,
            "email": owner.email or "",
            "is_whitelisted": bool(owner.is_whitelisted),
            "promo_code_count": len(promo_ids),
            "used_code_count": sum(1 for promo_id in promo_ids if promo_referral_map.get(promo_id, 0) > 0),
            "total_referrals": len(referrals),
            "reward_credits": len(referrals) * PROMO_CODE_REWARD_CREDITS,
            "purchase_credits": int(purchase_by_owner.get(owner_id, 0)),
            "redeem_credits": int(redeem_by_owner.get(owner_id, 0)),
            "last_referral_at": referrals[0].created_at if referrals else None,
            "created_at": owner.created_at,
        })
    users_payload.sort(key=lambda item: (item["total_referrals"], item["reward_credits"]), reverse=True)

    recent_referrals = []
    promo_code_map = {int(promo.id): promo for promo in promo_codes}
    for invitee in invitees[:100]:
        promo = promo_code_map.get(int(invitee.used_promo_code_id or 0))
        promoter = user_map.get(int(promo.user_id)) if promo else None
        if not promo or not promoter:
            continue
        recent_referrals.append({
            "id": invitee.id,
            "promoter_user_id": user_external_id(promoter),
            "promoter_username": promoter.username,
            "invitee_user_id": user_external_id(invitee),
            "invitee_username": invitee.username,
            "promo_code": promo.code,
            "platform_name": promo.platform_name,
            "reward_credits": PROMO_CODE_REWARD_CREDITS,
            "registered_at": invitee.created_at,
        })

    return {
        "summary": {
            "total_referrals": len(invitees),
            "active_promoters": sum(1 for item in users_payload if item["total_referrals"] > 0),
            "total_promo_codes": int(total_promo_codes),
            "used_promo_codes": int(used_promo_codes),
            "whitelisted_users": int(whitelisted_users),
            "reward_credits": int(len(invitees) * PROMO_CODE_REWARD_CREDITS),
            "purchase_count": int(purchase_count),
            "purchase_credits": int(purchase_credits),
            "redeem_count": int(redeem_count),
            "redeem_credits": int(redeem_credits),
        },
        "users": users_payload,
        "recent_referrals": recent_referrals,
    }


def get_admin_promo_stats_user_detail(db: Session, user_id: str) -> dict:
    target_user = get_user_by_business_id(db, user_id)
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    return get_user_promo_dashboard_for_admin(db, target_user, require_whitelist=False)


def _build_reward_description(invitee: User, source_type: str, source_id: str, reward_index: int) -> str:
    source_label = "在线购买" if source_type == REFERRAL_SOURCE_PAYMENT else "兑换码兑换"
    username = (invitee.username or "").strip() or f"ID {invitee.id}"
    return f"邀请奖励：{username} 第 {reward_index} 次{source_label}返利 {source_id}"


def _build_user_label(user: User) -> str:
    username = (user.username or "").strip() or f"ID {user.id}"
    email = (user.email or "").strip()
    return f"{username} ({email})" if email else username


def _source_type_label(source_type: str) -> str:
    return "在线购买" if source_type == REFERRAL_SOURCE_PAYMENT else "兑换码兑换"


def _send_referral_reward_notification(
    db: Session,
    *,
    referrer: User,
    invitee: User,
    grant: ReferralRewardGrant,
) -> None:
    credit_account = get_user_credit_account(db, referrer.id, create_if_missing=False)
    remain_credit = int(credit_account.remain_credit or 0) if credit_account else 0
    used_credit = int(credit_account.used_credit or 0) if credit_account else 0
    send_wecom_markdown(
        "## 🎉 邀请奖励已发放\n"
        f"> 👤 邀请人: **{_build_user_label(referrer)}**\n"
        f"> 🙋 被邀请用户: **{_build_user_label(invitee)}**\n"
        f"> 🏷️ 奖励来源: **{_source_type_label(grant.source_type)}**\n"
        f"> 🔖 来源编号: `{grant.source_id}`\n"
        f"> ⚡ 对方到账积分: **{int(grant.source_credits or 0)}**\n"
        f"> 🎁 奖励比例: **{int(grant.reward_rate or 0)}%**\n"
        f"> 🎁 发放奖励积分: **{int(grant.reward_credits or 0)}**\n"
        f"> 🔁 第 **{int(grant.reward_index or 0)}** 次奖励\n"
        f"> ⚡ 邀请人已使用积分: **{used_credit}**\n"
        f"> ⚡ 邀请人剩余积分: **{remain_credit}**\n"
        f"> ⏰ 发放时间: {now_local().strftime('%Y-%m-%d %H:%M:%S')}"
    )
