from pathlib import Path

from property_reco.catalog import (
    collection_count,
    filter_properties,
    load_property_catalog,
    upsert_properties,
)
from property_reco.scoring import score_properties
from property_reco.seed import generate_fake_properties
from property_reco.types import SessionConstraints


def test_hard_filter_and_score_pipeline(tmp_path: Path):
    catalog = load_property_catalog(str(tmp_path / "catalog"), "property_listings")
    records = generate_fake_properties(n=20, seed=7)
    upsert_properties(catalog, records)

    assert collection_count(catalog) == 20

    constraints = SessionConstraints(
        max_price_aed=4_000_000,
        beds_min=2,
        city="Dubai",
        hard_fields={"max_price_aed", "beds_min", "city"},
    )
    filtered = filter_properties(catalog, constraints)
    assert filtered
    assert all(item.price_aed <= 4_000_000 for item in filtered)
    assert all(item.beds >= 2 for item in filtered)
    assert all(item.city == "Dubai" for item in filtered)

    cards = score_properties(filtered, constraints, top_k=3)
    assert 1 <= len(cards) <= 3
    assert all(card.score >= 0 for card in cards)
    assert cards == sorted(cards, key=lambda card: card.score, reverse=True)

