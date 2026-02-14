from gradio_demo import render_recommendation_cards
from property_reco.types import RecommendationCard, RecommendationResult, SessionConstraints


def test_render_cards_contains_image_and_price():
    result = RecommendationResult(
        cards=[
            RecommendationCard(
                property_id="PROP-0001",
                title="Apartment at Dubai Marina #1",
                image_url="https://example.com/image.jpg",
                detail_url="https://example.com/listing",
                price_aed=2_200_000,
                beds=2,
                baths=2.5,
                area_sqft=1340,
                property_type="Apartment",
                city="Dubai",
                community="Dubai Marina",
                handover_date="2027-06-01",
                developer="Emaar",
                status="off_plan",
                amenities=["pool", "gym"],
                match_reason="Strong location and budget fit.",
                score=0.92,
                score_breakdown={
                    "budget_fit": 0.95,
                    "beds_fit": 1.0,
                    "location_fit": 1.0,
                    "area_fit": 0.75,
                    "handover_fit": 0.82,
                },
            )
        ],
        total_candidates=40,
        filtered_candidates=10,
        session_constraints=SessionConstraints(),
    )
    html = render_recommendation_cards(result)
    assert "<img" in html
    assert "AED 2,200,000" in html
    assert "Dubai Marina" in html


def test_render_no_match_panel():
    result = RecommendationResult(
        cards=[],
        no_match_reason="No listings match your current criteria.",
        next_relaxation_suggestions=["Expand budget range"],
        session_constraints=SessionConstraints(),
    )
    html = render_recommendation_cards(result)
    assert "No listings match your current criteria." in html
    assert "Expand budget range" in html

