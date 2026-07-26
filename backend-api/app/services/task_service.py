from datetime import timedelta
import logging
import json
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from app.config import settings
from app.models.task import Task
from app.models.image import Image
from app.models.user import User
from app.models.credit_log import CreditLog
from app.models.prompt_history import PromptHistory
from app.services.business_id_service import task_external_id, user_external_id
from app.services.distributed_lock_service import acquire_redis_lock, release_redis_lock
from app.services.external_api_config_service import SCENE_INPAINT, get_scene_credit_cost
from app.services.user_credit_service import apply_user_credit_delta, get_user_credit_account
from app.utils.datetime_utils import now_local
from app.utils.business_id import normalize_business_id

ACTIVE_TASK_STATUSES = ("pending", "queued", "processing")
MAX_TASK_PROMPT_LENGTH = 5000
ENQUEUE_FAILURE_DESCRIPTION = "任务入队失败，返还积分"
TASK_FAILURE_REFUND_DESCRIPTION = "任务失败，返还积分"
DAILY_TASK_FAILURE_REFUND_LIMIT = 10
TASK_SUBMISSION_LOCK_PREFIX = "banana:tasks:submission:user"
TASK_SUBMISSION_LOCK_TIMEOUT_SECONDS = 30
TASK_SUBMISSION_LOCK_BLOCKING_TIMEOUT_SECONDS = 5
PROCESSING_TASK_TIMEOUT_DESCRIPTION = "任务处理超时，已自动关闭"
task_logger = logging.getLogger("app.task")


def _is_credit_exempt_user(user: User | None) -> bool:
    return bool(user and user.role == "superadmin")


def is_task_credit_refunded(db: Session, task_id: int) -> bool:
    return (
        db.query(CreditLog.id)
        .filter(
            CreditLog.task_id == task_id,
            CreditLog.type == "allocate",
            CreditLog.description.in_([
                ENQUEUE_FAILURE_DESCRIPTION,
                TASK_FAILURE_REFUND_DESCRIPTION,
            ]),
        )
        .first()
        is not None
    )


def is_task_generation_failure_credit_refunded(db: Session, task_id: int) -> bool:
    return (
        db.query(CreditLog.id)
        .filter(
            CreditLog.task_id == task_id,
            CreditLog.type == "allocate",
            CreditLog.description == TASK_FAILURE_REFUND_DESCRIPTION,
        )
        .first()
        is not None
    )


def _today_failure_refund_window() -> tuple:
    today_start = now_local().replace(hour=0, minute=0, second=0, microsecond=0)
    return today_start, today_start + timedelta(days=1)


def get_today_task_failure_refund_count(db: Session, user_id: int) -> int:
    today_start, tomorrow_start = _today_failure_refund_window()
    rows = (
        db.query(CreditLog.id)
        .filter(
            CreditLog.user_id == user_id,
            CreditLog.type == "allocate",
            CreditLog.description == TASK_FAILURE_REFUND_DESCRIPTION,
            CreditLog.created_at >= today_start,
            CreditLog.created_at < tomorrow_start,
        )
        .with_for_update()
        .all()
    )
    return len(rows)


def refund_task_credit_for_generation_failure_if_needed(
    db: Session,
    task: Task,
) -> bool:
    if task.status != "failed":
        return False
    credit_cost = int(task.credit_cost or 0)
    if credit_cost <= 0:
        return False

    if is_task_credit_refunded(db, task.id):
        return False

    try:
        with db.begin_nested():
            get_user_credit_account(db, task.user_id, for_update=True)
            today_refund_count = get_today_task_failure_refund_count(db, task.user_id)
            if today_refund_count >= DAILY_TASK_FAILURE_REFUND_LIMIT:
                task_logger.info(
                    "task credit refund skipped due to daily failure refund limit",
                    extra={
                        "event": "task.credit.refund_daily_limit_exceeded",
                        "task_id": task_external_id(task),
                        "user_id": user_external_id(task.user) if task.user else str(task.user_id),
                        "credit_cost": credit_cost,
                        "today_refund_count": today_refund_count,
                        "daily_limit": DAILY_TASK_FAILURE_REFUND_LIMIT,
                    },
                )
                return False
            apply_user_credit_delta(
                db,
                task.user_id,
                delta=credit_cost,
                restore_used_credit=True,
            )
            db.add(CreditLog(
                user_id=task.user_id,
                amount=credit_cost,
                type="allocate",
                description=TASK_FAILURE_REFUND_DESCRIPTION,
                task_id=task.id,
            ))
            db.flush()
    except Exception:
        task_logger.exception(
            "failed to refund task credit after generation failure",
            extra={
                "event": "task.credit.refund_failed",
                "task_id": task_external_id(task),
                "user_id": user_external_id(task.user) if task.user else str(task.user_id),
                "credit_cost": credit_cost,
            },
        )
        return False
    task_logger.info(
        "task credit refunded after generation failure",
        extra={
            "event": "task.credit.refunded",
            "task_id": task_external_id(task),
            "user_id": user_external_id(task.user) if task.user else str(task.user_id),
            "credit_cost": credit_cost,
            "today_refund_count": today_refund_count + 1,
            "daily_limit": DAILY_TASK_FAILURE_REFUND_LIMIT,
        },
    )
    return True


