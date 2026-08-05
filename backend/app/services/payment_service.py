from __future__ import annotations

import base64
import json
import re
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from urllib.parse import urlencode

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from fastapi import HTTPException, Request, status
import httpx
from sqlalchemy.orm import Session

from app.models.payment_order import PaymentOrder
from app.models.user import User
from app.services.referral_reward_service import REFERRAL_SOURCE_PAYMENT, apply_referral_reward_safely
from app.services.user_credit_service import change_user_credit_balance, get_user_credit_account
from app.services.wecom_notify_service import send_wecom_markdown
from app.utils.datetime_utils import now_local

ONLINE_PURCHASE_DESCRIPTION_PREFIX = "在线支付订单 "
ALIPAY_TRADE_SUCCESS_STATUSES = {"TRADE_SUCCESS", "TRADE_FINISHED"}
ALIPAY_TRADE_WAITING_STATUS = "WAIT_BUYER_PAY"
ALIPAY_TRADE_CLOSED_STATUS = "TRADE_CLOSED"
PAYMENT_STATUS_CREATED = "created"
PAYMENT_STATUS_PENDING_PAY = "pending_pay"
PAYMENT_STATUS_PAID = "paid"
PAYMENT_STATUS_CREDITED = "credited"
PAYMENT_STATUS_CLOSED = "closed"
PAYMENT_STATUS_FAILED = "failed"


@dataclass(frozen=True)
class PaymentPlan:
    key: str
    title: str
    amount_fen: int
    credits: int
    tag: str = ""

    @property
    def display_amount(self) -> str:
        amount = Decimal(self.amount_fen) / Decimal("100")
        normalized = amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return format(normalized.normalize(), "f")


@dataclass(frozen=True)
class AlipayTradeQueryResult:
    trade_status: str
    trade_no: str = ""
    total_amount: str = ""
    buyer_id: str = ""


# 商品数值后续可直接在这里调整，前端只使用后端返回结果。
PLAN_CATALOG: tuple[PaymentPlan, ...] = (
    PaymentPlan(key="starter", title="100积分包", amount_fen=750, credits=100, tag="入门推荐"),
    PaymentPlan(key="light", title="500积分包", amount_fen=3650, credits=500),
    PaymentPlan(key="value", title="1000积分包", amount_fen=6890, credits=1000, tag="热门选择"),
    PaymentPlan(key="vip", title="2000积分包", amount_fen=12500, credits=2000, tag="超值加量"),
)
PLAN_CATALOG_MAP = {plan.key: plan for plan in PLAN_CATALOG}
STARTER_PLAN_KEY = "starter"
SUCCESSFUL_PURCHASE_STATUSES = {PAYMENT_STATUS_PAID, PAYMENT_STATUS_CREDITED}
ACTIVE_PURCHASE_STATUSES = {PAYMENT_STATUS_CREATED, PAYMENT_STATUS_PENDING_PAY, PAYMENT_STATUS_PAID, PAYMENT_STATUS_CREDITED}
ALIPAY_QUERYABLE_STATUSES = {PAYMENT_STATUS_PENDING_PAY, PAYMENT_STATUS_PAID}
ALIPAY_TIMEOUT_PATTERN = re.compile(r"^\s*(\d+)\s*([mhd])\s*$", re.IGNORECASE)


def _serialize_payment_plan(plan: PaymentPlan) -> dict:
    return {
        "key": plan.key,
        "title": plan.title,
        "amount_fen": plan.amount_fen,
        "display_amount": plan.display_amount,
        "credits": plan.credits,
        "tag": plan.tag,
        "purchasable": True,
        "disabled_reason": "",
    }


def _has_successful_plan_purchase(db: Session, *, user_id: int, plan_key: str) -> bool:
    return (
        db.query(PaymentOrder.id)
        .filter(
            PaymentOrder.user_id == user_id,
            PaymentOrder.plan_key == plan_key,
            PaymentOrder.status.in_(tuple(SUCCESSFUL_PURCHASE_STATUSES)),
        )
        .first()
        is not None
    )


def _has_active_plan_order(db: Session, *, user_id: int, plan_key: str) -> bool:
    return (
        db.query(PaymentOrder.id)
        .filter(
            PaymentOrder.user_id == user_id,
            PaymentOrder.plan_key == plan_key,
            PaymentOrder.status.in_(tuple(ACTIVE_PURCHASE_STATUSES)),
        )
        .first()
        is not None
    )


