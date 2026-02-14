from __future__ import annotations

import argparse
import csv
import os
import random
from datetime import date
from pathlib import Path

from .catalog import load_property_catalog, upsert_properties
from .types import PropertyRecord


def _random_handover(rng: random.Random) -> str:
    year = rng.choice([2026, 2027, 2028, 2029])
    month = rng.randint(1, 12)
    day = min(rng.randint(1, 28), 28)
    return date(year, month, day).isoformat()


def generate_fake_properties(n: int = 40, seed: int = 42) -> list[PropertyRecord]:
    rng = random.Random(seed)
    developers = [
        "Emaar",
        "DAMAC",
        "Aldar",
        "Sobha",
        "Nakheel",
        "Meraas",
    ]
    communities_by_city = {
        "Dubai": [
            "Dubai Marina",
            "Downtown Dubai",
            "Business Bay",
            "JVC",
            "Palm Jumeirah",
            "Dubai Hills",
        ],
        "Abu Dhabi": [
            "Yas Island",
            "Saadiyat Island",
            "Al Reem Island",
            "Al Raha Beach",
        ],
    }
    property_types = ["Apartment", "Townhouse", "Villa", "Penthouse", "Studio"]
    amenities_pool = [
        "pool",
        "gym",
        "park",
        "beach",
        "school",
        "metro",
        "waterfront",
        "concierge",
    ]

    records: list[PropertyRecord] = []
    for idx in range(1, n + 1):
        city = "Dubai" if idx <= int(n * 0.65) else "Abu Dhabi"
        community = rng.choice(communities_by_city[city])
        property_type = rng.choice(property_types)
        beds = rng.choice([1, 2, 3, 4, 5])
        baths = round(max(1.0, beds - 0.5 + rng.random()), 1)
        base_price = {
            "Studio": 850_000,
            "Apartment": 1_350_000,
            "Townhouse": 2_100_000,
            "Villa": 3_800_000,
            "Penthouse": 5_200_000,
        }[property_type]
        city_multiplier = 1.12 if city == "Dubai" else 1.0
        bed_multiplier = 1 + (beds - 1) * 0.25
        variance = rng.uniform(0.82, 1.24)
        price = round(base_price * city_multiplier * bed_multiplier * variance, -3)
        area = round((550 + beds * 380) * rng.uniform(0.88, 1.25), 0)
        developer = rng.choice(developers)
        status = "off_plan" if rng.random() < 0.72 else "ready"
        amenities = sorted(rng.sample(amenities_pool, k=rng.randint(3, 6)))
        property_id = f"PROP-{idx:04d}"
        records.append(
            PropertyRecord(
                property_id=property_id,
                title=f"{property_type} at {community} #{idx}",
                price_aed=float(price),
                beds=beds,
                baths=baths,
                area_sqft=float(area),
                property_type=property_type,
                city=city,
                community=community,
                handover_date=_random_handover(rng),
                developer=developer,
                status=status,
                image_url=f"https://picsum.photos/seed/{property_id.lower()}/960/640",
                detail_url=f"https://example-properties.local/{property_id.lower()}",
                amenities=amenities,
                is_active=True,
                description=(
                    f"{property_type} in {community}, {city}. "
                    f"Developed by {developer}. Suitable for long-term investment."
                ),
            )
        )
    return records


def _write_csv(records: list[PropertyRecord], csv_path: str) -> None:
    path = Path(csv_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "property_id",
        "title",
        "price_aed",
        "beds",
        "baths",
        "area_sqft",
        "property_type",
        "city",
        "community",
        "handover_date",
        "developer",
        "status",
        "image_url",
        "detail_url",
        "amenities",
        "is_active",
        "description",
    ]
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for record in records:
            row = record.model_dump()
            row["amenities"] = ",".join(record.amenities)
            writer.writerow(row)


def load_properties_from_csv(csv_path: str) -> list[PropertyRecord]:
    rows: list[PropertyRecord] = []
    with open(csv_path, "r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        for item in reader:
            rows.append(
                PropertyRecord(
                    property_id=item["property_id"],
                    title=item["title"],
                    price_aed=float(item["price_aed"]),
                    beds=int(item["beds"]),
                    baths=float(item["baths"]),
                    area_sqft=float(item["area_sqft"]),
                    property_type=item["property_type"],
                    city=item["city"],
                    community=item["community"],
                    handover_date=item["handover_date"],
                    developer=item["developer"],
                    status=item["status"],
                    image_url=item["image_url"],
                    detail_url=item["detail_url"],
                    amenities=[p.strip() for p in item.get("amenities", "").split(",") if p.strip()],
                    is_active=item.get("is_active", "True").lower() == "true",
                    description=item.get("description", ""),
                )
            )
    return rows


def seed_fake_properties(
    csv_path: str,
    out_chroma_dir: str,
    n: int = 40,
    seed: int = 42,
    collection_name: str = "property_listings",
) -> None:
    records = generate_fake_properties(n=n, seed=seed)
    _write_csv(records, csv_path)
    catalog = load_property_catalog(out_chroma_dir, collection_name)
    upsert_properties(catalog, records)


def seed_from_existing_csv(
    csv_path: str,
    out_chroma_dir: str,
    collection_name: str = "property_listings",
) -> None:
    records = load_properties_from_csv(csv_path)
    catalog = load_property_catalog(out_chroma_dir, collection_name)
    upsert_properties(catalog, records)


def _main() -> None:
    parser = argparse.ArgumentParser(description="Generate and seed fake property listings into Chroma.")
    parser.add_argument("--csv-path", default="data/properties_seed.csv")
    parser.add_argument("--chroma-dir", default="property_vector_db")
    parser.add_argument("--collection", default="property_listings")
    parser.add_argument("--count", type=int, default=40)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--mode",
        choices=["generate-and-seed", "seed-existing"],
        default="generate-and-seed",
    )
    args = parser.parse_args()

    if args.mode == "generate-and-seed":
        seed_fake_properties(
            csv_path=args.csv_path,
            out_chroma_dir=args.chroma_dir,
            n=args.count,
            seed=args.seed,
            collection_name=args.collection,
        )
    else:
        if not os.path.exists(args.csv_path):
            raise FileNotFoundError(f"CSV not found: {args.csv_path}")
        seed_from_existing_csv(
            csv_path=args.csv_path,
            out_chroma_dir=args.chroma_dir,
            collection_name=args.collection,
        )


if __name__ == "__main__":
    _main()