def _validate_task_create_payload(
    mode: str,
    prompt: str,
    num_images: int,
    source_image: str,
    mask_image: str,
) -> tuple[str, int]:
    mode = (mode or "generate").strip().lower()
    if mode not in {"generate", "inpaint"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不支持的生成模式")
    if not prompt or not prompt.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="提示词不能为空")
    if len(prompt.strip()) > MAX_TASK_PROMPT_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"提示词不能超过 {MAX_TASK_PROMPT_LENGTH} 个字符",
        )
    if num_images < 1 or num_images > 12:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="生成数量须在 1-12 之间")
    if mode == "inpaint":
        if not source_image.strip():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请先上传原图")
        if not mask_image.strip():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请先涂抹需要重绘的区域")
        num_images = 1
    return mode, num_images


def _task_submission_lock_name(user_id: int) -> str:
    return f"{TASK_SUBMISSION_LOCK_PREFIX}:{int(user_id)}"


def _expire_stale_processing_tasks(
    db: Session,
    *,
    user_id: int | None = None,
    business_ids: list[str] | None = None,
) -> None:
    timeout_seconds = max(int(settings.PROCESSING_TASK_TIMEOUT_SECONDS or 0), 0)
    if timeout_seconds <= 0:
        return

    cutoff = now_local() - timedelta(seconds=timeout_seconds)
    query = db.query(Task).filter(
        Task.status == "processing",
        Task.is_deleted.is_(False),
        Task.updated_at.is_not(None),
        Task.updated_at <= cutoff,
    )
    if user_id is not None:
        query = query.filter(Task.user_id == user_id)
    if business_ids:
        query = query.filter(Task.business_id.in_(business_ids))

    stale_tasks = query.all()
    if not stale_tasks:
        return

    for task in stale_tasks:
        has_success_image = False
        for image in task.images:
            if image.status == "success":
                has_success_image = True
                continue
            image.status = "failed"
            image.error_message = PROCESSING_TASK_TIMEOUT_DESCRIPTION
            image.image_url = ""
            image.preview_url = ""
            image.image_format = ""
            image.image_size_bytes = 0

        task.status = "success" if has_success_image and all(image.status == "success" for image in task.images) else "failed"
        task.error_message = "" if task.status == "success" else PROCESSING_TASK_TIMEOUT_DESCRIPTION

    db.commit()
    task_logger.error(
        "stale processing tasks expired",
        extra={
            "event": "task.processing.expired",
            "task_ids": [task_external_id(task) for task in stale_tasks],
            "task_count": len(stale_tasks),
            "timeout_seconds": timeout_seconds,
        },
    )


