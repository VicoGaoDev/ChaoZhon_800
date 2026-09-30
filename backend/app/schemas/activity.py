from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


ActivityStatus = Literal["enabled", "disabled"]


class ActivityBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    image_url: str = Field(..., min_length=1, max_length=500)
    description: str = Field("", max_length=5000)
    status: ActivityStatus = "enabled"
    sort_order: int = 100


class ActivityCreateRequest(ActivityBase):
    pass


class ActivityUpdateRequest(ActivityBase):
    pass


class ActivityStatusUpdateRequest(BaseModel):
    status: ActivityStatus


class ActivityOut(BaseModel):
    activity_id: str
    title: str
    image_url: str
    description: str
    status: ActivityStatus
    sort_order: int
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ActivityListResponse(BaseModel):
    total: int
    items: list[ActivityOut]