def parse_alipay_timeout_express(value: str) -> timedelta:
    match = ALIPAY_TIMEOUT_PATTERN.match(value or "")
    if not match:
        return timedelta(minutes=15)
    amount = int(match.group(1))
    unit = match.group(2).lower()
    if unit == "h":
        return timedelta(hours=amount)
    if unit == "d":
        return timedelta(days=amount)
    return timedelta(minutes=amount)


def close_expired_unpaid_starter_orders(
    db: Session,
    *,
    user: User,
    timeout_express: str,
    alipay_app_id: str,
    gateway: str,
    private_key: str,
    sign_type: str,
    alipay_public_key: str,
) -> None:
    timeout_delta = parse_alipay_timeout_express(timeout_express)
    expired_before = now_local() - timeout_delta
    expired_orders = (
        db.query(PaymentOrder)
        .filter(
            PaymentOrder.user_id == user.id,
            PaymentOrder.plan_key == STARTER_PLAN_KEY,
            PaymentOrder.status.in_((PAYMENT_STATUS_CREATED, PAYMENT_STATUS_PENDING_PAY)),
            PaymentOrder.created_at <= expired_before,
        )
        .all()
    )
    if not expired_orders:
        return

    for order in expired_orders:
        alipay_query_configured = all(
            (
                (alipay_app_id or "").strip(),
                (gateway or "").strip(),
                (private_key or "").strip(),
                (sign_type or "").strip(),
                (alipay_public_key or "").strip(),
            )
        )
        if order.status == PAYMENT_STATUS_PENDING_PAY and alipay_query_configured:
            try:
                query_result = query_alipay_trade_status(
                    app_id=alipay_app_id,
                    gateway=gateway,
                    out_trade_no=order.out_trade_no,
                    private_key=private_key,
                    sign_type=sign_type,
                )
            except HTTPException as exc:
                if exc.status_code != status.HTTP_502_BAD_GATEWAY:
                    raise
                query_result = None

            if query_result and query_result.trade_status == ALIPAY_TRADE_WAITING_STATUS:
                order.trade_status = query_result.trade_status
                order.alipay_trade_no = query_result.trade_no or order.alipay_trade_no
                order.buyer_id = query_result.buyer_id or order.buyer_id
                db.add(order)
                continue
            if query_result and query_result.trade_status:
                payload = {
                    "app_id": alipay_app_id,
                    "out_trade_no": order.out_trade_no,
                    "trade_no": query_result.trade_no,
                    "trade_status": query_result.trade_status,
                    "total_amount": query_result.total_amount,
                    "buyer_id": query_result.buyer_id,
                    "query_source": "alipay.trade.query",
                }
                process_alipay_notification(
                    db,
                    payload=payload,
                    alipay_public_key=alipay_public_key,
                    alipay_app_id=alipay_app_id,
                    skip_signature_verify=True,
                )
                continue

        order.status = PAYMENT_STATUS_CLOSED
        order.trade_status = order.trade_status or ALIPAY_TRADE_CLOSED_STATUS
        order.closed_at = order.closed_at or now_local()
        db.add(order)
    db.flush()


def list_payment_plans(db: Session, *, user: User) -> list[dict]:
    serialized_plans: list[dict] = []
    for plan in PLAN_CATALOG:
        item = _serialize_payment_plan(plan)
        serialized_plans.append(item)
    return serialized_plans


def get_payment_plan(plan_key: str) -> PaymentPlan:
    plan = PLAN_CATALOG_MAP.get((plan_key or "").strip())
    if not plan:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="积分套餐不存在")
    return plan


def format_payment_order(order: PaymentOrder) -> dict:
    return {
        "order_no": order.order_no,
        "plan_key": order.plan_key,
        "subject": order.subject,
        "amount_fen": int(order.amount_fen or 0),
        "credits": int(order.credits or 0),
        "status": order.status,
        "paid_at": order.paid_at,
        "credited_at": order.credited_at,
        "created_at": order.created_at,
        "updated_at": order.updated_at,
    }


def generate_order_no() -> str:
    return f"ALI{datetime.utcnow():%Y%m%d%H%M%S}{secrets.token_hex(4).upper()}"


