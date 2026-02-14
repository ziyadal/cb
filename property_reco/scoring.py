from __future__ import annotations

from datetime import date
from typing import Iterable

from .catalog import CatalogHandle, filter_properties, list_properties
from .constraints import merge_constraints, parse_constraints_structured
from .types import (
    ConstraintUpdate,
    PropertyRecord,
    RecommendationCard,
    RecommendationResult,
    SessionConstraints,
)

WEIGHTS = {
    "budget_fit": 0.40,
    "beds_fit": 0.20,
    "location_fit": 0.20,
    "area_fit": 0.10,
    "handover_fit": 0.10,
}


def _clamp_unit(value: float) -> float:
    return max(0.0, min(1.0, value))


def _safe_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except Exception:
        return None


def _budget_target(constraints: SessionConstraints) -> float | None:
    if constraints.min_price_aed and constraints.max_price_aed:
        return (constraints.min_price_aed + constraints.max_price_aed) / 2
    if constraints.max_price_aed:
        return constraints.max_price_aed
    if constraints.min_price_aed:
        return constraints.min_price_aed
    return None


def _budget_fit(prop: PropertyRecord, constraints: SessionConstraints) -> float:
    target = _budget_target(constraints)
    if target is None:
        return 0.5
    if target <= 0:
        return 0.0
    distance_ratio = abs(prop.price_aed - target) / target
    return _clamp_unit(1.0 - distance_ratio)


def _beds_fit(prop: PropertyRecord, constraints: SessionConstraints) -> float:
    if constraints.beds_min is None and constraints.beds_max is None:
        return 0.5

    if constraints.beds_min is not None and constraints.beds_max is not None:
        midpoint = (constraints.beds_min + constraints.beds_max) / 2
        tolerance = max((constraints.beds_max - constraints.beds_min) / 2, 1.0)
    elif constraints.beds_min is not None:
        midpoint = float(constraints.beds_min)
        tolerance = max(float(constraints.beds_min), 1.0)
    else:
        midpoint = float(constraints.beds_max)
        tolerance = max(float(constraints.beds_max), 1.0)

    distance = abs(prop.beds - midpoint)
    return _clamp_unit(1.0 - (distance / tolerance))


def _area_fit(prop: PropertyRecord, constraints: SessionConstraints) -> float:
    if constraints.area_min_sqft is None and constraints.area_max_sqft is None:
        return 0.5

    if constraints.area_min_sqft is not None and constraints.area_max_sqft is not None:
        midpoint = (constraints.area_min_sqft + constraints.area_max_sqft) / 2
        tolerance = max((constraints.area_max_sqft - constraints.area_min_sqft) / 2, 100.0)
    elif constraints.area_min_sqft is not None:
        midpoint = float(constraints.area_min_sqft)
        tolerance = max(midpoint * 0.5, 100.0)
    else:
        midpoint = float(constraints.area_max_sqft)
        tolerance = max(midpoint * 0.5, 100.0)

    distance = abs(prop.area_sqft - midpoint)
    return _clamp_unit(1.0 - (distance / tolerance))


def _location_fit(prop: PropertyRecord, constraints: SessionConstraints) -> float:
    if constraints.community:
        if prop.community.lower() == constraints.community.lower():
            return 1.0
        if prop.city.lower() == (constraints.city or prop.city).lower():
            return 0.6
        return 0.0
    if constraints.city:
        return 1.0 if prop.city.lower() == constraints.city.lower() else 0.0
    return 0.5


def _handover_fit(prop: PropertyRecord, constraints: SessionConstraints) -> float:
    handover = _safe_date(prop.handover_date)
    if handover is None:
        return 0.0

    before = _safe_date(constraints.handover_before)
    after = _safe_date(constraints.handover_after)
    if before is None and after is None:
        return 0.5

    if before and after:
        midpoint = after.toordinal() + (before.toordinal() - after.toordinal()) / 2
        distance = abs(handover.toordinal() - midpoint)
        tolerance = max((before.toordinal() - after.toordinal()) / 2, 1.0)
        return _clamp_unit(1.0 - distance / tolerance)

    if before:
        if handover <= before:
            return 1.0
        overflow = handover.toordinal() - before.toordinal()
        return _clamp_unit(1.0 - overflow / 365.0)

    if after:
        if handover >= after:
            return 1.0
        underflow = after.toordinal() - handover.toordinal()
        return _clamp_unit(1.0 - underflow / 365.0)

    return 0.5