def create_tasks(
    db: Session,
    user_id: int,
    model: str,
    source: str,
    mode: str,
    prompt: str,
    num_images: int,
    size: str,
    resolution: str = "4K",
    custom_size: str = "",
    reference_images: list[str] | None = None,
    source_image: str = "",
    mask_image: str = "",
) -> list[Task]:
    mode, num_images = _validate_task_create_payload(
        mode=mode,
        prompt=prompt,
        num_images=num_images,
        source_image=source_image,
        mask_image=mask_image,
    )
    submission_lock = acquire_redis_lock(
        _task_submission_lock_name(user_id),
        timeout_seconds=TASK_SUBMISSION_LOCK_TIMEOUT_SECONDS,
        blocking_timeout_seconds=TASK_SUBMISSION_LOCK_BLOCKING_TIMEOUT_SECONDS,
    )
    if submission_lock.status == "contended":
        task_logger.warning(
            "task submission rejected by submission lock",
            extra={
                "event": "task.create.lock_contended",
                "user_id": str(user_id),
                "mode": mode,
                "model": model.strip(),
            },
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="当前提交任务较多，请稍后重试",
        )
    if submission_lock.status == "unavailable" and not settings.allow_sync_generation_fallback:
        task_logger.error(
            "task submission lock unavailable",
            extra={
                "event": "task.create.lock_unavailable",
                "user_id": str(user_id),
                "mode": mode,
                "model": model.strip(),
            },
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="任务提交锁服务不可用，请稍后重试",
        )

    tasks: list[Task] = []
    try:
        user = (
            db.query(User)
            .filter(User.id == user_id)
            .with_for_update()
            .first()
        )
        if not user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="用户不存在",
            )
        credit_account = get_user_credit_account(db, user.id, for_update=True)
        current_balance = int(credit_account.remain_credit or 0) if credit_account else 0
        scene_key = SCENE_INPAINT if mode == "inpaint" else model.strip()
        task_logger.info(
            "task submission accepted",
            extra={
                "event": "task.create.requested",
                "user_id": user_external_id(user),
                "mode": mode,
                "model": model.strip(),
                "task_count": 1 if mode == "inpaint" else num_images,
                "prompt_length": len((prompt or "").strip()),
            },
        )
        unit_cost = get_scene_credit_cost(db, scene_key, resolution=resolution)
        task_count = 1 if mode == "inpaint" else num_images
        task_count = ensure_task_submission_capacity(db, user_id=user_id, new_task_count=task_count)
        total_cost = task_count * unit_cost
        per_task_credit_cost = 0 if _is_credit_exempt_user(user) else unit_cost
        actual_total_cost = 0 if _is_credit_exempt_user(user) else total_cost
        if actual_total_cost and current_balance < total_cost:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"积分不足，需要 {total_cost} 积分，当前余额 {current_balance}",
            )

        ref_json = json.dumps(reference_images or [])

        if actual_total_cost:
            credit_account.remain_credit = current_balance - total_cost
            credit_account.used_credit = int(credit_account.used_credit or 0) + total_cost
            db.add(credit_account)

        normalized_prompt = prompt.strip()
        normalized_model = model.strip()
        normalized_source = (source or "web").strip().lower() or "web"
        normalized_custom_size = custom_size.strip()
        normalized_source_image = source_image.strip()
        normalized_mask_image = mask_image.strip()
        credit_log_description = "局部重绘 1 张图片" if mode == "inpaint" else "生成 1 张图片"
        if normalized_source == "api":
            credit_log_description = f"API {credit_log_description}"

        for _ in range(task_count):
            task = Task(
                user_id=user_id,
                model=normalized_model,
                source=normalized_source,
                mode=mode,
                prompt=normalized_prompt,
                num_images=1,
                size=size,
                resolution=resolution,
                custom_size=normalized_custom_size,
                reference_images=ref_json,
                source_image=normalized_source_image,
                mask_image=normalized_mask_image,
                credit_cost=per_task_credit_cost,
                status="pending",
                error_message="",
            )
            db.add(task)
            db.flush()

            image = Image(task_id=task.id, image_url="", status="pending", error_message="")
            db.add(image)

            if per_task_credit_cost:
                db.add(CreditLog(
                    user_id=user_id,
                    amount=-per_task_credit_cost,
                    type="consume",
                    description=credit_log_description,
                    task_id=task.id,
                ))

            tasks.append(task)

        db.add(PromptHistory(user_id=user_id, prompt=normalized_prompt, mode=mode))
        db.commit()
        for task in tasks:
            db.refresh(task)
        task_logger.info(
            "tasks created",
            extra={
                "event": "task.create.persisted",
                "user_id": user_external_id(user),
                "task_ids": [task_external_id(task) for task in tasks],
                "task_count": len(tasks),
                "mode": mode,
                "model": normalized_model,
                "credit_cost": per_task_credit_cost,
                "total_cost": actual_total_cost,
            },
        )
        return tasks
    except Exception:
        task_logger.exception(
            "task creation failed",
            extra={
                "event": "task.create.failed",
                "user_id": user_external_id(user) if "user" in locals() and user else str(user_id),
                "mode": mode,
                "model": model.strip(),
            },
        )
        db.rollback()
        raise
    finally:
        release_redis_lock(submission_lock)


def ensure_task_submission_capacity(db: Session, user_id: int, new_task_count: int) -> int:
    normalized_new_task_count = max(int(new_task_count or 0), 0)
    if normalized_new_task_count <= 0:
        return 0

    _expire_stale_processing_tasks(db, user_id=user_id)

    per_user_limit = max(int(settings.MAX_ACTIVE_TASKS_PER_USER or 0), 0)
    if per_user_limit:
        current_user_active_count = (
            db.query(Task)
            .filter(
                Task.user_id == user_id,
                Task.status.in_(ACTIVE_TASK_STATUSES),
                Task.is_deleted.is_(False),
            )
            .count()
        )
        available_user_slots = per_user_limit - current_user_active_count
        if available_user_slots <= 0:
            task_logger.warning(
                "task submission exceeded per-user limit",
                extra={
                    "event": "task.create.user_limit_exceeded",
                    "user_id": str(user_id),
                    "task_count": normalized_new_task_count,
                },
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=(
                    f"当前最多允许同时处理 {per_user_limit} 个任务，"
                    "请等待部分任务完成后再试"
                ),
            )
        normalized_new_task_count = min(normalized_new_task_count, available_user_slots)

    global_limit = max(int(settings.MAX_ACTIVE_TASKS_GLOBAL or 0), 0)
    if global_limit:
        current_global_active_count = (
            db.query(Task)
            .filter(Task.status.in_(ACTIVE_TASK_STATUSES), Task.is_deleted.is_(False))
            .count()
        )
        available_global_slots = global_limit - current_global_active_count
        if available_global_slots <= 0:
            task_logger.warning(
                "task submission exceeded global limit",
                extra={
                    "event": "task.create.global_limit_exceeded",
                    "user_id": str(user_id),
                    "task_count": normalized_new_task_count,
                },
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="当前排队任务较多，请稍后再试",
            )
        normalized_new_task_count = min(normalized_new_task_count, available_global_slots)

    return normalized_new_task_count


