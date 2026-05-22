from datetime import date
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class TravelStyle(StrEnum):
    """Supported high-level travel styles."""

    BUDGET = "budget"
    COMFORT = "comfort"
    LUXURY = "luxury"
    FAMILY = "family"
    ADVENTURE = "adventure"
    CULTURE = "culture"
    BUSINESS = "business"


class TravelPlanRequest(BaseModel):
    """Client request to create a travel plan workflow."""

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
        """Normalize currency codes to uppercase ISO-like values."""

        return value.upper()


class TravelRequirements(BaseModel):
    """Structured requirements extracted from a travel planning request."""

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
    """Standard output contract returned by every agent."""

    agent_name: str
    data: dict[str, Any]
    confidence: float = Field(default=0.75, ge=0, le=1)
    warnings: list[str] = Field(default_factory=list)


class ValidationResult(BaseModel):
    """Result produced by the validation agent."""

    is_valid: bool
    conflicts: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)


class TravelPlanResponse(BaseModel):
    """Response containing the workflow identity and final plan status."""

    workflow_id: UUID
    trip_id: UUID | None = None
    status: str
    plan: dict[str, Any] = Field(default_factory=dict)
    validation: ValidationResult | None = None


class ReplanRequest(BaseModel):
    """Client request to create a revised plan from a previous workflow."""

    workflow_id: UUID
    prompt: str = Field(min_length=3, max_length=10_000)


class BookingRequest(BaseModel):
    """Client request to reserve or book a selected travel component."""

    trip_id: UUID
    provider: str = Field(min_length=1, max_length=120)
    selection_id: str = Field(min_length=1, max_length=255)
    payment_token: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
