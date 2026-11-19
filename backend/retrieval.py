"""Shared hybrid retrieval, exact entity matching, source scopes, and raw distances."""

from __future__ import annotations

import math
import re
import threading
import time
import unicodedata
from collections import Counter

from backend.csv_importer import classify_page
from backend.data_access import (
    DEFAULT_POLICY,
    SEARCHABLE_PAGE_TYPES,
    SourcePolicy,
    document_id,
    normalize_source,
)
from backend.embedding import cached_encoder

STOP_WORDS = frozenset(["a", "an", "and", "are", "as", "at", "be", "by", "can", "could", "does", "for", "from", "give", "has", "have", "how", "i", "in", "is", "it", "me", "of", "on", "or", "please", "tell", "that", "the", "their", "this", "to", "what", "when", "where", "which", "with", "would", "you", "about", "property", "properties", "estate", "real"])
REQUEST_LOCATION_WORDS = {"location", "located", "where", "address", "الموقع", "المدينة", "الحي"}
TOPICS = {
    "bedrooms": {"bedroom", "bed", "غرف", "نوم"},
    "amenities": {"amenity", "facility", "pool", "spa", "sauna", "gym", "fitness", "parking", "garden", "balcony", "مميزات", "مرافق"},
    "location": {"location", "located", "city", "neighborhood", "neighbourhood", "where", "address", "street", "london", "riyadh", "jeddah", "dubai", "marjan", "muscat", "saudi", "الموقع", "المدينة", "الحي"},
    "size": {"size", "area", "sqm", "sqft", "measurement", "المساحة", "مساحة"},
    "price": {"price", "cost", "sar", "aed", "usd", "gbp", "السعر", "ريال"},
    "handover": {"handover", "completion", "delivery", "تسليم"},
}
_catalogs = {}
_catalog_lock = threading.RLock()


def tokens(text: str, *, stopwords: bool = True) -> list[str]:
    text = re.sub(r"\b(Location|Price|Bedrooms|Bathrooms|Units|Area|Status)(?=[A-Z0-9])", r"\1 ", text)
    text = unicodedata.normalize("NFKC", text).casefold()
    text = "".join(str(unicodedata.digit(character)) if character.isdigit() else character for character in text)
    text = re.sub(r"(?<=\d)[,٬](?=\d)", "", text)
    text = text.replace("m²", "sqm").replace("m2", "sqm")
    values = re.findall(r"[^\W_]+", text, flags=re.UNICODE)
    result = []
    for value in values:
        if value.endswith("ies") and len(value) > 5:
            value = value[:-3] + "y"
        elif value.endswith("s") and len(value) > 3 and not value.endswith("ss"):
            value = value[:-1]
        if not stopwords or value not in STOP_WORDS:
            result.append(value)
    return result


def requested_topics(query: str) -> set[str]:
    query_tokens = set(tokens(query, stopwords=False))
    return {topic for topic, words in TOPICS.items()
        if query_tokens & (REQUEST_LOCATION_WORDS if topic == "location" else words)}


def inferred_page_types(query: str) -> list[str] | None:
    """Scope explicit knowledge kinds without treating place names as attribute requests."""
    words = set(tokens(query, stopwords=False))
    if words & {"auction", "مزاد", "مزادات"}:
        return ["auction"]
    if words & {"service", "company", "corporate", "خدمات"}:
        return ["company"]
    if words & {"sale", "rent", "rental"} or re.search(r"types of properties", query, re.IGNORECASE):
        return ["project_directory", "company"]
    return None


def evidence_topics(record: dict) -> set[str]:
    body = record.get("body") or record.get("document") or ""
    section = record.get("metadata", {}).get("section", "")
    values = set(tokens(body + " " + section, stopwords=False))
    found = {topic for topic, words in TOPICS.items() if values & words}
    if record.get("metadata", {}).get("page_type") == "individual_property":
        lower = body.casefold()
        if "size" in found and not (re.search(r"\d[^\n]*(?:sqm|sqft|m²|m2|square (?:feet|met))", lower) or re.search(r"(?:sqm|sqft|m²|m2|square (?:feet|met))[^\n]*\d", lower)):
            found.discard("size")
        if "handover" in found:
            dated_handover = any(re.search(r"handover|completion|delivery|تسليم", line, re.IGNORECASE)
                and re.search(r"\b20\d{2}\b", line) for line in body.splitlines())
            dated_section = section.casefold() in {"handover", "handover date", "completion", "تسليم"} and bool(re.search(r"\b20\d{2}\b", lower))
            if not dated_handover and not dated_section:
                found.discard("handover")
        price_lines = [line for line in body.splitlines() if re.search(r"price|pricing|cost|asking|starting from|السعر", line, re.IGNORECASE)]
        section_price = section.casefold() in {"price", "pricing", "السعر"} and bool(re.search(r"\d", body)) and "%" not in body
        explicit_price = any(
            not re.search(r"tax|visa|yield|market|investment|premium|appreciation", line, re.IGNORECASE)
            and (re.search(r"(?:price|cost|asking price|starting from|السعر)\s*(?::|=|is|from)?\s*(?:SAR|AED|USD|GBP|EUR|[$£€])?\s*\d", line, re.IGNORECASE)
                or (re.search(r"\d", line) and re.search(r"\b(?:SAR|AED|USD|GBP|EUR)\b|[$£€]", line)))
            and "%" not in line
            for line in price_lines
        )
        if "price" in found and not section_price and not explicit_price:
            found.discard("price")
    return found


