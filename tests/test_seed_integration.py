from pathlib import Path

from property_reco.catalog import collection_count, load_property_catalog
from property_reco.scoring import recommend_properties_turn
from property_reco.seed import seed_fake_properties
from property_reco.types import SessionConstraints


def test_seed_and_recommendation_roundtrip(tmp_path: Path):
    csv_path = str(tmp_path / "properties_seed.csv")
    chroma_dir = str(tmp_path / "property_vector_db")
    collection = "property_listings"

    seed_fake_properties(
        csv_path=csv_path,
        out_chroma_dir=chroma_dir,
        n=40,
        seed=42,
        collection_name=collection,
    )

    assert Path(csv_path).exists()
    catalog = load_property_catalog(chroma_dir, collection)
    assert collection_count(catalog) == 40

    state = SessionConstraints()
    result_1, state = recommend_properties_turn(
        "I must buy in Dubai, max budget 2.5m, at least 2 bed off-plan.",
        state,
        catalog,
    )
    assert result_1.total_candidates == 40
    assert result_1.filtered_candidates >= 0
    assert len(result_1.cards) <= 3

    result_2, state = recommend_properties_turn(
        "Actually raise budget to 4m and keep Dubai.",
        state,
        catalog,
    )
    assert state.max_price_aed == 4_000_000
    assert state.turn_index == 2
    assert result_2.filtered_candidates >= result_1.filtered_candidates

