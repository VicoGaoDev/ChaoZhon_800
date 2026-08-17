"""
AI image generation worker using configurable external APIs.

Supports multiple reference images (base64) and marks outputs as failed when
generation or persistence fails.
"""

import base64
import json
import logging
import re
import threading
import time
import uuid
from datetime import timedelta

import httpx
from pathlib import Path
from fastapi import HTTPException

from app.config import settings
from app.database import SessionLocal
from app.models.image import Image
from app.models.regenerate_log import RegenerateLog
from app.models.task import Task
from app.services.business_id_service import task_external_id, user_external_id
from app.services.distributed_lock_service import acquire_redis_lock, release_redis_lock
from app.services.cos_service import build_object_key, load_image_bytes, upload_bytes_to_cos
from app.services.external_api_config_service import (
    build_external_request_kwargs,
    build_secret_variables,
    render_config,
    require_scene_config,
    resolve_mapped_resolution,
    SCENE_INPAINT,
    should_use_multipart_request,
)
from app.services.image_delivery_service import get_optional_cos_config, serialize_asset_urls
from app.services.task_service import refund_task_credit_for_generation_failure_if_needed
from app.utils.datetime_utils import now_local

logger = logging.getLogger(__name__)
MAX_ERROR_MESSAGE_LENGTH = 1800
MAX_RESPONSE_PREVIEW_LENGTH = 1200
QUEUE_UNAVAILABLE_ERROR = "任务队列暂不可用，请稍后重试"
TASK_LOCK_UNAVAILABLE_ERROR = "任务锁服务不可用，请稍后重试"
PROCESSING_TASK_TIMEOUT_ERROR = "任务处理超时，已自动关闭"
TASK_PROCESSING_LOCK_TIMEOUT_SECONDS = max(int(settings.AI_TIMEOUT or 0) + 600, 900)
SINGLE_IMAGE_LOCK_TIMEOUT_SECONDS = max(int(settings.AI_TIMEOUT or 0) + 600, 900)
SYNC_GENERATION_MAX_WORKERS = max(int(settings.SYNC_GENERATION_MAX_WORKERS or 0), 1)
_sync_generation_semaphore = threading.BoundedSemaphore(SYNC_GENERATION_MAX_WORKERS)
_task_inline_images: dict[int, dict[str, object]] = {}


def _clip_error_message(message: str) -> str:
    cleaned = (message or "").strip()
    if not cleaned:
        return ""
    if len(cleaned) <= MAX_ERROR_MESSAGE_LENGTH:
        return cleaned
    return cleaned[:MAX_ERROR_MESSAGE_LENGTH] + "..."


def _clip_response_preview(payload: object) -> str:
    try:
        preview = json.dumps(payload, ensure_ascii=False)
    except Exception:
        preview = str(payload)
    preview = (preview or "").strip() or "(空响应)"
    if len(preview) <= MAX_RESPONSE_PREVIEW_LENGTH:
        return preview
    return preview[:MAX_RESPONSE_PREVIEW_LENGTH] + "..."


def _mark_task_request_started(task: Task) -> bool:
    if task.request_started_at is not None:
        return False
    task.request_started_at = now_local()
    task.request_finished_at = None
    return True


def _mark_task_request_finished(task: Task) -> None:
    task.request_finished_at = now_local()

def _read_file_as_base64(ref_url: str) -> tuple[str, str] | None:
    """Read a local or remote image and return (mime_type, base64_data)."""
    result = load_image_bytes(ref_url)
    if not result:
        return None
    data, mime_type = result
    return mime_type, base64.b64encode(data).decode("utf-8")


def _build_reference_image_payload(image_url: str) -> dict[str, object] | None:
    ref = _read_file_as_base64(image_url)
    if not ref:
        return None
    mime_type, b64_data = ref
    return {
        "inline_part": {"inlineData": {"mimeType": mime_type, "data": b64_data}},
        "base64": b64_data,
        "mime_type": mime_type,
        "data_url": f"data:{mime_type};base64,{b64_data}",
    }


def _build_inline_image_part(image_url: str) -> dict | None:
    reference_payload = _build_reference_image_payload(image_url)
    if not reference_payload:
        return None
    inline_part = reference_payload.get("inline_part")
    return inline_part if isinstance(inline_part, dict) else None


def register_task_inline_images(
    task_id: int,
    *,
    reference_images: list[str] | None = None,
    source_image: str = "",
    mask_image: str = "",
) -> None:
    _task_inline_images[int(task_id)] = {
        "reference_images": list(reference_images or []),
        "source_image": source_image,
        "mask_image": mask_image,
    }


def pop_task_inline_images(task_id: int) -> dict[str, object]:
    return _task_inline_images.pop(int(task_id), {})


def _append_inline_image(parts: list[dict], image_url: str) -> bool:
    inline_part = _build_inline_image_part(image_url)
    if not inline_part:
        return False
    parts.append(inline_part)
    return True


