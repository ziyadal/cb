from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from datetime import date
from typing import Any

import chromadb

from .types import PropertyRecord, SessionConstraints


@dataclass
class CatalogHandle:
    persist_directory: str
    collection_name: str
    client: chromadb.PersistentClient
    collection: Any


def _embedding_for_text(text: str, dim: int = 48) -> list[float]:
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    out: list[float] = []
    for i in range(dim):
        value = digest[i % len(digest)]
        out.append((value / 127.5) - 1.0)
    return out


def load_property_catalog(chroma_dir: str, collection_name: str) -> CatalogHandle:
    os.makedirs(chroma_dir, exist_ok=True)
    client = chromadb.PersistentClient(path=chroma_dir)
    collection = client.get_or_create_collection(
        name=collection_name,
        metadata={"hnsw:space": "cosine"},
    )
    return CatalogHandle(
        persist_directory=chroma_dir,
        collection_name=collection_name,
        client=client,
        collection=collection,
    )


def collection_count(catalog: CatalogHandle) -> int:
    return int(catalog.collection.count())


def _record_to_document(record: PropertyRecord) -> str:
    amenities = ", ".join(record.amenities) if record.amenities else "none listed"
    return (
        f"{record.title}. {record.property_type} in {record.community}, {record.city}. "
        f"Price AED {record.price_aed:,.0f}, {record.beds} bed, {record.baths} bath, "
        f"{record.area_sqft:,.0f} sqft. Handover {record.handover_date}. "
        f"Developer: {record.developer}. Amenities: {amenities}. {record.description}"
    )


def _record_to_metadata(record: PropertyRecord) -> dict[str, Any]:
    return {
        "property_id": record.property_id,
        "title": record.title,
        "price_aed": float(record.price_aed),
        "beds": int(record.beds),
        "baths": float(record.baths),
        "area_sqft": float(record.area_sqft),
        "property_type": record.property_type,
        "city": record.city,
        "community": record.community,
        "handover_date": record.handover_date,
        "developer": record.developer,
        "status": record.status,
        "image_url": record.image_url,
        "detail_url": record.detail_url,
        "amenities": ",".join(record.amenities),
        "is_active": bool(record.is_active),
    }


def upsert_properties(catalog: CatalogHandle, properties: list[PropertyRecord]) -> None:
    if not properties:
        return

    ids = [prop.property_id for prop in properties]
    documents = [_record_to_document(prop) for prop in properties]
    metadatas = [_record_to_metadata(prop) for prop in properties]
    embeddings = [_embedding_for_text(doc) for doc in documents]

    catalog.collection.upsert(
        ids=ids,
        documents=documents,
        metadatas=metadatas,
        embeddings=embeddings,
    )


def _metadata_to_record(metadata: dict[str, Any], document: str | None = None) -> PropertyRecord:
    amenities_raw = str(metadata.get("amenities", "")).strip()
    amenities = [item.strip() for item in amenities_raw.split(",") if item.strip()]
    return PropertyRecord(
        property_id=str(metadata["property_id"]),
        title=str(metadata.get("title", "")),
        price_aed=float(metadata.get("price_aed", 0.0)),
        beds=int(metadata.get("beds", 0)),
        baths=float(metadata.get("baths", 0.0)),
        area_sqft=float(metadata.get("area_sqft", 0.0)),
        property_type=str(metadata.get("property_type", "")),
        city=str(metadata.get("city", "")),
        community=str(metadata.get("community", "")),
        handover_date=str(metadata.get("handover_date", "")),
        developer=str(metadata.get("developer", "")),
        status=str(metadata.get("status", "")),
        image_url=str(metadata.get("image_url", "")),
        detail_url=str(metadata.get("detail_url", "")),
        amenities=amenities,
        is_active=bool(metadata.get("is_active", True)),
        description=document or "",
    )


def list_properties(catalog: CatalogHandle) -> list[PropertyRecord]:
    payload = catalog.collection.get(include=["metadatas", "documents"])
    metadatas = payload.get("metadatas", []) or []
    documents = payload.get("documents", []) or []
    records: list[PropertyRecord] = []
    for index, metadata in enumerate(metadatas):
        if not metadata:
            continue
        document = documents[index] if index < len(documents) else ""
        records.append(_metadata_to_record(metadata, document))
    return records


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except Exception:
        return None


def _community_match(candidate: str, required: str) -> bool:
    candidate_norm = candidate.strip().lower()
    required_norm = required.strip().lower()
    return required_norm in candidate_norm or candidate_norm in required_norm


def _matches_hard_constraints(prop: PropertyRecord, constraints: SessionConstraints) -> bool:
    hard = constraints.hard_fields
    if not prop.is_active:
        return False

    if "max_price_aed" in hard and constraints.max_price_aed is not None and prop.price_aed > constraints.max_price_aed:
        return False
    if "min_price_aed" in hard and constraints.min_price_aed is not None and prop.price_aed < constraints.min_price_aed:
        return False
    if "beds_min" in hard and constraints.beds_min is not None and prop.beds < constraints.beds_min:
        return False
    if "beds_max" in hard and constraints.beds_max is not None and prop.beds > constraints.beds_max:
        return False
    if "area_min_sqft" in hard and constraints.area_min_sqft is not None and prop.area_sqft < constraints.area_min_sqft:
        return False
    if "area_max_sqft" in hard and constraints.area_max_sqft is not None and prop.area_sqft > constraints.area_max_sqft:
        return False
    if "property_type" in hard and constraints.property_type:
        if prop.property_type.lower() != constraints.property_type.lower():
            return False
    if "city" in hard and constraints.city:
        if prop.city.lower() != constraints.city.lower():
            return False
    if "community" in hard and constraints.community:
        if not _community_match(prop.community, constraints.community):
            return False
    if "status" in hard and constraints.status:
        if prop.status.lower() != constraints.status.lower():
            return False

    handover = _parse_date(prop.handover_date)
    before = _parse_date(constraints.handover_before)
    after = _parse_date(constraints.handover_after)
    if "handover_before" in hard and before is not None and handover and handover > before:
        return False
    if "handover_after" in hard and after is not None and handover and handover < after:
        return False

    if "must_have" in hard and constraints.must_have:
        amenities = {item.lower() for item in prop.amenities}
        for required in constraints.must_have:
            if required.lower() not in amenities:
                return False

    return True


def filter_properties(catalog: CatalogHandle, session_constraints: SessionConstraints) -> list[PropertyRecord]:
    properties = list_properties(catalog)
    return [item for item in properties if _matches_hard_constraints(item, session_constraints)]