def build_return_redirect_url(base_url: str, order_no: str) -> str:
    separator = "&" if "?" in base_url else "?"
    return f"{base_url}{separator}order_no={order_no}"


def create_payment_order(
    db: Session,
    *,
    user: User,
    plan_key: str,
    alipay_app_id: str,
    notify_url: str,
    return_url: str,
    gateway: str,
    timeout_express: str,
    private_key: str,
    sign_type: str,
) -> dict:
    missing_config_fields: list[str] = []
    if not (alipay_app_id or "").strip():
        missing_config_fields.append("ALIPAY_APP_ID")
    if not (private_key or "").strip():
        missing_config_fields.append("ALIPAY_PRIVATE_KEY")
    if not (gateway or "").strip():
        missing_config_fields.append("ALIPAY_GATEWAY")
    if not (notify_url or "").strip():
        missing_config_fields.append("ALIPAY_NOTIFY_URL")
    if not (return_url or "").strip():
        missing_config_fields.append("ALIPAY_RETURN_URL")
    if not (sign_type or "").strip():
        missing_config_fields.append("ALIPAY_SIGN_TYPE")
    if not (timeout_express or "").strip():
        missing_config_fields.append("ALIPAY_TIMEOUT_EXPRESS")
    if missing_config_fields:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"支付宝支付配置不完整，缺少: {', '.join(missing_config_fields)}",
        )
    plan = get_payment_plan(plan_key)
    order_no = generate_order_no()
    order = PaymentOrder(
        order_no=order_no,
        out_trade_no=order_no,
        user_id=user.id,
        plan_key=plan.key,
        subject=plan.title,
        amount_fen=plan.amount_fen,
        credits=plan.credits,
        status=PAYMENT_STATUS_CREATED,
    )
    db.add(order)
    db.flush()

    pay_url = build_alipay_page_pay_url(
        app_id=alipay_app_id,
        gateway=gateway,
        order=order,
        notify_url=notify_url,
        return_url=build_return_redirect_url(return_url, order.order_no),
        timeout_express=timeout_express,
        private_key=private_key,
        sign_type=sign_type,
    )
    order.status = PAYMENT_STATUS_PENDING_PAY
    order.return_payload = json.dumps({"pay_url": pay_url}, ensure_ascii=False, separators=(",", ":"))
    db.add(order)
    db.flush()
    return {
        "order_no": order.order_no,
        "status": order.status,
        "amount_fen": int(order.amount_fen or 0),
        "credits": int(order.credits or 0),
        "subject": order.subject,
        "pay_url": pay_url,
    }


def get_payment_order_for_user(db: Session, *, order_no: str, user: User) -> PaymentOrder:
    order = (
        db.query(PaymentOrder)
        .filter(PaymentOrder.order_no == order_no, PaymentOrder.user_id == user.id)
        .first()
    )
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="订单不存在")
    return order


