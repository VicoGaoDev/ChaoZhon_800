import json
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, field_validator


StatusType = Literal["enabled", "disabled"]
RequestFormatType = Literal["json", "multipart"]
SceneTypeType = Literal["generate", "image_edit", "prompt_reverse", "prompt_optimize", "inpaint"]
SceneKeyType = str


def _validate_json_text(value: str, field_name: str, *, expect_object: bool) -> str:
    raw = (value or "").strip() or ("{}" if expect_object else "{}")
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{field_name} 必须是合法 JSON: {exc.msg}") from exc

    if expect_object and not isinstance(parsed, dict):
        raise ValueError(f"{field_name} 必须是 JSON 对象")
    return json.dumps(parsed, ensure_ascii=False, indent=2)


def _validate_scene_options_json(value: str, field_name: str) -> str:
    raw = (value or "").strip() or "[]"
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{field_name} 必须是合法 JSON: {exc.msg}") from exc

    if not isinstance(parsed, list):
        raise ValueError(f"{field_name} 必须是 JSON 数组")

    normalized: list[dict[str, str]] = []
    for index, item in enumerate(parsed, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"{field_name} 第 {index} 项必须是对象")
        label = str(item.get("label", "") or "").strip()
        option_value = str(item.get("value", "") or "").strip()
        if not label or not option_value:
            raise ValueError(f"{field_name} 第 {index} 项必须包含非空 label 和 value")
        normalized.append({"label": label, "value": option_value})

    return json.dumps(normalized, ensure_ascii=False, indent=2)


def _validate_resolution_mapping_json(value: str, field_name: str) -> str:
    raw = (value or "").strip() or "{}"
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{field_name} 必须是合法 JSON: {exc.msg}") from exc

    if not isinstance(parsed, dict):
        raise ValueError(f"{field_name} 必须是 JSON 对象")

    normalized: dict[str, dict[str, str]] = {}
    for aspect_ratio, resolution_map in parsed.items():
        aspect_key = str(aspect_ratio or "").strip()
        if not aspect_key:
            raise ValueError(f"{field_name} 的宽高比键不能为空")
        if not isinstance(resolution_map, dict):
            raise ValueError(f"{field_name} 中 {aspect_key} 的值必须是对象")
        normalized_resolution_map: dict[str, str] = {}
        for image_size, mapped_resolution in resolution_map.items():
            image_size_key = str(image_size or "").strip()
            mapped_value = str(mapped_resolution or "").strip()
            if not image_size_key or not mapped_value:
                raise ValueError(f"{field_name} 中 {aspect_key} 的分辨率键和值不能为空")
            normalized_resolution_map[image_size_key] = mapped_value
        normalized[aspect_key] = normalized_resolution_map
    return json.dumps(normalized, ensure_ascii=False, indent=2)


def _validate_resolution_credit_costs_json(value: str, field_name: str) -> str:
    raw = (value or "").strip() or "{}"
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{field_name} 必须是合法 JSON: {exc.msg}") from exc

    if not isinstance(parsed, dict):
        raise ValueError(f"{field_name} 必须是 JSON 对象")

    normalized: dict[str, int] = {}
    for resolution, credit_cost in parsed.items():
        resolution_key = str(resolution or "").strip()
        if not resolution_key:
            raise ValueError(f"{field_name} 的分辨率键不能为空")
        if isinstance(credit_cost, bool):
            raise ValueError(f"{field_name} 中 {resolution_key} 的积分消耗必须是整数")
        try:
            normalized_cost = int(credit_cost)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{field_name} 中 {resolution_key} 的积分消耗必须是整数") from exc
        if normalized_cost < 0:
            raise ValueError(f"{field_name} 中 {resolution_key} 的积分消耗不能小于 0")
        normalized[resolution_key] = normalized_cost
    return json.dumps(normalized, ensure_ascii=False, indent=2)