def _split_field_path(field_path: str) -> list[str]:
    normalized = re.sub(r"\[(\d+)\]", r".\1", (field_path or "").strip()).strip(".")
    return [segment for segment in normalized.split(".") if segment]


def _read_value_by_path(payload: object, field_path: str) -> tuple[object | None, object | None]:
    current = payload
    parent: object | None = None
    for segment in _split_field_path(field_path):
        parent = current
        if isinstance(current, dict):
            if segment not in current:
                return None, parent
            current = current[segment]
            continue
        if isinstance(current, list):
            if not segment.isdigit():
                return None, parent
            index = int(segment)
            if index < 0 or index >= len(current):
                return None, parent
            current = current[index]
            continue
        return None, parent
    return current, parent


def _extract_image_from_url_value(image_url: object) -> tuple[tuple[bytes, str] | None, str]:
    if not isinstance(image_url, str) or not image_url.strip():
        return None, ""

    result = load_image_bytes(image_url.strip())
    if not result:
        return None, _clip_error_message(f"生图接口返回了结果图地址，但图片下载失败：{image_url}")
    return result, ""


def _extract_first_inline_image_from_parts(payload: dict) -> tuple[tuple[bytes, str] | None, str]:
    candidates = payload.get("candidates", [])
    if not candidates:
        return None, ""

    for part in candidates[0].get("content", {}).get("parts", []):
        if not isinstance(part, dict):
            continue
        inline = part.get("inlineData")
        if not isinstance(inline, dict):
            continue
        b64_str = inline.get("data")
        if not isinstance(b64_str, str) or not b64_str.strip():
            continue
        mime = str(inline.get("mimeType") or "image/png")
        try:
            img_bytes = base64.b64decode(b64_str)
        except Exception as exc:
            return None, _clip_error_message(f"生图接口返回的 base64 数据解析失败: {exc}")
        logger.info(
            "Generation API success from inlineData parts fallback, mime=%s, image size: %d bytes",
            mime,
            len(img_bytes),
        )
        return (img_bytes, mime), ""
    return None, ""


def _extract_configured_image_url_data(
    payload: dict,
    field_path: str,
    parent: object | None = None,
) -> tuple[tuple[bytes, str] | None, str]:
    candidate_paths: list[str] = []
    if isinstance(parent, dict):
        candidate_paths.append(f"{field_path.rsplit('.', 1)[0]}.url" if "." in field_path else "url")
    candidate_paths.append("data.0.url")

    seen_paths: set[str] = set()
    last_error_message = ""
    for candidate_path in candidate_paths:
        normalized_path = candidate_path.strip()
        if not normalized_path or normalized_path in seen_paths:
            continue
        seen_paths.add(normalized_path)
        image_url, _ = _read_value_by_path(payload, normalized_path)
        result, error_message = _extract_image_from_url_value(image_url)
        if result:
            logger.info(
                "Generation API fallback to image url succeeded: configured_field=%s, url_field=%s",
                field_path,
                normalized_path,
            )
            return result, ""
        if error_message:
            logger.warning(
                "Generation API fallback image url download failed: configured_field=%s, url_field=%s, error=%s",
                field_path,
                normalized_path,
                error_message,
            )
            last_error_message = error_message
    return None, last_error_message


def _extract_configured_image_data(
    payload: dict,
    field_path: str,
) -> tuple[tuple[bytes, str] | None, str]:
    image_b64, parent = _read_value_by_path(payload, field_path)
    if not isinstance(image_b64, str) or not image_b64.strip():
        fallback_result, fallback_error = _extract_configured_image_url_data(payload, field_path, parent)
        if fallback_result:
            return fallback_result, ""
        parts_result, parts_error = _extract_first_inline_image_from_parts(payload)
        if parts_result:
            logger.info(
                "Generation API fallback to first inlineData part succeeded: configured_field=%s",
                field_path,
            )
            return parts_result, ""
        preview = _clip_response_preview(payload)
        logger.warning(
            "Generation API configured field missing: path=%s, response_preview=%s",
            field_path,
            preview,
        )
        if parts_error:
            return None, parts_error
        if fallback_error:
            return None, fallback_error
        return None, _clip_error_message(
            f"生图接口返回内容缺少配置路径 {field_path} 对应的 base64 数据；响应摘要：{preview}"
        )

    mime = "image/png"
    if isinstance(parent, dict):
        mime = str(parent.get("mimeType") or parent.get("mime_type") or mime)

    try:
        return (base64.b64decode(image_b64), mime), ""
    except Exception as exc:
        return None, _clip_error_message(f"生图接口返回的 base64 数据解析失败: {exc}")