def get_payment_order_for_user_with_sync(
    db: Session,
    *,
    order_no: str,
    user: User,
    alipay_app_id: str,
    gateway: str,
    private_key: str,
    sign_type: str,
    alipay_public_key: str,
) -> PaymentOrder:
    order = get_payment_order_for_user(db, order_no=order_no, user=user)
    if order.status not in ALIPAY_QUERYABLE_STATUSES:
        return order

    try:
        query_result = query_alipay_trade_status(
            app_id=alipay_app_id,
            gateway=gateway,
            out_trade_no=order.out_trade_no,
            private_key=private_key,
            sign_type=sign_type,
        )
    except HTTPException as exc:
        if exc.status_code == status.HTTP_502_BAD_GATEWAY:
            return order
        raise
    if not query_result or not query_result.trade_status:
        return order

    if query_result.trade_status == ALIPAY_TRADE_WAITING_STATUS:
        order.trade_status = query_result.trade_status
        order.alipay_trade_no = query_result.trade_no or order.alipay_trade_no
        order.buyer_id = query_result.buyer_id or order.buyer_id
        order.notify_payload = json.dumps(
            {
                "app_id": alipay_app_id,
                "out_trade_no": order.out_trade_no,
                "trade_no": query_result.trade_no,
                "trade_status": query_result.trade_status,
                "total_amount": query_result.total_amount,
                "buyer_id": query_result.buyer_id,
                "query_source": "alipay.trade.query",
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
        db.add(order)
        db.flush()
        return order

    if query_result.trade_status == ALIPAY_TRADE_CLOSED_STATUS:
        if query_result.total_amount:
            _assert_payment_amount_matches_order(order, query_result.total_amount, detail="支付宝查单金额与订单不一致")
        order.trade_status = query_result.trade_status
        order.alipay_trade_no = query_result.trade_no or order.alipay_trade_no
        order.buyer_id = query_result.buyer_id or order.buyer_id
        order.notify_payload = json.dumps(
            {
                "app_id": alipay_app_id,
                "out_trade_no": order.out_trade_no,
                "trade_no": query_result.trade_no,
                "trade_status": query_result.trade_status,
                "total_amount": query_result.total_amount,
                "buyer_id": query_result.buyer_id,
                "query_source": "alipay.trade.query",
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
        order.status = PAYMENT_STATUS_CLOSED
        order.closed_at = now_local()
        db.add(order)
        db.flush()
        return order

    payload = {
        "app_id": alipay_app_id,
        "out_trade_no": order.out_trade_no,
        "trade_no": query_result.trade_no,
        "trade_status": query_result.trade_status,
        "total_amount": query_result.total_amount,
        "buyer_id": query_result.buyer_id,
        "query_source": "alipay.trade.query",
    }
    process_alipay_notification(
        db,
        payload=payload,
        alipay_public_key=alipay_public_key,
        alipay_app_id=alipay_app_id,
        skip_signature_verify=True,
    )
    db.flush()
    return order


def get_payment_order_by_order_no(
    db: Session,
    *,
    order_no: str,
    for_update: bool = False,
) -> PaymentOrder | None:
    query = db.query(PaymentOrder).filter(PaymentOrder.order_no == order_no)
    if for_update:
        query = query.with_for_update()
    return query.first()


def _send_payment_success_notification(db: Session, order: PaymentOrder) -> None:
    user = order.user
    username = user.username if user else f"ID {order.user_id}"
    email = (user.email or "").strip() if user else ""
    user_label = f"{username} ({email})" if email else username
    amount_yuan = f"{Decimal(int(order.amount_fen or 0)) / Decimal('100'):.2f}"
    credit_account = get_user_credit_account(db, order.user_id, create_if_missing=False)
    remain_credit = int(credit_account.remain_credit or 0) if credit_account else 0
    used_credit = int(credit_account.used_credit or 0) if credit_account else 0
    send_wecom_markdown(
        "## 💰 订单购买成功\n"
        f"> 🧾 订单号: `{order.order_no}`\n"
        f"> 👤 用户: **{user_label}**\n"
        f"> 📦 套餐: **{order.subject or order.plan_key}**\n"
        f"> 💵 金额: <font color=\"warning\">¥{amount_yuan}</font>\n"
        f"> ⚡ 积分到账: **{int(order.credits or 0)}**\n"
        f"> ⚡ 已使用积分: **{used_credit}**\n"
        f"> ⚡ 剩余积分: **{remain_credit}**\n"
        f"> ⏰ 时间: {now_local().strftime('%Y-%m-%d %H:%M:%S')}"
    )


def build_alipay_page_pay_url(
    *,
    app_id: str,
    gateway: str,
    order: PaymentOrder,
    notify_url: str,
    return_url: str,
    timeout_express: str,
    private_key: str,
    sign_type: str,
) -> str:
    biz_content = {
        "out_trade_no": order.out_trade_no,
        "product_code": "FAST_INSTANT_TRADE_PAY",
        "subject": order.subject,
        "total_amount": f"{Decimal(int(order.amount_fen or 0)) / Decimal('100'):.2f}",
        "timeout_express": timeout_express,
    }
    params = {
        "app_id": app_id,
        "method": "alipay.trade.page.pay",
        "format": "JSON",
        "charset": "UTF-8",
        "sign_type": sign_type,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "version": "1.0",
        "notify_url": notify_url,
        "return_url": return_url,
        "biz_content": json.dumps(biz_content, ensure_ascii=False, separators=(",", ":")),
    }
    params["sign"] = sign_alipay_params(params, private_key=private_key, sign_type=sign_type)
    return f"{gateway.rstrip('?')}?{urlencode(params)}"


def query_alipay_trade_status(
    *,
    app_id: str,
    gateway: str,
    out_trade_no: str,
    private_key: str,
    sign_type: str,
) -> AlipayTradeQueryResult | None:
    biz_content = {
        "out_trade_no": out_trade_no,
    }
    params = {
        "app_id": app_id,
        "method": "alipay.trade.query",
        "format": "JSON",
        "charset": "UTF-8",
        "sign_type": sign_type,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "version": "1.0",
        "biz_content": json.dumps(biz_content, ensure_ascii=False, separators=(",", ":")),
    }
    params["sign"] = sign_alipay_params(params, private_key=private_key, sign_type=sign_type)
    try:
        response = _post_alipay_gateway(gateway=gateway, params=params)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"支付宝查单请求失败: {exc}",
        ) from exc

    payload = _parse_alipay_json_response(response, action="支付宝查单")

    result = payload.get("alipay_trade_query_response") or {}
    result_code = str(result.get("code") or "").strip()
    if result_code == "40004":
        return None
    if result_code != "10000":
        sub_msg = str(result.get("sub_msg") or result.get("msg") or "支付宝查单失败").strip()
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=sub_msg)
    return AlipayTradeQueryResult(
        trade_status=str(result.get("trade_status") or "").strip(),
        trade_no=str(result.get("trade_no") or "").strip(),
        total_amount=str(result.get("total_amount") or "").strip(),
        buyer_id=str(result.get("buyer_id") or "").strip(),
    )


def _assert_payment_amount_matches_order(order: PaymentOrder, raw_amount: str, *, detail: str) -> None:
    try:
        amount = Decimal(str(raw_amount or "0")).quantize(Decimal("0.01"))
    except InvalidOperation as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail) from exc
    if int(amount * 100) != int(order.amount_fen or 0):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


def _post_alipay_gateway(*, gateway: str, params: dict[str, str]) -> httpx.Response:
    # Alipay verifies charset from the URL query string for self-signed POST requests.
    return httpx.post(
        gateway.rstrip("?"),
        params=params,
        headers={"Accept": "application/json"},
        timeout=20,
    )


def _parse_alipay_json_response(response: httpx.Response, *, action: str) -> dict:
    try:
        payload = response.json()
    except ValueError as exc:
        payload = _parse_alipay_json_body(response)
        if payload is None:
            content_type = response.headers.get("content-type", "")
            body_preview = " ".join(response.text.strip().split())[:300]
            detail = f"{action}返回了无法解析的响应"
            if content_type:
                detail = f"{detail}，Content-Type: {content_type}"
            if body_preview:
                detail = f"{detail}，响应片段: {body_preview}"
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=detail) from exc
    if not isinstance(payload, dict):
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"{action}返回格式异常")
    return payload


