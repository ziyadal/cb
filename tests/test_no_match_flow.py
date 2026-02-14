from pathlib import Path

from property_reco.catalog import load_property_catalog
from property_reco.scoring import recommend_properties_turn
from property_reco.seed import seed_fake_properties
from property_reco.types import SessionConstraints


def test_no_match_response_prompts_expansion(tmp_path: Path):
    csv_path = str(tmp_path / "seed.csv")
    chroma_dir = str(tmp_path / "property_vector_db")
    seed_fake_properties(
        csv_path=csv_path,
        out_chroma_dir=chroma_dir,
        n=20,
        seed=99,
    )
    catalog = load_property_catalog(chroma_dir, "property_listings")
    state = SessionConstraints()

    result, state = recommend_properties_turn(
        "I must have a 5 bedroom villa in Dubai Marina under 200k AED with handover before 2025.",
        state,
        catalog,
    )

    assert result.cards == []
    assert result.filtered_candidates == 0
    assert result.no_match_reason == "No listings match your current criteria."
    assert "Expand budget range" in result.next_relaxation_suggestions
    assert state.turn_index == 1