def _extract_legacy_image_data(payload: dict) -> tuple[tuple[bytes, str] | None, str]:
    candidates = payload.get("candidates", [])
    if not candidates:
        logger.warning("Generation API returned no candidates: %s", str(payload)[:300])
        return None, _clip_error_message(
            f"生图接口返回内容缺少 candidates: {str(payload)[:300]}"
        )

    result, error_message = _extract_first_inline_image_from_parts(payload)
    if result:
        return result, ""
    if error_message:
        return None, error_message

    logger.warning("Generation API response has no inlineData in parts")
    return None, "生图接口返回内容缺少图片数据 inlineData"


def _call_gemini_api(
    prompt: str,
    aspect_ratio: str,
    image_size: str,
    custom_size: str,
    model_key: str = "",
    reference_images: list[str] | None = None,
    mode: str = "generate",
    source_image: str = "",
    mask_image: str = "",
) -> tuple[tuple[bytes, str] | None, str, int | None]:
    """
    Call Gemini image generation API.
    Returns ((image_bytes, mime_type), "", None) on success and
    (None, error_message, http_status_code) on HTTP failure.
    """
    db = SessionLocal()

    try:
        scene_key = SCENE_INPAINT if mode == "inpaint" else model_key
        config = require_scene_config(db, scene_key)
        config_name = config.name
        configured_field_path = (config.result_base64_field or "").strip()
        mapped_resolution = resolve_mapped_resolution(db, scene_key, aspect_ratio, image_size)
        cos_config = get_optional_cos_config(db)

        parts: list[dict] = []
        render_variables = {
            **build_secret_variables(db),
            "prompt": prompt,
            "aspect_ratio": aspect_ratio,
            "image_size": image_size,
            "custom_size": custom_size,
            "mapped_resolution": mapped_resolution,
            "generation_config": {},
            "mode": mode,
            "reference_image_count": 0,
        }
        if mode == "inpaint":
            source_payload = _build_reference_image_payload(source_image)
            if not source_payload:
                logger.warning("Inpaint source image not found: %s", source_image)
                return None, "图编辑原图不存在或无法读取", None
            source_inline_part = source_payload.get("inline_part")
            if not isinstance(source_inline_part, dict):
                logger.warning("Inpaint source image payload malformed: %s", source_image)
                return None, "图编辑原图格式无效", None
            parts.append(source_inline_part)
            render_variables["source_image"] = source_inline_part
            render_variables["source_image_url"] = serialize_asset_urls(source_image, cos_config=cos_config)["image_url"]
            render_variables["source_image_base64"] = source_payload["base64"]
            render_variables["source_image_mime_type"] = source_payload["mime_type"]
            render_variables["source_image_data_url"] = source_payload["data_url"]

            mask_payload = _build_reference_image_payload(mask_image)
            if not mask_payload:
                logger.warning("Inpaint mask image not found: %s", mask_image)
                return None, "图编辑蒙版不存在或无法读取", None
            mask_inline_part = mask_payload.get("inline_part")
            if not isinstance(mask_inline_part, dict):
                logger.warning("Inpaint mask image payload malformed: %s", mask_image)
                return None, "图编辑蒙版格式无效", None
            parts.append(mask_inline_part)
            render_variables["mask_image"] = mask_inline_part
            render_variables["mask_image_base64"] = mask_payload["base64"]
            render_variables["mask_image_mime_type"] = mask_payload["mime_type"]
            render_variables["mask_image_data_url"] = mask_payload["data_url"]
            parts.append({
                "text": (
                    "请基于第1张原图进行局部重绘，第2张图是蒙版：白色区域需要重绘，"
                    "黑色区域必须保持原样。严格保留未遮罩区域的主体、构图、光影与细节。"
                    f"重绘要求：{prompt}"
                )
            })
        else:
            reference_count = 0
            for index, ref_url in enumerate(reference_images or [], start=1):
                reference_payload = _build_reference_image_payload(ref_url)
                if not reference_payload:
                    logger.warning("Reference image not found or unreadable: index=%d, url=%s", index, ref_url)
                    continue
                inline_part = reference_payload["inline_part"]
                if not isinstance(inline_part, dict):
                    logger.warning("Reference image payload malformed: index=%d, url=%s", index, ref_url)
                    continue
                parts.append(inline_part)
                reference_count += 1
                render_variables[f"reference_image_{index}"] = inline_part
                render_variables[f"reference_image_{index}_url"] = serialize_asset_urls(ref_url, cos_config=cos_config)["image_url"]
                render_variables[f"reference_image_{index}_base64"] = reference_payload["base64"]
                render_variables[f"reference_image_{index}_mime_type"] = reference_payload["mime_type"]
                render_variables[f"reference_image_{index}_data_url"] = reference_payload["data_url"]
            render_variables["reference_image_count"] = reference_count
            parts.append({"text": prompt})

        generation_config = {"responseModalities": ["IMAGE"]}
        if mode != "inpaint":
            generation_config["imageConfig"] = {
                "aspectRatio": aspect_ratio,
            }
            if image_size:
                generation_config["imageConfig"]["imageSize"] = image_size

        render_variables["contents_parts"] = parts
        render_variables["generation_config"] = generation_config
        rendered = render_config(
            config,
            render_variables,
        )
        request_kwargs = build_external_request_kwargs(rendered)
        db.close()

        auth_value = rendered.headers.get("Authorization", "")
        logger.info(
            "Calling generation API: config=%s, mode=%s, prompt=%s, ratio=%s, size=%s, custom_size=%s, ref_count=%d, auth_prefix=%s, request_mode=%s",
            config_name,
            mode,
            prompt[:60],
            aspect_ratio,
            image_size,
            custom_size,
            len(reference_images or []),
            (auth_value[:8] + "...") if auth_value else "none",
            "multipart" if should_use_multipart_request(rendered) else "json",
        )

        with httpx.Client(timeout=settings.AI_TIMEOUT, trust_env=False) as client:
            resp = client.post(
                rendered.request_url,
                **request_kwargs,
            )

            if resp.status_code != 200:
                logger.error(
                    "Generation API HTTP %s: %s", resp.status_code, resp.text[:500]
                )
                return None, _clip_error_message(
                    f"生图接口返回 HTTP {resp.status_code}: {resp.text[:500] or '(空响应)'}"
                ), resp.status_code

            data = resp.json()

        if configured_field_path:
            result, error_message = _extract_configured_image_data(data, configured_field_path)
            if result:
                img_bytes, mime = result
                logger.info(
                    "Generation API success, configured field=%s, mime=%s, image size: %d bytes",
                    configured_field_path, mime, len(img_bytes),
                )
                return result, "", None
            logger.warning("Generation API configured field extraction failed: %s", error_message)
            return None, error_message, None

        result, error_message = _extract_legacy_image_data(data)
        return result, error_message, None
    except HTTPException as exc:
        detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
        logger.error("Generation API config error: %s", detail)
        return None, _clip_error_message(detail), None

    except httpx.TimeoutException:
        logger.error("Generation API request timed out (%s seconds)", settings.AI_TIMEOUT)
        return None, f"生图接口请求超时（{settings.AI_TIMEOUT} 秒）", None
    except Exception as e:
        logger.error("Generation API error: %s", e, exc_info=True)
        return None, _clip_error_message(f"生图接口调用异常: {e}"), None
    finally:
        db.close()


