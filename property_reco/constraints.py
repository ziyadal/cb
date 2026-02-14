from __future__ import annotations

import os
import re
from datetime import date
from typing import Iterable

from .types import ConstraintUpdate, SessionConstraints

CORE_SCALAR_FIELDS = [
    "max_price_aed",
    "min_price_aed",
    "beds_min",
    "beds_max",
    "area_min_sqft",
    "area_max_sqft",
    "property_type",
    "city",
    "community",
    "handover_before",
    "handover_after",
    "status",
]

CITY_BY_COMMUNITY = {
    "dubai marina": "Dubai",
    "downtown dubai": "Dubai",
    "business bay": "Dubai",
    "jvc": "Dubai",
    "jumeirah village circle": "Dubai",
    "palm jumeirah": "Dubai",
    "dubai hills": "Dubai",
    "yas island": "Abu Dhabi",
    "saadiyat island": "Abu Dhabi",
    "al reem island": "Abu Dhabi",
    "al raha beach": "Abu Dhabi",
}

PROPERTY_TYPES = [
    "apartment",
    "villa",
    "townhouse",
    "penthouse",
    "duplex",
    "studio",
]

AMENITY_TOKENS = [
    "pool",
    "gym",
    "park",
    "beach",
    "school",
    "metro",
    "waterfront",
    "concierge",
]

HARD_HINTS = ("must", "only", "at least", "no more than", "exactly")
SOFT_HINTS = ("prefer", "ideally", "nice to have", "open to")


def _parse_money(value: str) -> float | None:
    cleaned = (
        value.lower()
        .replace("aed", "")
        .replace("$", "")
        .replace(",", "")
        .replace("million", "m")
        .replace("mn", "m")
        .strip()
    )
    match = re.search(r"(\d+(?:\.\d+)?)([mk])?", cleaned)
    if not match:
        return None
    base = float(match.group(1))
    suffix = match.group(2)
    if suffix == "m":
        base *= 1_000_000
    elif suffix == "k":
        base *= 1_000
    return base


def _parse_numeric(value: str) -> float | None:
    match = re.search(r"(\d+(?:\.\d+)?)", value.replace(",", ""))
    return float(match.group(1)) if match else None


def _extract_list_after_phrase(text: str, phrases: Iterable[str]) -> list[str]:
    for phrase in phrases:
        if phrase in text:
            tail = text.split(phrase, 1)[1]
            tail = re.split(r"[.;]", tail)[0]
            parts = re.split(r",| and ", tail)
            clean = [part.strip() for part in parts if part.strip()]
            if clean:
                return clean
    return []


def _maybe_extract_with_llm(message: str, prior: SessionConstraints) -> ConstraintUpdate | None:
    if os.getenv("ENABLE_LLM_CONSTRAINT_EXTRACTION", "0") != "1":
        return None

    try:
        from agents import Agent, Runner
    except Exception:
        return None

    model = os.getenv("CONSTRAINT_EXTRACTOR_MODEL", "gpt-4.1-mini")
    extractor = Agent(
        name="Constraint Extractor",
        model=model,
        output_type=ConstraintUpdate,
        instructions=(
            "Extract structured real-estate constraints from the latest user message. "
            "Return only typed fields. Use field_priority per extracted field as hard or soft."
        ),
    )
    prompt = (
        "Prior constraints:\n"
        f"{prior.compact_dict()}\n\n"
        "Latest user message:\n"
        f"{message}"
    )
    try:
        result = Runner.run_sync(extractor, prompt, max_turns=1)
        return result.final_output_as(ConstraintUpdate, raise_if_incorrect_type=True)
    except Exception:
        return None


