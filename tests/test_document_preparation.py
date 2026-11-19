"""Token windows, overlap, full content, source lineage, and deterministic identities."""

from datetime import UTC, datetime

import pytest

from backend.data_access import SourcePolicy, document_id
from backend.document_preparation import (
    PreparationConflict,
    prepare_documents,
    prepare_record,
)
from backend.models import ExtractedRecord


def _long_record():
    return ExtractedRecord(source="darglobal", url="https://darglobal.example/one-of-one/synthetic",
        extracted_at=datetime(2026, 11, 19, tzinfo=UTC), data={
            "title": "Synthetic Chunk Test Residence", "page_type": "individual_property", "description": "",
            "content": "Specifications\n\n" + "A source sentence describing supplied bedrooms, measurements, and property amenities. " * 90,
            "data_origin": "synthetic",
        })


def test_actual_content_and_every_required_metadata_field_are_preserved(actual_documents, profile):
    chunks = prepare_documents(actual_documents, profile=profile)
    assert {chunk.metadata["source"] for chunk in chunks} == {"darglobal", "wasalt"}
    required = {"source", "url", "title", "page_type", "document_id", "chunk_index", "section", "extracted_at",
        "content_fingerprint", "chunk_fingerprint", "preparation_version", "embedding_model", "embedding_revision", "embedding_dimension"}
    assert all(required <= set(chunk.metadata) for chunk in chunks)
    assert all(profile.count(chunk.text) == chunk.token_count <= 256 for chunk in chunks)
    assert any("December 2028" in chunk.body for chunk in chunks)
    assert any("682 - 12,277" in chunk.body for chunk in chunks)
    assert any("61 to 265 sqm" in chunk.body for chunk in chunks)
    assert any(chunk.metadata["page_type"] == "auction" for chunk in chunks)
    assert not any(chunk.metadata["page_type"] == "legal_reference" for chunk in chunks)


def test_long_sections_use_token_bounded_overlapping_source_spans(profile):
    chunks = prepare_record(_long_record(), profile=profile, policy=SourcePolicy(allow_synthetic=True))
    assert len(chunks) > 2
    assert all(chunk.token_count <= 256 and chunk.body_token_count <= 210 for chunk in chunks)
    tokenizer = profile.tokenizer
    first = tokenizer.encode(chunks[0].body, add_special_tokens=False)
    second = tokenizer.encode(chunks[1].body, add_special_tokens=False)
    overlaps = [size for size in range(25, 41) if first[-size:] == second[:size]]
    assert overlaps


def test_short_sections_are_not_padded_and_faqs_are_not_replaced_by_summaries(profile):
    record = _long_record().model_copy(update={"data": {**_long_record().data,
        "content": "Amenities\nPool and sauna.\n\nFrequently Asked Questions\nHandover is December 2028.\n\nOther projects\nUnrelated neighboring project."}})
    chunks = prepare_record(record, profile=profile, policy=SourcePolicy(allow_synthetic=True))
    assert len(chunks) == 2
    assert chunks[0].body == "Pool and sauna."
    assert chunks[1].body == "Handover is December 2028."
    assert not any("Unrelated" in chunk.text for chunk in chunks)


def test_ids_ignore_tracking_parameters_and_extraction_timestamp(profile):
    record = _long_record()
    changed = record.model_copy(update={"url": record.url.upper().replace("HTTPS", "https").replace("DARGLOBAL.EXAMPLE", "darglobal.example") + "?utm_source=retry",
        "extracted_at": datetime(2026, 11, 20, tzinfo=UTC)})
    policy = SourcePolicy(allow_synthetic=True)
    first = prepare_record(record, profile=profile, policy=policy)
    second = prepare_record(changed, profile=profile, policy=policy)
    assert [chunk.id for chunk in first] == [chunk.id for chunk in second]
    assert document_id(record.source, record.url) == document_id(changed.source, changed.url)
    assert len(prepare_documents([record, changed], profile=profile, policy=policy)) == len(first)


def test_conflicting_contents_for_one_canonical_url_stop_preparation(profile):
    record = _long_record()
    changed = record.model_copy(update={"data": {**record.data, "content": "Different supplied source content."}})
    with pytest.raises(PreparationConflict):
        prepare_documents([record, changed], profile=profile, policy=SourcePolicy(allow_synthetic=True))


def test_sources_have_separate_document_identities():
    url = "https://example.test/item"
    assert document_id("darglobal", url) != document_id("wasalt", url)


def test_long_title_and_prefix_still_respect_actual_token_limits(profile):
    record = _long_record().model_copy(update={"data": {**_long_record().data, "title": "A supplied long title " * 100}})
    chunks = prepare_record(record, profile=profile, policy=SourcePolicy(allow_synthetic=True))
    assert all(chunk.metadata["title"] == record.data["title"] for chunk in chunks)
    assert all(chunk.token_count <= 256 for chunk in chunks)


@pytest.mark.parametrize("body,overlap", [(256, 32), (200, 0), (200, 100)])
def test_invalid_chunk_budgets_are_rejected(profile, body, overlap):
    with pytest.raises(ValueError):
        prepare_record(_long_record(), profile=profile, policy=SourcePolicy(allow_synthetic=True), body_tokens=body, overlap_tokens=overlap)
