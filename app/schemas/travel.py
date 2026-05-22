from datetime import date
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class TravelStyle(StrEnum):
    BUDGET = "budget"
    COMFORT = "comfort"
    LUXURY = "luxury"
    FAMILY = "family"
    ADVENTURE = "adventure"
    CULTURE = "culture"
    BUSINESS = "business"


class TravelPlanRequest(BaseModel):
    user_id: UUID | None = None
    prompt: str = Field(min_length=5, max_length=10_000)
    origin: str | None = Field(default=None, max_length=255)
    destination: str | None = Field(default=None, max_length=255)
    start_date: date | None = None
    end_date: date | None = None
    travelers: int = Field(default=1, ge=1, le=20)
    budget_amount: float | None = Field(default=None, gt=0)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    preferences: list[str] = Field(default_factory=list)
    travel_style: TravelStyle | None = None

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.upper()


class TravelRequirements(BaseModel):
    origin: str | None = None
    destination: str
    start_date: date | None = None
    end_date: date | None = None
    duration_days: int = Field(ge=1)
    travelers: int = Field(ge=1)
    budget_amount: float | None = None
    currency: str = "USD"
    preferences: list[str] = Field(default_factory=list)
    travel_style: TravelStyle = TravelStyle.COMFORT
    visa_requirements: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)


class AgentOutput(BaseModel):
    agent_name: str
    data: dict[str, Any]
    confidence: float = Field(default=0.75, ge=0, le=1)
    warnings: list[str] = Field(default_factory=list)


class ValidationResult(BaseModel):
    is_valid: bool
    conflicts: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)


class TravelPlanResponse(BaseModel):
    workflow_id: UUID
    trip_id: UUID | None = None
    status: str
    plan: dict[str, Any] = Field(default_factory=dict)
    validation: ValidationResult | None = None


class ReplanRequest(BaseModel):
    workflow_id: UUID
    prompt: str = Field(min_length=3, max_length=10_000)


class BookingRequest(BaseModel):
    trip_id: UUID
    provider: str = Field(min_length=1, max_length=120)
    selection_id: str = Field(min_length=1, max_length=255)
    payment_token: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