def _metadata_completeness(prop: PropertyRecord) -> float:
    fields = [
        prop.title,
        prop.price_aed,
        prop.beds,
        prop.baths,
        prop.area_sqft,
        prop.property_type,
        prop.city,
        prop.community,
        prop.handover_date,
        prop.developer,
        prop.status,
        prop.image_url,
        prop.detail_url,
    ]
    available = sum(1 for value in fields if value not in (None, "", 0))
    return available / len(fields)


def _match_reason(prop: PropertyRecord, breakdown: dict[str, float], constraints: SessionConstraints) -> str:
    top_items = sorted(breakdown.items(), key=lambda item: item[1], reverse=True)[:2]
    labels = {
        "budget_fit": "price alignment",
        "beds_fit": "bedroom fit",
        "location_fit": "location match",
        "area_fit": "size fit",
        "handover_fit": "handover fit",
    }
    reasons = [labels.get(name, name) for name, score in top_items if score >= 0.65]
    if not reasons:
        reasons = ["overall profile fit"]
    return (
        f"Strong {', '.join(reasons)} for your current criteria in "
        f"{constraints.community or constraints.city or prop.city}."
    )


def score_properties(
    filtered: list[PropertyRecord],
    constraints: SessionConstraints,
    top_k: int = 3,
) -> list[RecommendationCard]:
    target_budget = _budget_target(constraints)
    scored: list[tuple[float, float, float, PropertyRecord, dict[str, float]]] = []

    for prop in filtered:
        breakdown = {
            "budget_fit": round(_budget_fit(prop, constraints), 6),
            "beds_fit": round(_beds_fit(prop, constraints), 6),
            "location_fit": round(_location_fit(prop, constraints), 6),
            "area_fit": round(_area_fit(prop, constraints), 6),
            "handover_fit": round(_handover_fit(prop, constraints), 6),
        }
        score = round(sum(WEIGHTS[key] * breakdown[key] for key in WEIGHTS), 6)
        budget_gap = abs(prop.price_aed - target_budget) if target_budget is not None else 0.0
        completeness = _metadata_completeness(prop)
        scored.append((score, budget_gap, completeness, prop, breakdown))

    scored.sort(key=lambda row: (-row[0], row[1], -row[2], row[3].property_id))
    cards: list[RecommendationCard] = []
    for score, _, _, prop, breakdown in scored[:top_k]:
        cards.append(
            RecommendationCard(
                property_id=prop.property_id,
                title=prop.title,
                image_url=prop.image_url or "https://picsum.photos/seed/property-fallback/960/640",
                detail_url=prop.detail_url or "#",
                price_aed=prop.price_aed,
                beds=prop.beds,
                baths=prop.baths,
                area_sqft=prop.area_sqft,
                property_type=prop.property_type,
                city=prop.city,
                community=prop.community,
                handover_date=prop.handover_date,
                developer=prop.developer,
                status=prop.status,
                amenities=prop.amenities,
                match_reason=_match_reason(prop, breakdown, constraints),
                score=score,
                score_breakdown=breakdown,
            )
        )
    return cards


def recommend_properties_turn(
    message: str,
    session_state: SessionConstraints,
    catalog: CatalogHandle,
) -> tuple[RecommendationResult, SessionConstraints]:
    update: ConstraintUpdate = parse_constraints_structured(message, session_state)
    merged = merge_constraints(session_state, update)

    all_candidates = list_properties(catalog)
    filtered = filter_properties(catalog, merged)

    hard_filters = sorted(merged.hard_fields)
    soft_preferences = sorted(merged.soft_fields)

    if not filtered:
        result = RecommendationResult(
            cards=[],
            total_candidates=len(all_candidates),
            filtered_candidates=0,
            hard_filters_applied=hard_filters,
            soft_preferences_applied=soft_preferences,
            no_match_reason="No listings match your current criteria.",
            next_relaxation_suggestions=[
                "Expand budget range",
                "Widen location",
                "Adjust bedroom requirement",
                "Broaden handover window",
            ],
            session_constraints=merged,
            parsed_update=update,
        )
        return result, merged

    cards = score_properties(filtered, merged, top_k=3)
    result = RecommendationResult(
        cards=cards,
        total_candidates=len(all_candidates),
        filtered_candidates=len(filtered),
        hard_filters_applied=hard_filters,
        soft_preferences_applied=soft_preferences,
        session_constraints=merged,
        parsed_update=update,
    )
    return result, merged
