from pathlib import Path

from property_reco.catalog import load_property_catalog, upsert_properties
from property_reco.constraints import parse_constraints_structured
from property_reco.scoring import score_properties
from property_reco.types import PropertyRecord, SessionConstraints


def test_missing_image_uses_fallback(tmp_path: Path):
    catalog = load_property_catalog(str(tmp_path / "catalog"), "property_listings")
    upsert_properties(
        catalog,
        [
            PropertyRecord(
                property_id="PROP-X",
                title="Fallback Image Unit",
                price_aed=1_500_000,
                beds=2,
                baths=2.0,
                area_sqft=1200,
                property_type="Apartment",
                city="Dubai",
                community="Business Bay",
                handover_date="2027-10-01",
                developer="Emaar",
                status="off_plan",
                image_url="",
                detail_url="",
                amenities=["pool"],
                description="Test listing",
            )
        ],
    )
    constraints = SessionConstraints(city="Dubai", hard_fields={"city"})
    cards = score_properties(
        filtered=[
            PropertyRecord(
                property_id="PROP-X",
                title="Fallback Image Unit",
                price_aed=1_500_000,
                beds=2,
                baths=2.0,
                area_sqft=1200,
                property_type="Apartment",
                city="Dubai",
                community="Business Bay",
                handover_date="2027-10-01",
                developer="Emaar",
                status="off_plan",
                image_url="",
                detail_url="",
                amenities=["pool"],
                description="Test listing",
            )
        ],
        constraints=constraints,
    )
    assert cards[0].image_url.startswith("https://picsum.photos/seed/property-fallback")


def test_structured_extraction_fallback_does_not_crash():
    prior = SessionConstraints()
    update = parse_constraints_structured("??? ### gibberish request ###", prior)
    assert update is not None
    assert update.clarification_needed is False

