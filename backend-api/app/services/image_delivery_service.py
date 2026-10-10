from __future__ import annotations

from urllib.parse import urlparse, urlunparse

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.config import settings
from app.models.image import Image
from app.models.task import Task
from app.services.business_id_service import task_external_id
from app.services.cos_service import CosRuntimeConfig, build_cos_public_url, get_cos_config
from app.services.task_service import is_task_generation_failure_credit_refunded

_API_PUBLIC_CDN_HOST = "cdn.12ai.org"
_API_PUBLIC_DISPLAY_HOST = "api.800ai.vip"


def sanitize_api_public_message(text: str | None) -> str:
    value = text or ""
    if not value or _API_PUBLIC_CDN_HOST not in value:
        return value
    return value.replace(_API_PUBLIC_CDN_HOST, _API_PUBLIC_DISPLAY_HOST)


def get_optional_cos_config(db: Session) -> CosRuntimeConfig | None:
    try:
        return get_cos_config(db)
    except HTTPException:
        return None


def _normalize_url(value: str | None) -> str:
    return (value or "").strip()


def normalize_external_image_url(
    image_url: str | None,
    *,
    cos_config: CosRuntimeConfig | None = None,
) -> str:
    canonical_url = _normalize_url(image_url)
    if not canonical_url:
        return ""

    parsed = urlparse(canonical_url)
    if parsed.scheme in {"http", "https"} and parsed.netloc:
        return canonical_url
    if canonical_url.startswith("data:"):
        return canonical_url
    if canonical_url.startswith("/uploads/") or canonical_url.startswith("uploads/"):
        return canonical_url
    if cos_config:
        return build_cos_public_url(cos_config, canonical_url)
    return canonical_url


def _looks_like_cos_url(image_url: str, cos_config: CosRuntimeConfig | None) -> bool:
    parsed = urlparse(image_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return False
    if parsed.netloc.endswith(".myqcloud.com"):
        return True
    if not cos_config:
        return False
    return parsed.netloc == urlparse(cos_config.public_base_url).netloc


def _append_ci_rule(image_url: str, rule: str) -> str:
    cleaned_rule = rule.strip().lstrip("?&")
    if not cleaned_rule or cleaned_rule in image_url:
        return image_url
    separator = "&" if "?" in image_url else "?"
    return f"{image_url}{separator}{cleaned_rule}"


COS_WEBP_FORMAT_RULE = "imageMogr2/format/webp"


def _normalize_style_name(rule: str) -> str:
    cleaned_rule = rule.strip()
    if not cleaned_rule:
        return ""
    if cleaned_rule.startswith("style/"):
        return cleaned_rule[len("style/"):].strip()
    if "/" in cleaned_rule:
        return ""
    return cleaned_rule


def _append_style_suffix(image_url: str, style_name: str) -> str:
    cleaned_style = style_name.strip()
    if not cleaned_style:
        return image_url

    parsed = urlparse(image_url)
    separator = (settings.COS_IMAGE_STYLE_SEPARATOR or "!").strip() or "!"
    if parsed.path.endswith(f"{separator}{cleaned_style}"):
        return image_url

    new_path = f"{parsed.path}{separator}{cleaned_style}"
    return urlunparse(parsed._replace(path=new_path))


def _build_cos_thumb_url(image_url: str, rule: str) -> str:
    style_name = _normalize_style_name(rule)
    if style_name:
        return _append_style_suffix(image_url, style_name)
    return _append_ci_rule(image_url, rule)


def build_webp_url(image_url: str | None) -> str:
    canonical_url = _normalize_url(image_url)
    if not canonical_url:
        return ""
    lowered = canonical_url.lower()
    if lowered.startswith("data:") or lowered.startswith("blob:"):
        return canonical_url
    return _append_ci_rule(canonical_url, COS_WEBP_FORMAT_RULE)


def build_thumb_url(
    image_url: str | None,
    *,
    preview_url: str | None = None,
    cos_config: CosRuntimeConfig | None = None,
) -> str:
    canonical_url = _normalize_url(image_url)
    fallback_preview = _normalize_url(preview_url)
    if not canonical_url:
        return fallback_preview
    if not _looks_like_cos_url(canonical_url, cos_config):
        return canonical_url
    return _build_cos_thumb_url(canonical_url, settings.COS_IMAGE_THUMBNAIL_RULE)


def serialize_asset_urls(
    image_url: str | None,
    *,
    cos_config: CosRuntimeConfig | None = None,
) -> dict[str, str]:
    canonical_url = normalize_external_image_url(image_url, cos_config=cos_config)
    return {
        "image_url": canonical_url,
        "thumb_url": build_thumb_url(canonical_url, cos_config=cos_config),
    }


def serialize_image(image: Image, *, cos_config: CosRuntimeConfig | None = None) -> dict:
    image_url = _normalize_url(image.image_url)
    preview_url = _normalize_url(image.preview_url)
    exposed_preview_url = "" if image_url else preview_url
    return {
        "id": image.id,
        "image_url": image_url,
        "preview_url": exposed_preview_url,
        "thumb_url": build_thumb_url(image_url, preview_url=preview_url, cos_config=cos_config),
        "status": image.status,
        "error_message": sanitize_api_public_message(image.error_message),
        "image_format": image.image_format or "",
        "image_size_bytes": int(image.image_size_bytes or 0),
        "is_deleted": bool(image.is_deleted),
    }


def serialize_task(
    task: Task,
    *,
    cos_config: CosRuntimeConfig | None = None,
    credit_refunded: bool | None = None,
) -> dict:
    task_credit_cost = int(task.credit_cost or 0)
    resolved_credit_refunded = False
    if credit_refunded is not None:
        resolved_credit_refunded = bool(credit_refunded)
    elif task.status == "failed" and task_credit_cost > 0:
        db = Session.object_session(task)
        resolved_credit_refunded = bool(db and is_task_generation_failure_credit_refunded(db, task.id))

    return {
        "id": task_external_id(task),
        "mode": task.mode or "generate",
        "model": task.model or "",
        "source": (task.source or "web"),
        "prompt": task.prompt or "",
        "size": task.size,
        "resolution": task.resolution or "",
        "credit_cost": task_credit_cost,
        "credit_refunded": resolved_credit_refunded,
        "status": task.status,
        "error_message": sanitize_api_public_message(task.error_message),
        "created_at": task.created_at,
        "enqueued_at": task.enqueued_at,
        "request_started_at": task.request_started_at,
        "request_finished_at": task.request_finished_at,
        "images": [serialize_image(image, cos_config=cos_config) for image in task.images],
    }