def source_where(policy: SourcePolicy, sources: list[str] | None) -> dict | None:
    branches = policy.source_branches(sources)
    if not branches:
        return None
    return branches[0] if len(branches) == 1 else {"$or": branches}


def inferred_sources(query: str) -> list[str] | None:
    lower = query.casefold()
    names = [name for name in ("darglobal", "wasalt") if name in lower or (name == "darglobal" and "dar global" in lower)]
    return names or None


def _record(identity: str, document: str, metadata: dict, policy: SourcePolicy) -> dict | None:
    if not metadata.get("source") or not metadata.get("url") or not metadata.get("title"):
        return None
    source = normalize_source(metadata["source"])
    origin = metadata.get("data_origin", "legacy")
    try:
        policy.require_url(source, metadata["url"], origin)
    except PermissionError:
        return None
    page_type = metadata.get("page_type") or classify_page(source, metadata["url"], metadata["title"], document)[0]
    if page_type not in SEARCHABLE_PAGE_TYPES:
        return None
    normalized = {**metadata, "source": source, "page_type": page_type,
        "document_id": metadata.get("document_id") or document_id(source, metadata["url"]),
        "section": metadata.get("section", "Legacy summary"), "data_origin": origin}
    body = document.split("\n\n", 1)[-1] if metadata.get("preparation_version") and document.startswith("Title:") else document
    return {"id": identity, "document": document, "body": body, "metadata": normalized, "distance": None}


def invalidate_catalog(collection_id: str | None = None) -> None:
    with _catalog_lock:
        if collection_id is None:
            _catalogs.clear()
        else:
            for key in list(_catalogs):
                if key[0] == collection_id:
                    del _catalogs[key]


def catalog(collection, sources: list[str] | None, policy: SourcePolicy = DEFAULT_POLICY) -> list[dict]:
    where = source_where(policy, sources)
    if where is None:
        return []
    key = (str(collection.id), repr(where), policy.allow_synthetic)
    count = collection.count()
    with _catalog_lock:
        cached = _catalogs.get(key)
        if cached and cached[0] == count and time.monotonic() - cached[1] < 30:
            return cached[2]
    records = []
    offset = 0
    while True:
        batch = collection.get(where=where, limit=500, offset=offset, include=["documents", "metadatas"])
        ids = batch["ids"]
        for identity, document, metadata in zip(ids, batch["documents"], batch["metadatas"], strict=True):
            try:
                record = _record(identity, document or "", metadata or {}, policy)
            except ValueError:
                record = None
            if record:
                records.append(record)
        if len(ids) < 500:
            break
        offset += len(ids)
    with _catalog_lock:
        _catalogs[key] = (count, time.monotonic(), records)
    return records


def _entities(query: str, records: list[dict]) -> set[str]:
    query_values = tokens(query)
    matches = []
    for record in records:
        metadata = record["metadata"]
        if metadata["page_type"] != "individual_property":
            continue
        title = re.split(r"[|,]", metadata["title"], maxsplit=1)[0]
        core = tokens(title)
        if core:
            for start in range(len(query_values) - len(core) + 1):
                if query_values[start:start + len(core)] == core:
                    matches.append((metadata["document_id"], start, start + len(core)))
    return {
        identity for identity, start, end in matches
        if not any(other_start <= start and end <= other_end and other_end - other_start > end - start
            for _, other_start, other_end in matches)
    }


def _lexical(query: str, records: list[dict]) -> list[tuple[dict, float, float]]:
    wanted = tokens(query)
    document_tokens = [tokens(record["metadata"]["title"] + " " + record["body"]) for record in records]
    average = sum(len(values) for values in document_tokens) / max(len(document_tokens), 1)
    frequency = Counter(word for values in document_tokens for word in set(values))
    scored = []
    for record, values in zip(records, document_tokens, strict=True):
        counts = Counter(values)
        score = 0.0
        for word in wanted:
            occurrences = counts[word]
            if occurrences:
                inverse = math.log(1 + (len(records) - frequency[word] + 0.5) / (frequency[word] + 0.5))
                score += inverse * occurrences * 2.2 / (occurrences + 1.2 * (0.25 + 0.75 * len(values) / max(average, 1)))
        coverage = len(set(wanted) & set(values)) / max(len(set(wanted)), 1)
        scored.append((record, score, coverage))
    return sorted(scored, key=lambda item: (-item[1], item[0]["id"]))


