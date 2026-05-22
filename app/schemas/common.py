from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class APIStatus(StrEnum):
    """Common status values returned by API envelopes."""

    ACCEPTED = "accepted"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class APIEnvelope(BaseModel):
    """Generic API envelope for status, data, and error payloads."""

    status: APIStatus
    data: dict[str, Any] = Field(default_factory=dict)
    error: dict[str, Any] | None = None


class TimestampedSchema(BaseModel):
    """Base schema for ORM-backed timestamped resources."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime
    updated_at: datetime