MIME_TO_EXT = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "image/gif": "gif",
}


def _save_image_bytes(db, image_bytes: bytes, mime: str = "image/png") -> str:
    ext = MIME_TO_EXT.get(mime, "png")
    key = build_object_key("generated", f"generated.{ext}", mime)
    return upload_bytes_to_cos(
        db,
        data=image_bytes,
        key=key,
        content_type=mime,
        cache_control=settings.GENERATED_IMAGE_CACHE_CONTROL,
    )


def _cleanup_expired_previews() -> None:
    ttl_seconds = max(int(settings.GENERATED_PREVIEW_TTL_SECONDS or 0), 0)
    if ttl_seconds <= 0:
        return

    preview_dir = Path(settings.UPLOAD_DIR) / "generated_preview"
    if not preview_dir.exists():
        return

    expire_before = max(int(time.time()) - ttl_seconds, 0)
    for file_path in preview_dir.iterdir():
        try:
            if not file_path.is_file():
                continue
            if int(file_path.stat().st_mtime) < expire_before:
                file_path.unlink(missing_ok=True)
        except OSError:
            logger.warning("Failed to cleanup preview file: %s", file_path)


def _save_preview_image(image_bytes: bytes, mime: str = "image/png") -> str:
    ext = MIME_TO_EXT.get(mime, "png")
    preview_dir = Path(settings.UPLOAD_DIR) / "generated_preview"
    preview_dir.mkdir(parents=True, exist_ok=True)
    _cleanup_expired_previews()
    file_name = f"{uuid.uuid4().hex}.{ext}"
    file_path = preview_dir / file_name
    file_path.write_bytes(image_bytes)
    return f"/uploads/generated_preview/{file_name}"


def _remove_local_preview(preview_url: str) -> None:
    relative = (preview_url or "").strip().lstrip("/")
    if not relative.startswith("uploads/"):
        return
    file_path = Path(settings.UPLOAD_DIR) / relative[len("uploads/"):]
    try:
        file_path.unlink(missing_ok=True)
    except OSError:
        logger.warning("Failed to remove local preview file: %s", file_path)


def _derive_image_format(mime: str) -> str:
    if not mime:
        return ""
    return mime.split("/")[-1].upper()