def parse_constraints_structured(message: str, prior_constraints: SessionConstraints) -> ConstraintUpdate:
    llm_out = _maybe_extract_with_llm(message, prior_constraints)
    if llm_out is not None:
        return llm_out

    text = message.lower().strip()
    update = ConstraintUpdate()

    if "ignore budget" in text or "any budget" in text:
        update.clear_fields.extend(["max_price_aed", "min_price_aed"])
    if "ignore location" in text or "any location" in text:
        update.clear_fields.extend(["city", "community"])
    if "ignore handover" in text or "any handover" in text:
        update.clear_fields.extend(["handover_before", "handover_after"])

    between_money = re.search(
        r"(?:between|from)\s+([a-z0-9$,\.\s]+?)\s+(?:and|to)\s+([a-z0-9$,\.\s]+)",
        text,
    )
    if between_money:
        low = _parse_money(between_money.group(1))
        high = _parse_money(between_money.group(2))
        if low is not None:
            update.min_price_aed = low
        if high is not None:
            update.max_price_aed = high

    max_budget = re.search(
        r"(?:under|below|less than|no more than|up to|max(?:imum)?(?: budget)?(?: of)?)\s+([a-z0-9$,\.\s]+)",
        text,
    )
    if max_budget:
        parsed = _parse_money(max_budget.group(1))
        if parsed is not None:
            update.max_price_aed = parsed

    budget_to = re.search(
        r"(?:budget|price)(?:\s+\w+){0,3}\s+(?:to|around)\s+([a-z0-9$,\.\s]+)",
        text,
    )
    if budget_to:
        parsed = _parse_money(budget_to.group(1))
        if parsed is not None:
            update.max_price_aed = parsed

    around_budget = re.search(r"(?:around|about|approximately)\s+([a-z0-9$,\.\s]*[mk])", text)
    if around_budget and update.max_price_aed is None:
        parsed = _parse_money(around_budget.group(1))
        if parsed is not None:
            update.max_price_aed = parsed

    min_budget = re.search(
        r"(?:over|above|more than|at least|min(?:imum)?(?: budget)?(?: of)?)\s+([a-z0-9$,\.\s]+)",
        text,
    )
    if min_budget:
        parsed = _parse_money(min_budget.group(1))
        if parsed is not None:
            update.min_price_aed = parsed

    exact_beds = re.search(r"\b(\d+)\s*(?:bed|bedroom|br)\b", text)
    if exact_beds and "at least" not in text and "up to" not in text and "max" not in text:
        value = int(exact_beds.group(1))
        update.beds_min = value
        update.beds_max = value

    min_beds = re.search(r"(?:at least|min(?:imum)?|>=)\s*(\d+)\s*(?:bed|bedroom|br)", text)
    if min_beds:
        update.beds_min = int(min_beds.group(1))

    max_beds = re.search(r"(?:up to|at most|max(?:imum)?|<=)\s*(\d+)\s*(?:bed|bedroom|br)", text)
    if max_beds:
        update.beds_max = int(max_beds.group(1))

    min_area = re.search(r"(?:at least|min(?:imum)?|>=)\s*(\d+(?:,\d+)?)\s*(?:sq ?ft|sqft)", text)
    if min_area:
        parsed = _parse_numeric(min_area.group(1))
        if parsed is not None:
            update.area_min_sqft = parsed

    max_area = re.search(r"(?:up to|at most|max(?:imum)?|<=)\s*(\d+(?:,\d+)?)\s*(?:sq ?ft|sqft)", text)
    if max_area:
        parsed = _parse_numeric(max_area.group(1))
        if parsed is not None:
            update.area_max_sqft = parsed

    for prop_type in PROPERTY_TYPES:
        if prop_type in text:
            update.property_type = prop_type.title()
            break

    if "abu dhabi" in text:
        update.city = "Abu Dhabi"
    elif "dubai" in text:
        update.city = "Dubai"

    for community, city in CITY_BY_COMMUNITY.items():
        if community in text:
            update.community = community.title()
            update.city = city
            break

    before_year = re.search(r"(?:handover\s+)?(?:before|by)\s+(20\d{2})", text)
    after_year = re.search(r"(?:handover\s+)?(?:after|from)\s+(20\d{2})", text)
    in_year = re.search(r"(?:handover\s+)?in\s+(20\d{2})", text)
    if before_year:
        update.handover_before = f"{before_year.group(1)}-12-31"
    if after_year:
        update.handover_after = f"{after_year.group(1)}-01-01"
    if in_year:
        year = in_year.group(1)
        update.handover_after = f"{year}-01-01"
        update.handover_before = f"{year}-12-31"

    if "off-plan" in text or "off plan" in text:
        update.status = "off_plan"
    elif "ready" in text:
        update.status = "ready"

    update.must_have = _extract_list_after_phrase(text, ["must have", "must include", "need"])
    update.nice_to_have = _extract_list_after_phrase(text, ["prefer", "ideally", "nice to have", "open to"])

    for amenity in AMENITY_TOKENS:
        if amenity in text:
            if any(token in text for token in HARD_HINTS):
                if amenity not in update.must_have:
                    update.must_have.append(amenity)
            elif any(token in text for token in SOFT_HINTS):
                if amenity not in update.nice_to_have:
                    update.nice_to_have.append(amenity)

    hard_default = any(token in text for token in HARD_HINTS) or not any(
        token in text for token in SOFT_HINTS
    )
    for field_name in CORE_SCALAR_FIELDS:
        if getattr(update, field_name) is None:
            continue
        update.field_priority[field_name] = "hard" if hard_default else "soft"

    if update.must_have:
        update.field_priority["must_have"] = "hard"
    if update.nice_to_have:
        update.field_priority["nice_to_have"] = "soft"

    if "exactly" in text and update.beds_min is not None:
        update.field_priority["beds_min"] = "hard"
        update.field_priority["beds_max"] = "hard"

    if re.search(r"\b(any|whatever)\b.*\bbeds?\b", text):
        update.clear_fields.extend(["beds_min", "beds_max"])
    if re.search(r"\b(any|whatever)\b.*\btype\b", text):
        update.clear_fields.append("property_type")

    return update