def hybrid_search(
    collection, query: str, *, encoder=None, k: int = 4, sources: list[str] | None = None,
    page_types: list[str] | None = None, property_name: str | None = None, parent_id: str | None = None,
    policy: SourcePolicy = DEFAULT_POLICY, max_distance: float | None = None,
) -> list[dict]:
    if not query.strip() or k <= 0 or sources == []:
        return []
    sources = sources if sources is not None else inferred_sources(query)
    records = catalog(collection, sources, policy)
    if page_types is not None:
        records = [record for record in records if record["metadata"]["page_type"] in page_types]
    matched = _entities(property_name or query, records)
    if parent_id:
        matched = {parent_id}
    if property_name and not matched:
        return []
    if matched:
        records = [record for record in records if record["metadata"]["document_id"] in matched and (parent_id or record["metadata"]["page_type"] == "individual_property")]
    elif page_types is None and inferred_page_types(query):
        kinds = inferred_page_types(query)
        records = [record for record in records if record["metadata"]["page_type"] in kinds]
    elif requested_topics(query) & {"bedrooms", "amenities", "size", "handover"}:
        records = [record for record in records if record["metadata"]["page_type"] == "individual_property"]
    if not records:
        return []
    lexical = _lexical(query, records)
    allowed = {record["id"] for record in records}
    where = source_where(policy, sources)
    if page_types is not None or inferred_page_types(query) or matched:
        # Query the actual allowed documents so unrelated page types cannot exhaust semantic candidates.
        urls = sorted({record["metadata"]["url"] for record in records})
        where = {"$and": [where, {"url": {"$in": urls}}]}
    encoder = encoder or cached_encoder()
    vector = encoder.encode(query.strip(), convert_to_numpy=True, normalize_embeddings=True)
    result = collection.query(query_embeddings=[vector], n_results=min(collection.count(), max(24, k * 4)), where=where)
    semantic = {}
    for rank, (identity, distance) in enumerate(zip(result["ids"][0], result["distances"][0], strict=True), start=1):
        if identity in allowed:
            semantic[identity] = (rank, float(distance))
    configuration = collection.configuration or {}
    metric = (configuration.get("hnsw") or configuration.get("spann") or {}).get("space")
    cutoff = max_distance if max_distance is not None else {"cosine": 0.75, "l2": 1.0}.get(metric)
    topics = requested_topics(query)
    ranked = []
    for rank, (record, lexical_score, coverage) in enumerate(lexical, start=1):
        semantic_rank, distance = semantic.get(record["id"], (None, None))
        semantic_relevant = cutoff is not None and distance is not None and distance <= cutoff
        if not matched and coverage < 0.2 and not semantic_relevant:
            continue
        fusion = (1 / (60 + rank) if lexical_score > 0 else 0) + (1 / (60 + semantic_rank) if semantic_rank else 0)
        facts = evidence_topics(record) & topics
        score = fusion + coverage * 0.1 + len(facts) * 0.05
        section = record["metadata"].get("section", "").casefold()
        if not topics:
            # Overview questions need descriptions, not navigation or market-number fragments.
            if section in {"content", "description", "our products", "albert hall mansions history", "a prestigious address", "location", "amenities"}:
                score += 0.06 if len(record["body"].split()) >= 10 else 0.01
            if section == "frequently asked questions":
                score += 0.025
            if matched and section in {"why invest", "dg1", "floor plans"}:
                score -= 0.08
        ranked.append({**record, "distance": distance, "lexical_score": lexical_score,
            "rank_score": score, "matched_topics": sorted(facts),
            "retrieval_methods": [method for method, present in (("lexical", lexical_score > 0), ("semantic", semantic_rank is not None)) if present]})
    ranked.sort(key=lambda record: (-record["rank_score"], record["id"]))
    # Balance sources, then choose strong sections; weak documents must not displace useful evidence.
    selected = []
    if sources and len(sources) > 1:
        for source in sources:
            candidate = next((record for record in ranked if record["metadata"]["source"] == source), None)
            if candidate:
                selected.append(candidate)
    selected_ids = {record["id"] for record in selected}
    per_document = Counter(record["metadata"]["document_id"] for record in selected)
    for record in ranked:
        identity = record["metadata"]["document_id"]
        if record["id"] in selected_ids or (not matched and per_document[identity] >= 3):
            continue
        selected.append(record)
        selected_ids.add(record["id"])
        per_document[identity] += 1
        if len(selected) >= k:
            break
    selected.extend(record for record in ranked if record["id"] not in selected_ids)
    return selected[:k]