def _mark_image_storage_fallback(image: Image, error_message: str = "") -> None:
    """
    Preserve the locally saved preview when remote storage upload fails.

    The preview file contains the full generated bytes, so we can safely expose
    it as the downloadable image_url fallback instead of discarding the result.
    """
    fallback_url = image.preview_url or ""
    image.image_url = fallback_url
    image.status = "success" if fallback_url else "failed"
    if not fallback_url:
        image.image_format = ""
        image.image_size_bytes = 0
        image.error_message = _clip_error_message(error_message or "图片已生成，但保存结果失败")


def _mark_generation_failure(image: Image, error_message: str) -> None:
    image.preview_url = ""
    image.image_url = ""
    image.image_format = ""
    image.image_size_bytes = 0
    image.status = "failed"
    image.error_message = _clip_error_message(error_message or "生图失败")


def _parse_reference_images(task: Task) -> list[str]:
    """Parse reference_images JSON string from task."""
    if not task.reference_images:
        return []
    try:
        refs = json.loads(task.reference_images)
        return refs if isinstance(refs, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


def _resolve_task_status(images: list[Image]) -> str:
    if any(image.status == "pending" for image in images):
        return "processing"
    if images and all(image.status == "success" for image in images):
        return "success"
    return "failed"


def _rollback_session_safely(db) -> None:
    try:
        db.rollback()
    except Exception:
        logger.exception("Failed to rollback database session")


def _is_task_processing_timed_out(task: Task) -> bool:
    timeout_seconds = max(int(settings.PROCESSING_TASK_TIMEOUT_SECONDS or 0), 0)
    if timeout_seconds <= 0 or (task.status or "") != "processing":
        return False

    last_progress_at = task.updated_at or task.enqueued_at or task.created_at
    if last_progress_at is None:
        return False

    return last_progress_at <= now_local() - timedelta(seconds=timeout_seconds)


def _expire_processing_task(
    db,
    task: Task,
    images: list[Image] | None = None,
    *,
    reason: str = PROCESSING_TASK_TIMEOUT_ERROR,
) -> bool:
    if not _is_task_processing_timed_out(task):
        return False

    task_images = images if images is not None else db.query(Image).filter(Image.task_id == task.id).all()
    normalized_error = _clip_error_message(reason)
    for image in task_images:
        if image.status == "pending":
            _mark_generation_failure(image, normalized_error)

    task.status = _resolve_task_status(task_images)
    if task.status == "processing":
        task.status = "failed"
    task.error_message = "" if task.status == "success" else normalized_error
    db.commit()
    logger.error(
        "Task processing timed out: task_id=%s, timeout_seconds=%s",
        task.id,
        int(settings.PROCESSING_TASK_TIMEOUT_SECONDS or 0),
        extra={
            "event": "task.worker.timeout",
            "task_id": task_external_id(task),
            "user_id": user_external_id(task.user) if task.user else None,
            "timeout_seconds": int(settings.PROCESSING_TASK_TIMEOUT_SECONDS or 0),
        },
    )
    return True


def _recover_task_after_exception(task_id: int, error_message: str) -> None:
    recovery_db = SessionLocal()
    try:
        task = recovery_db.query(Task).filter(Task.id == task_id).first()
        if not task:
            return

        normalized_error = _clip_error_message(error_message or "生图任务执行异常")
        images = recovery_db.query(Image).filter(Image.task_id == task_id).all()
        for image in images:
            if image.status == "pending":
                _mark_generation_failure(image, normalized_error)

        task.status = _resolve_task_status(images)
        if task.status == "processing":
            task.status = "failed"
        task.error_message = "" if task.status == "success" else normalized_error
        refund_task_credit_for_generation_failure_if_needed(recovery_db, task)
        recovery_db.commit()
    except Exception:
        _rollback_session_safely(recovery_db)
        logger.exception("Failed to recover task after exception: task_id=%s", task_id)
    finally:
        recovery_db.close()


def _recover_single_image_after_exception(image_id: int, error_message: str) -> None:
    recovery_db = SessionLocal()
    try:
        image = recovery_db.query(Image).filter(Image.id == image_id).first()
        if not image:
            return

        normalized_error = _clip_error_message(error_message or "重新生成任务执行异常")
        if image.status == "pending":
            _mark_generation_failure(image, normalized_error)

        task = recovery_db.query(Task).filter(Task.id == image.task_id).first()
        if not task:
            recovery_db.commit()
            return

        images = recovery_db.query(Image).filter(Image.task_id == task.id).all()
        task.status = _resolve_task_status(images)
        if task.status == "processing":
            task.status = "failed"
        task.error_message = "" if task.status == "success" else normalized_error
        recovery_db.commit()
    except Exception:
        _rollback_session_safely(recovery_db)
        logger.exception("Failed to recover image after exception: image_id=%s", image_id)
    finally:
        recovery_db.close()


def _process_task(task_id: int, *, use_distributed_lock: bool = True):
    started_at = time.perf_counter()
    logger.info(
        "task processing started",
        extra={
            "event": "task.worker.started",
            "task_id": task_id,
        },
    )
    task_lock = None
    if use_distributed_lock:
        task_lock = acquire_redis_lock(
            f"banana:task:process:{task_id}",
            timeout_seconds=TASK_PROCESSING_LOCK_TIMEOUT_SECONDS,
        )
        if task_lock.status == "contended":
            logger.info(
                "Skip duplicate task delivery: task_id=%s",
                task_id,
                extra={
                    "event": "task.worker.duplicate_skipped",
                    "task_id": task_id,
                },
            )
            return
        if task_lock.status == "unavailable":
            logger.error(
                "Task lock unavailable: task_id=%s",
                task_id,
                extra={
                    "event": "task.worker.lock_unavailable",
                    "task_id": task_id,
                },
            )
            raise RuntimeError(TASK_LOCK_UNAVAILABLE_ERROR)
    db = SessionLocal()
    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            logger.warning(
                "Task not found when processing started",
                extra={
                    "event": "task.worker.not_found",
                    "task_id": task_id,
                },
            )
            return
        if task.status not in {"pending", "queued", "processing"}:
            logger.info(
                "Skip task processing due to terminal status",
                extra={
                    "event": "task.worker.skipped",
                    "task_id": task_id,
                    "task_status": task.status,
                },
            )
            return
        if _expire_processing_task(db, task):
            return
        queue_duration_ms = None
        total_duration_ms = None
        if task.created_at is not None:
            now_ts = time.time()
            created_ts = task.created_at.timestamp()
            total_duration_ms = round(max(now_ts - created_ts, 0) * 1000, 2)
            if task.enqueued_at is not None:
                queue_duration_ms = round(max(task.enqueued_at.timestamp() - created_ts, 0) * 1000, 2)
            else:
                queue_duration_ms = round(
                    max((now_ts - created_ts) * 1000 - ((time.perf_counter() - started_at) * 1000), 0),
                    2,
                )
        task.status = "processing"
        task.error_message = ""
        db.commit()
        db.refresh(task)
        logger.info(
            "Task status switched to processing",
            extra={
                "event": "task.worker.processing",
                "task_id": task_external_id(task),
                "user_id": user_external_id(task.user),
                "mode": task.mode or "generate",
                "model": task.model or "",
                "queue_duration_ms": queue_duration_ms,
            },
        )

        images = db.query(Image).filter(Image.task_id == task_id).all()
        pending_images = [image for image in images if image.status == "pending"]
        if not pending_images:
            task.status = _resolve_task_status(images)
            task.error_message = "" if task.status == "success" else (task.error_message or "生图失败")
            refund_task_credit_for_generation_failure_if_needed(db, task)
            db.commit()
            logger.info(
                "Task finished without pending images",
                extra={
                    "event": "task.worker.completed",
                    "task_id": task_external_id(task),
                    "user_id": user_external_id(task.user),
                    "task_status": task.status,
                    "duration_ms": round((time.perf_counter() - started_at) * 1000, 2),
                    "queue_duration_ms": queue_duration_ms,
                    "total_duration_ms": total_duration_ms,
                },
            )
            return
        inline_images = pop_task_inline_images(task.id)
        ref_urls = list(inline_images.get("reference_images") or []) or _parse_reference_images(task)
        task_mode = (task.mode or "generate").lower()
        all_success = all(image.status == "success" for image in images if image.status != "pending")

        for image in pending_images:
            db.refresh(task)
            if _expire_processing_task(db, task, images):
                return
            if _mark_task_request_started(task):
                db.commit()
                db.refresh(task)
            api_prompt = task.prompt
            api_aspect_ratio = task.size
            api_image_size = task.resolution
            api_custom_size = task.custom_size or ""
            api_model_key = task.model or ""
            api_source_image = str(inline_images.get("source_image") or task.source_image or "")
            api_mask_image = str(inline_images.get("mask_image") or task.mask_image or "")
            # Release the checked-out DB connection while the external AI call is in flight.
            db.commit()
            result, error_message, _http_status_code = _call_gemini_api(
                prompt=api_prompt,
                aspect_ratio=api_aspect_ratio,
                image_size=api_image_size,
                custom_size=api_custom_size,
                model_key=api_model_key,
                reference_images=ref_urls,
                mode=task_mode,
                source_image=api_source_image,
                mask_image=api_mask_image,
            )
            _mark_task_request_finished(task)
            db.commit()

            if result:
                img_bytes, mime = result
                image.preview_url = _save_preview_image(img_bytes, mime)
                image.image_url = ""
                image.image_format = _derive_image_format(mime)
                image.image_size_bytes = len(img_bytes)
                image.status = "success"
                image.error_message = ""
                db.commit()
                try:
                    local_preview_url = image.preview_url
                    image.image_url = _save_image_bytes(db, img_bytes, mime)
                    image.preview_url = ""
                    db.commit()
                    _remove_local_preview(local_preview_url)
                except Exception as exc:
                    logger.exception("Failed to persist generated image to storage")
                    _mark_image_storage_fallback(image, f"图片已生成，但保存结果失败: {exc}")
                    if image.status == "failed":
                        task.error_message = image.error_message
                    all_success = image.status == "success" and all_success
                    db.commit()
            else:
                _mark_generation_failure(image, error_message)
                task.error_message = image.error_message
                all_success = False
                db.commit()

        task.status = "success" if all_success else "failed"
        if task.status == "success":
            task.error_message = ""
        refund_task_credit_for_generation_failure_if_needed(db, task)
        db.commit()
        logger.info(
            "Task processing finished",
            extra={
                "event": "task.worker.completed",
                "task_id": task_external_id(task),
                "user_id": user_external_id(task.user),
                "task_status": task.status,
                "duration_ms": round((time.perf_counter() - started_at) * 1000, 2),
                "queue_duration_ms": queue_duration_ms,
                "total_duration_ms": round(max(time.time() - task.created_at.timestamp(), 0) * 1000, 2)
                if task.created_at is not None
                else None,
            },
        )
    except Exception as exc:
        _rollback_session_safely(db)
        logger.exception(
            "Task processing crashed: task_id=%s",
            task_id,
            extra={
                "event": "task.worker.crashed",
                "task_id": task_external_id(task) if "task" in locals() and task else str(task_id),
                "user_id": user_external_id(task.user) if "task" in locals() and task else None,
                "duration_ms": round((time.perf_counter() - started_at) * 1000, 2),
                "total_duration_ms": round(max(time.time() - task.created_at.timestamp(), 0) * 1000, 2)
                if "task" in locals() and task and task.created_at is not None
                else None,
            },
        )
        _recover_task_after_exception(task_id, str(exc))
    finally:
        db.close()
        if task_lock is not None:
            release_redis_lock(task_lock)


def _process_single_image(image_id: int, *, use_distributed_lock: bool = True):
    image_lock = None
    if use_distributed_lock:
        image_lock = acquire_redis_lock(
            f"banana:image:process:{image_id}",
            timeout_seconds=SINGLE_IMAGE_LOCK_TIMEOUT_SECONDS,
        )
        if image_lock.status == "contended":
            logger.info("Skip duplicate image delivery: image_id=%s", image_id)
            return
        if image_lock.status == "unavailable":
            logger.error("Image lock unavailable: image_id=%s", image_id)
            raise RuntimeError(TASK_LOCK_UNAVAILABLE_ERROR)
    db = SessionLocal()
    try:
        image = db.query(Image).filter(Image.id == image_id).first()
        if not image:
            return
        if image.status != "pending":
            return

        task = db.query(Task).filter(Task.id == image.task_id).first()
        if not task:
            _mark_generation_failure(image, "关联任务不存在")
            db.commit()
            return
        if _expire_processing_task(db, task, [image]):
            return

        task.status = "processing"
        task.error_message = ""
        db.commit()
        db.refresh(task)

        if _expire_processing_task(db, task, [image]):
            return

        ref_urls = _parse_reference_images(task)
        task_mode = (task.mode or "generate").lower()
        if _mark_task_request_started(task):
            db.commit()
            db.refresh(task)

        api_prompt = task.prompt
        api_aspect_ratio = task.size
        api_image_size = task.resolution
        api_custom_size = task.custom_size or ""
        api_model_key = task.model or ""
        api_source_image = task.source_image or ""
        api_mask_image = task.mask_image or ""
        # Release the checked-out DB connection while the external AI call is in flight.
        db.commit()
        result, error_message, _http_status_code = _call_gemini_api(
            prompt=api_prompt,
            aspect_ratio=api_aspect_ratio,
            image_size=api_image_size,
            custom_size=api_custom_size,
            model_key=api_model_key,
            reference_images=ref_urls,
            mode=task_mode,
            source_image=api_source_image,
            mask_image=api_mask_image,
        )
        _mark_task_request_finished(task)
        db.commit()

        if result:
            img_bytes, mime = result
            image.preview_url = _save_preview_image(img_bytes, mime)
            image.image_url = ""
            image.image_format = _derive_image_format(mime)
            image.image_size_bytes = len(img_bytes)
            image.status = "success"
            image.error_message = ""
            db.commit()
            try:
                local_preview_url = image.preview_url
                new_url = _save_image_bytes(db, img_bytes, mime)
                log = (
                    db.query(RegenerateLog)
                    .filter(RegenerateLog.image_id == image_id, RegenerateLog.new_image_url == "")
                    .order_by(RegenerateLog.created_at.desc())
                    .first()
                )
                if log:
                    log.new_image_url = new_url
                image.image_url = new_url
                image.preview_url = ""
                db.commit()
                _remove_local_preview(local_preview_url)
            except Exception as exc:
                logger.exception("Failed to persist regenerated image to storage")
                _mark_image_storage_fallback(image, f"图片已生成，但保存结果失败: {exc}")
                log = (
                    db.query(RegenerateLog)
                    .filter(RegenerateLog.image_id == image_id, RegenerateLog.new_image_url == "")
                    .order_by(RegenerateLog.created_at.desc())
                    .first()
                )
                if log and image.image_url:
                    log.new_image_url = image.image_url
                db.commit()
        else:
            _mark_generation_failure(image, error_message)
            db.commit()

        db.refresh(task)
        task.status = _resolve_task_status(list(task.images))
        task.error_message = "" if task.status == "success" else (image.error_message or task.error_message)
        db.commit()
    except Exception as exc:
        _rollback_session_safely(db)
        logger.exception("Image regeneration crashed: image_id=%s", image_id)
        _recover_single_image_after_exception(image_id, str(exc))
    finally:
        db.close()
        if image_lock is not None:
            release_redis_lock(image_lock)


# --- Celery tasks ---

def _redis_reachable() -> bool:
    """Quick check: can we actually connect to the Redis broker?"""
    try:
        import redis
        r = redis.Redis.from_url(
            settings.REDIS_URL, socket_connect_timeout=1, socket_timeout=1
        )
        r.ping()
        return True
    except Exception:
        return False


try:
    from app.workers.celery_app import celery_app
    CELERY_AVAILABLE = _redis_reachable()
    if not CELERY_AVAILABLE:
        if settings.allow_sync_generation_fallback:
            logger.info("Redis not reachable — falling back to sync thread mode")
        else:
            logger.warning("Redis not reachable — sync fallback disabled")
except Exception:
    CELERY_AVAILABLE = False
    celery_app = None

if CELERY_AVAILABLE and celery_app:
    @celery_app.task(bind=True, max_retries=2)
    def generate_images_task(self, task_id: int):
        try:
            _process_task(task_id)
        except RuntimeError as exc:
            if str(exc) == TASK_LOCK_UNAVAILABLE_ERROR:
                raise self.retry(exc=exc, countdown=2) from exc
            raise

    @celery_app.task(bind=True, max_retries=2)
    def regenerate_single_image_task(self, image_id: int):
        try:
            _process_single_image(image_id)
        except RuntimeError as exc:
            if str(exc) == TASK_LOCK_UNAVAILABLE_ERROR:
                raise self.retry(exc=exc, countdown=2) from exc
            raise
else:
    def generate_images_task():
        raise RuntimeError("Celery not available")

    def regenerate_single_image_task():
        raise RuntimeError("Celery not available")


# --- Sync fallbacks (for dev without Redis) ---

def _run_sync_generation_worker(target, *args) -> None:
    try:
        target(*args, use_distributed_lock=False)
    finally:
        _sync_generation_semaphore.release()


def generate_images_sync(task_id: int):
    if not _sync_generation_semaphore.acquire(blocking=False):
        raise RuntimeError(QUEUE_UNAVAILABLE_ERROR)
    threading.Thread(
        target=_run_sync_generation_worker,
        args=(_process_task, task_id),
        daemon=True,
    ).start()


def regenerate_single_sync(image_id: int):
    if not _sync_generation_semaphore.acquire(blocking=False):
        raise RuntimeError(QUEUE_UNAVAILABLE_ERROR)
    threading.Thread(
        target=_run_sync_generation_worker,
        args=(_process_single_image, image_id),
        daemon=True,
    ).start()


def _sync_fallback_allowed() -> bool:
    return settings.allow_sync_generation_fallback


def get_generation_dispatch_mode() -> str:
    if CELERY_AVAILABLE and celery_app:
        return "celery"
    if _sync_fallback_allowed():
        return "sync"
    raise RuntimeError(QUEUE_UNAVAILABLE_ERROR)


def dispatch_generation_task(task_id: int) -> str:
    mode = get_generation_dispatch_mode()
    if mode == "celery":
        logger.info(
            "Dispatch generation task to celery",
            extra={
                "event": "task.worker.dispatched",
                "task_id": task_id,
                "dispatch_mode": "celery",
            },
        )
        generate_images_task.delay(task_id)
        return "queued"
    logger.info(
        "Dispatch generation task to sync worker",
        extra={
            "event": "task.worker.dispatched",
            "task_id": task_id,
            "dispatch_mode": "sync",
        },
    )
    generate_images_sync(task_id)
    return "sync"


def dispatch_regenerate_task(image_id: int) -> str:
    mode = get_generation_dispatch_mode()
    if mode == "celery":
        regenerate_single_image_task.delay(image_id)
        return "queued"
    regenerate_single_sync(image_id)
    return "sync"