def mark_tasks_queued(db: Session, task_ids: list[int]) -> None:
    if not task_ids:
        return

    tasks = (
        db.query(Task)
        .filter(Task.id.in_(task_ids), Task.status == "pending")
        .all()
    )
    enqueued_at = now_local()
    for task in tasks:
        task.status = "queued"
        task.error_message = ""
        task.enqueued_at = enqueued_at
    db.commit()
    task_logger.info(
        "tasks marked queued",
        extra={
            "event": "task.dispatch.queued",
            "task_ids": [task_external_id(task) for task in tasks],
            "task_count": len(tasks),
        },
    )


def mark_tasks_dispatched(db: Session, task_ids: list[int]) -> None:
    if not task_ids:
        return

    tasks = db.query(Task).filter(Task.id.in_(task_ids)).all()
    if not tasks:
        return

    enqueued_at = now_local()
    for task in tasks:
        if task.enqueued_at is None:
            task.enqueued_at = enqueued_at
    db.commit()
    task_logger.info(
        "tasks marked dispatched",
        extra={
            "event": "task.dispatch.persisted",
            "task_ids": [task_external_id(task) for task in tasks],
            "task_count": len(tasks),
        },
    )


def mark_tasks_enqueue_failed(
    db: Session,
    task_ids: list[int],
    *,
    error_message: str,
) -> None:
    if not task_ids:
        return

    tasks = (
        db.query(Task)
        .filter(Task.id.in_(task_ids), Task.status == "pending")
        .all()
    )
    if not tasks:
        return

    normalized_error_message = (error_message or "任务入队失败").strip()
    user = tasks[0].user
    refund_total = 0

    for task in tasks:
        task.status = "failed"
        task.error_message = normalized_error_message
        refund_total += int(task.credit_cost or 0)
        for image in task.images:
            image.status = "failed"
            image.error_message = normalized_error_message
            image.image_url = ""
            image.preview_url = ""
            image.image_format = ""
            image.image_size_bytes = 0

        if task.credit_cost:
            db.add(CreditLog(
                user_id=task.user_id,
                amount=int(task.credit_cost or 0),
                type="allocate",
                description=ENQUEUE_FAILURE_DESCRIPTION,
                task_id=task.id,
            ))

    if user and refund_total:
        apply_user_credit_delta(
            db,
            user.id,
            delta=refund_total,
            restore_used_credit=True,
        )

    db.commit()
    task_logger.error(
        "tasks enqueue failed",
        extra={
            "event": "task.dispatch.failed",
            "task_ids": [task_external_id(task) for task in tasks],
            "task_count": len(tasks),
        },
    )


def get_task_detail(db: Session, task_id: str, user_id: int | None = None) -> Task:
    normalized_task_id = normalize_business_id(task_id)
    if normalized_task_id:
        _expire_stale_processing_tasks(db, user_id=user_id, business_ids=[normalized_task_id])
    query = db.query(Task).filter(Task.business_id == normalized_task_id)
    if user_id is not None:
        query = query.filter(Task.user_id == user_id, Task.is_deleted.is_(False))
    task = query.first()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")
    return task


def get_task_details(db: Session, task_ids: list[str], user_id: int | None = None) -> list[Task]:
    if not task_ids:
        return []

    normalized_ids = []
    seen_ids: set[str] = set()
    for task_id in task_ids:
        normalized_task_id = normalize_business_id(task_id)
        if not normalized_task_id:
            continue
        if normalized_task_id in seen_ids:
            continue
        seen_ids.add(normalized_task_id)
        normalized_ids.append(normalized_task_id)

    if not normalized_ids:
        return []

    _expire_stale_processing_tasks(db, user_id=user_id, business_ids=normalized_ids)

    query = db.query(Task).filter(Task.business_id.in_(normalized_ids))
    if user_id is not None:
        query = query.filter(Task.user_id == user_id, Task.is_deleted.is_(False))

    task_map = {task.business_id: task for task in query.all()}
    return [task_map[task_id] for task_id in normalized_ids if task_id in task_map]