def merge_constraints(prior: SessionConstraints, update: ConstraintUpdate) -> SessionConstraints:
    merged = prior.model_copy(deep=True)

    clear_unique = list(dict.fromkeys(update.clear_fields))
    for field in clear_unique:
        if hasattr(merged, field):
            setattr(merged, field, None if field not in ("must_have", "nice_to_have") else [])
        merged.hard_fields.discard(field)
        merged.soft_fields.discard(field)

    updated_fields: list[str] = []
    for field_name in CORE_SCALAR_FIELDS:
        value = getattr(update, field_name)
        if value is None:
            continue
        setattr(merged, field_name, value)
        updated_fields.append(field_name)
        priority = update.field_priority.get(field_name, "hard")
        if priority == "hard":
            merged.hard_fields.add(field_name)
            merged.soft_fields.discard(field_name)
        else:
            merged.soft_fields.add(field_name)
            merged.hard_fields.discard(field_name)

    if update.must_have:
        merged.must_have = list(dict.fromkeys(item.strip().lower() for item in update.must_have if item.strip()))
        updated_fields.append("must_have")
        merged.hard_fields.add("must_have")
        merged.soft_fields.discard("must_have")

    if update.nice_to_have:
        merged.nice_to_have = list(
            dict.fromkeys(item.strip().lower() for item in update.nice_to_have if item.strip())
        )
        updated_fields.append("nice_to_have")
        merged.soft_fields.add("nice_to_have")
        merged.hard_fields.discard("nice_to_have")

    merged.last_updated_fields = updated_fields
    merged.turn_index += 1

    # Clamp logically invalid ranges
    if (
        merged.min_price_aed is not None
        and merged.max_price_aed is not None
        and merged.min_price_aed > merged.max_price_aed
    ):
        merged.min_price_aed, merged.max_price_aed = merged.max_price_aed, merged.min_price_aed
    if merged.beds_min is not None and merged.beds_max is not None and merged.beds_min > merged.beds_max:
        merged.beds_min, merged.beds_max = merged.beds_max, merged.beds_min
    if (
        merged.area_min_sqft is not None
        and merged.area_max_sqft is not None
        and merged.area_min_sqft > merged.area_max_sqft
    ):
        merged.area_min_sqft, merged.area_max_sqft = merged.area_max_sqft, merged.area_min_sqft

    _validate_handover_order(merged)
    return merged


def _validate_handover_order(merged: SessionConstraints) -> None:
    if not merged.handover_after or not merged.handover_before:
        return
    try:
        after = date.fromisoformat(merged.handover_after)
        before = date.fromisoformat(merged.handover_before)
    except ValueError:
        return
    if after > before:
        merged.handover_after, merged.handover_before = merged.handover_before, merged.handover_after