def _parse_alipay_json_body(response: httpx.Response) -> dict | None:
    text_candidates = [response.text]
    for encoding in ("utf-8", "gbk"):
        try:
            text_candidates.append(response.content.decode(encoding))
        except UnicodeDecodeError:
            continue
    for text in text_candidates:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            continue
        try:
            payload = json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    return None


def _build_sign_content(payload: dict[str, str]) -> str:
    filtered_items = []
    for key in sorted(payload.keys()):
        value = payload.get(key)
        if value is None or value == "" or key == "sign":
            continue
        filtered_items.append(f"{key}={value}")
    return "&".join(filtered_items)


def _normalize_private_key(private_key: str) -> str:
    normalized = (private_key or "").strip()
    if "BEGIN" in normalized:
        return normalized
    body = "".join(normalized.split())
    return f"-----BEGIN PRIVATE KEY-----\n{body}\n-----END PRIVATE KEY-----"


def _normalize_public_key(public_key: str) -> str:
    normalized = (public_key or "").strip()
    if "BEGIN" in normalized:
        return normalized
    body = "".join(normalized.split())
    return f"-----BEGIN PUBLIC KEY-----\n{body}\n-----END PUBLIC KEY-----"


def sign_alipay_params(payload: dict[str, str], *, private_key: str, sign_type: str) -> str:
    if sign_type != "RSA2":
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="当前仅支持 RSA2 签名")
    sign_content = _build_sign_content(payload)
    private_key_obj = serialization.load_pem_private_key(
        _normalize_private_key(private_key).encode("utf-8"),
        password=None,
    )
    signature = private_key_obj.sign(
        sign_content.encode("utf-8"),
        padding.PKCS1v15(),
        hashes.SHA256(),
    )
    return base64.b64encode(signature).decode("utf-8")