class ExternalApiConfigBase(BaseModel):
    name: str
    description: str = ""
    group_name: str = "默认"
    request_url: str
    request_format: RequestFormatType = "json"
    headers_json: str
    payload_json: str
    response_json: str = "{}"
    result_base64_field: str = ""
    status: StatusType = "enabled"

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("名称不能为空")
        return cleaned

    @field_validator("request_url")
    @classmethod
    def validate_request_url(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("请求地址不能为空")
        return cleaned

    @field_validator("request_format")
    @classmethod
    def validate_request_format(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if cleaned not in {"json", "multipart"}:
            raise ValueError("请求格式只能是 json 或 multipart")
        return cleaned

    @field_validator("description")
    @classmethod
    def validate_description(cls, value: str) -> str:
        return value.strip()

    @field_validator("group_name")
    @classmethod
    def validate_group_name(cls, value: str) -> str:
        return value.strip()

    @field_validator("headers_json")
    @classmethod
    def validate_headers_json(cls, value: str) -> str:
        return _validate_json_text(value, "Header JSON", expect_object=True)

    @field_validator("payload_json")
    @classmethod
    def validate_payload_json(cls, value: str) -> str:
        return _validate_json_text(value, "请求 JSON", expect_object=False)

    @field_validator("response_json")
    @classmethod
    def validate_response_json(cls, value: str) -> str:
        return _validate_json_text(value, "响应 JSON", expect_object=False)

    @field_validator("result_base64_field")
    @classmethod
    def validate_result_base64_field(cls, value: str) -> str:
        return (value or "").strip()

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if cleaned not in {"enabled", "disabled"}:
            raise ValueError("状态只能是 enabled 或 disabled")
        return cleaned


class ExternalApiConfigCreate(ExternalApiConfigBase):
    pass


class ExternalApiConfigUpdate(ExternalApiConfigBase):
    pass


class ExternalApiConfigStatusUpdate(BaseModel):
    status: StatusType

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        return value.strip().lower()


class ExternalApiConfigOut(BaseModel):
    id: int
    name: str
    description: str
    group_name: str
    request_url: str
    request_format: RequestFormatType
    headers_json: str
    payload_json: str
    response_json: str
    result_base64_field: str
    status: StatusType
    created_at: datetime
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class RenderedExternalApiConfig(BaseModel):
    request_url: str
    request_format: RequestFormatType = "json"
    headers: dict[str, str]
    payload: Any


class GenerationModelOptionOut(BaseModel):
    model_key: str
    model_label: str
    model_description: str
    display_name: str
    subtitle: str
    sort_order: int
    hide_aspect_ratio: bool
    hide_resolution: bool
    hide_custom_size: bool
    credit_cost: int
    resolution_credit_costs: dict[str, int] = {}
    max_reference_images: int = 0
    aspect_ratio_options: list["SceneOptionItem"] = []
    image_size_options: list["SceneOptionItem"] = []
    custom_size_options: list["SceneOptionItem"] = []


class SceneOptionItem(BaseModel):
    label: str
    value: str


class ExternalApiSceneBindingCreate(BaseModel):
    scene_key: str
    scene_label: str
    scene_description: str = ""
    sort_order: int = 0
    hide_aspect_ratio: bool = False
    hide_resolution: bool = False
    hide_custom_size: bool = True
    api_config_id: int | None = None
    backup_api_config_id: int | None = None
    display_name: str = ""
    subtitle: str = ""
    credit_cost: int
    max_reference_images: int = 0
    scene_type: SceneTypeType = "generate"
    status: StatusType = "enabled"
    aspect_ratio_options_json: str = "[]"
    image_size_options_json: str = "[]"
    custom_size_options_json: str = "[]"
    resolution_mapping_json: str = "{}"
    resolution_credit_costs_json: str = "{}"

    @field_validator("scene_key")
    @classmethod
    def validate_scene_key(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if not cleaned:
            raise ValueError("场景标识不能为空")
        if not all(ch.islower() or ch.isdigit() or ch == "_" for ch in cleaned):
            raise ValueError("场景标识仅支持小写字母、数字和下划线")
        return cleaned

    @field_validator("scene_label", "scene_description", "display_name", "subtitle")
    @classmethod
    def validate_scene_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("sort_order")
    @classmethod
    def validate_sort_order(cls, value: int) -> int:
        if value < 0:
            raise ValueError("排序值不能小于 0")
        return value

    @field_validator("credit_cost")
    @classmethod
    def validate_credit_cost(cls, value: int) -> int:
        if value < 0:
            raise ValueError("积分消耗不能小于 0")
        return value

    @field_validator("max_reference_images")
    @classmethod
    def validate_max_reference_images(cls, value: int) -> int:
        if value < 0:
            raise ValueError("最大参考图张数不能小于 0")
        return value

    @field_validator("status")
    @classmethod
    def validate_binding_status(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if cleaned not in {"enabled", "disabled"}:
            raise ValueError("状态只能是 enabled 或 disabled")
        return cleaned

    @field_validator("aspect_ratio_options_json")
    @classmethod
    def validate_aspect_ratio_options_json(cls, value: str) -> str:
        return _validate_scene_options_json(value, "宽高比选项 JSON")

    @field_validator("image_size_options_json")
    @classmethod
    def validate_image_size_options_json(cls, value: str) -> str:
        return _validate_scene_options_json(value, "生图质量选项 JSON")

    @field_validator("custom_size_options_json")
    @classmethod
    def validate_custom_size_options_json(cls, value: str) -> str:
        return _validate_scene_options_json(value, "自定义分辨率选项 JSON")

    @field_validator("resolution_mapping_json")
    @classmethod
    def validate_resolution_mapping_json(cls, value: str) -> str:
        return _validate_resolution_mapping_json(value, "分辨率映射 JSON")

    @field_validator("resolution_credit_costs_json")
    @classmethod
    def validate_resolution_credit_costs_json(cls, value: str) -> str:
        return _validate_resolution_credit_costs_json(value, "分辨率积分 JSON")


class ExternalApiSceneBindingUpdate(BaseModel):
    api_config_id: int | None = None
    backup_api_config_id: int | None = None
    display_name: str = ""
    subtitle: str = ""
    credit_cost: int
    resolution_credit_costs_json: str = "{}"

    @field_validator("display_name", "subtitle")
    @classmethod
    def validate_scene_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("credit_cost")
    @classmethod
    def validate_credit_cost(cls, value: int) -> int:
        if value < 0:
            raise ValueError("积分消耗不能小于 0")
        return value

    @field_validator("resolution_credit_costs_json")
    @classmethod
    def validate_resolution_credit_costs_json(cls, value: str) -> str:
        return _validate_resolution_credit_costs_json(value, "分辨率积分 JSON")


class ExternalApiSceneBindingMetaUpdate(BaseModel):
    scene_key: str = ""
    scene_label: str
    scene_description: str = ""
    sort_order: int = 0
    hide_aspect_ratio: bool = False
    hide_resolution: bool = False
    hide_custom_size: bool = True
    max_reference_images: int = 0
    aspect_ratio_options_json: str = "[]"
    image_size_options_json: str = "[]"
    custom_size_options_json: str = "[]"
    resolution_mapping_json: str = "{}"
    resolution_credit_costs_json: str = "{}"

    @field_validator("scene_key")
    @classmethod
    def validate_scene_meta_key(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if not cleaned:
            return ""
        if not all(ch.islower() or ch.isdigit() or ch == "_" for ch in cleaned):
            raise ValueError("场景标识仅支持小写字母、数字和下划线")
        return cleaned

    @field_validator("scene_label", "scene_description")
    @classmethod
    def validate_scene_meta_text(cls, value: str) -> str:
        cleaned = value.strip()
        if cls.__name__ and cleaned == "" and value is not None:
            return cleaned
        return cleaned

    @field_validator("sort_order")
    @classmethod
    def validate_meta_sort_order(cls, value: int) -> int:
        if value < 0:
            raise ValueError("排序值不能小于 0")
        return value

    @field_validator("max_reference_images")
    @classmethod
    def validate_meta_max_reference_images(cls, value: int) -> int:
        if value < 0:
            raise ValueError("最大参考图张数不能小于 0")
        return value

    @field_validator("aspect_ratio_options_json")
    @classmethod
    def validate_aspect_ratio_options_json(cls, value: str) -> str:
        return _validate_scene_options_json(value, "宽高比选项 JSON")

    @field_validator("image_size_options_json")
    @classmethod
    def validate_image_size_options_json(cls, value: str) -> str:
        return _validate_scene_options_json(value, "生图质量选项 JSON")

    @field_validator("custom_size_options_json")
    @classmethod
    def validate_custom_size_options_json(cls, value: str) -> str:
        return _validate_scene_options_json(value, "自定义分辨率选项 JSON")

    @field_validator("resolution_mapping_json")
    @classmethod
    def validate_resolution_mapping_json(cls, value: str) -> str:
        return _validate_resolution_mapping_json(value, "分辨率映射 JSON")

    @field_validator("resolution_credit_costs_json")
    @classmethod
    def validate_resolution_credit_costs_json(cls, value: str) -> str:
        return _validate_resolution_credit_costs_json(value, "分辨率积分 JSON")


class ExternalApiSceneBindingStatusUpdate(BaseModel):
    status: StatusType

    @field_validator("status")
    @classmethod
    def validate_scene_status(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if cleaned not in {"enabled", "disabled"}:
            raise ValueError("状态只能是 enabled 或 disabled")
        return cleaned


class ExternalApiSceneBindingOut(BaseModel):
    scene_key: SceneKeyType
    scene_type: SceneTypeType
    scene_label: str
    scene_description: str
    display_name: str
    subtitle: str
    sort_order: int
    hide_aspect_ratio: bool
    hide_resolution: bool
    hide_custom_size: bool
    status: StatusType
    is_builtin: bool
    api_config_id: int | None = None
    api_config_name: str = ""
    api_group_name: str = ""
    api_status: StatusType | None = None
    backup_api_config_id: int | None = None
    backup_api_config_name: str = ""
    backup_api_group_name: str = ""
    backup_api_status: StatusType | None = None
    credit_cost: int
    max_reference_images: int
    aspect_ratio_options_json: str
    image_size_options_json: str
    custom_size_options_json: str
    resolution_mapping_json: str
    resolution_credit_costs_json: str


class TaskSceneConfigOut(BaseModel):
    scene_key: SceneKeyType
    scene_type: SceneTypeType
    scene_label: str
    scene_description: str
    display_name: str
    subtitle: str
    sort_order: int
    hide_aspect_ratio: bool
    hide_resolution: bool
    hide_custom_size: bool
    credit_cost: int
    resolution_credit_costs: dict[str, int]
    max_reference_images: int
    aspect_ratio_options: list[SceneOptionItem]
    image_size_options: list[SceneOptionItem]
    custom_size_options: list[SceneOptionItem]


class ExternalApiConfigTestResult(BaseModel):
    success: bool
    request_url: str
    status_code: int | None = None
    response_preview: str
