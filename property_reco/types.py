from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


FieldPriority = Literal["hard", "soft"]


class ConstraintUpdate(BaseModel):
    max_price_aed: float | None = None
    min_price_aed: float | None = None
    beds_min: int | None = None
    beds_max: int | None = None
    area_min_sqft: float | None = None
    area_max_sqft: float | None = None
    property_type: str | None = None
    city: str | None = None
    community: str | None = None
    handover_before: str | None = None
    handover_after: str | None = None
    status: str | None = None
    must_have: list[str] = Field(default_factory=list)
    nice_to_have: list[str] = Field(default_factory=list)
    field_priority: dict[str, FieldPriority] = Field(default_factory=dict)
    clear_fields: list[str] = Field(default_factory=list)
    clarification_needed: bool = False
    notes: str | None = None


class SessionConstraints(BaseModel):
    max_price_aed: float | None = None
    min_price_aed: float | None = None
    beds_min: int | None = None
    beds_max: int | None = None
    area_min_sqft: float | None = None
    area_max_sqft: float | None = None
    property_type: str | None = None
    city: str | None = None
    community: str | None = None
    handover_before: str | None = None
    handover_after: str | None = None
    status: str | None = None
    must_have: list[str] = Field(default_factory=list)
    nice_to_have: list[str] = Field(default_factory=list)
    hard_fields: set[str] = Field(default_factory=set)
    soft_fields: set[str] = Field(default_factory=set)
    last_updated_fields: list[str] = Field(default_factory=list)
    turn_index: int = 0

    def compact_dict(self) -> dict:
        payload = self.model_dump()
        for key in list(payload.keys()):
            if payload[key] in (None, [], {}, set()):
                payload.pop(key, None)
        if "hard_fields" in payload:
            payload["hard_fields"] = sorted(payload["hard_fields"])
        if "soft_fields" in payload:
            payload["soft_fields"] = sorted(payload["soft_fields"])
        return payload


class PropertyRecord(BaseModel):
    property_id: str
    title: str
    price_aed: float
    beds: int
    baths: float
    area_sqft: float
    property_type: str
    city: str
    community: str
    handover_date: str
    developer: str
    status: str
    image_url: str
    detail_url: str
    amenities: list[str] = Field(default_factory=list)
    is_active: bool = True
    description: str = ""


class RecommendationCard(BaseModel):
    property_id: str
    title: str
    image_url: str
    detail_url: str
    price_aed: float
    beds: int
    baths: float
    area_sqft: float
    property_type: str
    city: str
    community: str
    handover_date: str
    developer: str
    status: str
    amenities: list[str] = Field(default_factory=list)
    match_reason: str
    score: float
    score_breakdown: dict[str, float] = Field(default_factory=dict)


class RecommendationResult(BaseModel):
    cards: list[RecommendationCard] = Field(default_factory=list)
    total_candidates: int = 0
    filtered_candidates: int = 0
    hard_filters_applied: list[str] = Field(default_factory=list)
    soft_preferences_applied: list[str] = Field(default_factory=list)
    no_match_reason: str | None = None
    next_relaxation_suggestions: list[str] = Field(default_factory=list)
    session_constraints: SessionConstraints = Field(default_factory=SessionConstraints)
    parsed_update: ConstraintUpdate | None = None