def verify_alipay_notification_signature(
    payload: dict[str, str],
    *,
    alipay_public_key: str,
) -> bool:
    sign = (payload.get("sign") or "").strip()
    if not sign or not (alipay_public_key or "").strip():
        return False
    sign_content = _build_sign_content(payload)
    public_key_obj = serialization.load_pem_public_key(_normalize_public_key(alipay_public_key).encode("utf-8"))
    try:
        public_key_obj.verify(
            base64.b64decode(sign),
            sign_content.encode("utf-8"),
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
        return True
    except (InvalidSignature, ValueError):
        return False


def process_alipay_notification(
    db: Session,
    *,
    payload: dict[str, str],
    alipay_public_key: str,
    alipay_app_id: str,
    skip_signature_verify: bool = False,
) -> PaymentOrder:
    if not skip_signature_verify and not verify_alipay_notification_signature(payload, alipay_public_key=alipay_public_key):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="支付宝回调验签失败")

    order_no = (payload.get("out_trade_no") or "").strip()
    if not order_no:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="缺少订单号")
    if (payload.get("app_id") or "").strip() != (alipay_app_id or "").strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="支付宝应用标识不匹配")

    order = get_payment_order_by_order_no(db, order_no=order_no, for_update=True)
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="订单不存在")

    _assert_payment_amount_matches_order(order, payload.get("total_amount") or "0", detail="回调金额与订单不一致")

    trade_status = (payload.get("trade_status") or "").strip()
    alipay_trade_no = (payload.get("trade_no") or "").strip()
    buyer_id = (payload.get("buyer_id") or "").strip()

    order.notify_payload = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    order.alipay_trade_no = alipay_trade_no or order.alipay_trade_no
    order.buyer_id = buyer_id or order.buyer_id
    order.trade_status = trade_status

    if order.status == PAYMENT_STATUS_CREDITED or order.credited_at:
        db.add(order)
        db.flush()
        return order

    if trade_status in ALIPAY_TRADE_SUCCESS_STATUSES:
        order.status = PAYMENT_STATUS_PAID
        order.paid_at = order.paid_at or now_local()
        db.add(order)
        db.flush()
        change_user_credit_balance(
            db,
            order.user_id,
            delta=int(order.credits or 0),
            log_type="allocate",
            description=f"{ONLINE_PURCHASE_DESCRIPTION_PREFIX}{order.order_no}",
        )
        order.status = PAYMENT_STATUS_CREDITED
        order.credited_at = now_local()
        db.add(order)
        db.flush()
        apply_referral_reward_safely(
            db,
            invitee_id=order.user_id,
            source_type=REFERRAL_SOURCE_PAYMENT,
            source_id=order.order_no,
            source_credits=int(order.credits or 0),
        )
        _send_payment_success_notification(db, order)
        return order

    if trade_status == ALIPAY_TRADE_WAITING_STATUS:
        if order.status == PAYMENT_STATUS_CREATED:
            order.status = PAYMENT_STATUS_PENDING_PAY
        db.add(order)
        db.flush()
        return order

    if trade_status == ALIPAY_TRADE_CLOSED_STATUS:
        order.status = PAYMENT_STATUS_CLOSED
        order.closed_at = now_local()
    else:
        order.status = PAYMENT_STATUS_FAILED
        order.failed_at = now_local()
    db.add(order)
    db.flush()
    return order


async def record_alipay_return(
    db: Session,
    *,
    request: Request,
) -> PaymentOrder | None:
    params = dict(request.query_params)
    order_no = (params.get("out_trade_no") or params.get("order_no") or "").strip()
    if not order_no:
        return None
    order = get_payment_order_by_order_no(db, order_no=order_no)
    if not order:
        return None
    order.return_payload = json.dumps(params, ensure_ascii=False, separators=(",", ":"))
    db.add(order)
    db.flush()
    return order


def build_auto_submit_form(pay_url: str) -> str:
    encoded_url = json.dumps(pay_url, ensure_ascii=False)
    return (
        "<!doctype html><html><head><meta charset='utf-8'><title>跳转支付宝</title></head>"
        "<body><p>正在跳转到支付宝，请稍候...</p>"
        f"<script>window.location.replace({encoded_url});</script>"
        "</body></html>"
    )
