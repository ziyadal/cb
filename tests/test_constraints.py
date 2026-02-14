from property_reco.constraints import merge_constraints, parse_constraints_structured
from property_reco.types import SessionConstraints


def test_parse_hard_constraints_from_message():
    prior = SessionConstraints()
    update = parse_constraints_structured(
        "I must buy only in Dubai Marina with no more than 2.5m AED and at least 2 bed off-plan.",
        prior,
    )

    assert update.max_price_aed == 2_500_000
    assert update.beds_min == 2
    assert update.community == "Dubai Marina"
    assert update.city == "Dubai"
    assert update.status == "off_plan"
    assert update.field_priority["max_price_aed"] == "hard"
    assert update.field_priority["community"] == "hard"


def test_parse_soft_constraints_from_message():
    prior = SessionConstraints()
    update = parse_constraints_structured(
        "I prefer around 2m in Dubai and ideally a 2 bedroom apartment.",
        prior,
    )

    assert update.max_price_aed == 2_000_000
    assert update.city == "Dubai"
    assert update.beds_min == 2
    assert update.beds_max == 2
    assert update.property_type == "Apartment"
    assert update.field_priority["max_price_aed"] == "soft"


def test_parse_clear_commands():
    prior = SessionConstraints()
    update = parse_constraints_structured("Ignore budget and any location for now.", prior)
    assert "max_price_aed" in update.clear_fields
    assert "min_price_aed" in update.clear_fields
    assert "city" in update.clear_fields
    assert "community" in update.clear_fields


def test_merge_constraints_overrides_and_persists():
    prior = SessionConstraints(
        max_price_aed=2_000_000,
        city="Dubai",
        hard_fields={"max_price_aed", "city"},
        turn_index=2,
    )
    update = parse_constraints_structured("Actually raise budget to 3.5m but keep city.", prior)
    merged = merge_constraints(prior, update)

    assert merged.max_price_aed == 3_500_000
    assert merged.city == "Dubai"
    assert "max_price_aed" in merged.hard_fields
    assert merged.turn_index == 3

