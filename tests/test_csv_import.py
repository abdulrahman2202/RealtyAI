"""CSV schema, actual authorized datasets, source adapters, validation, and reports."""

import csv
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from backend.csv_importer import (
    DarGlobalAdapter,
    EmptyRecord,
    WasaltAdapter,
    import_directory,
)
from backend.data_access import SourcePolicy, canonical_url, validate_record
from backend.models import ExtractedRecord
from backend.review import generate_review, preserve_review_timestamps
from scripts.csv_import import extracted_record_to_index_input

ROOT = Path(__file__).resolve().parents[1]


def test_archived_seven_records_remain_in_the_approved_nested_schema():
    saved = json.loads((ROOT / "data/import_review/extracted_records.json").read_text(encoding="utf-8"))
    assert len(saved["records"]) == 7
    for payload in saved["records"]:
        assert set(payload) == {"source", "url", "data", "extracted_at"}
        assert ExtractedRecord.model_validate(payload).model_dump(mode="json") == payload


def test_actual_model_rejects_the_old_flat_shape():
    with pytest.raises(ValidationError):
        ExtractedRecord.model_validate({"source": "darglobal", "url": "https://darglobal.co.uk/the-astera", "title": "The Astera"})


def test_both_actual_datasets_are_processed_without_quarantine(actual_imports):
    assert actual_imports["darglobal"].summary()["csv_files"] == 10
    assert actual_imports["darglobal"].rows_read == 10
    assert len(actual_imports["darglobal"].records) == 7
    assert actual_imports["darglobal"].empty_skipped == 2
    assert actual_imports["darglobal"].duplicate_skipped == 1
    assert actual_imports["wasalt"].summary()["csv_files"] == 6
    assert actual_imports["wasalt"].rows_read == 6
    assert len(actual_imports["wasalt"].records) == 6
    assert all(entry["status"] == "processed" for result in actual_imports.values() for entry in result.files)
    assert all(result.invalid_skipped == 0 for result in actual_imports.values())


def test_real_wasalt_directories_and_auctions_are_not_individual_properties(actual_imports):
    counts = actual_imports["wasalt"].summary()["classification_counts"]
    assert counts == {"auction": 1, "company": 2, "project_directory": 2, "legal_reference": 1}
    assert all(record.source == "wasalt" for record in actual_imports["wasalt"].records)


def test_actual_adapter_handles_alternate_column_names_without_changing_facts(actual_imports):
    source = next(record for record in actual_imports["wasalt"].records if record.data["page_type"] == "company")
    row = {"Listing URL": source.url, "Property Name": source.data["title"],
        "Full Text": source.data["content"], "Summary": source.data["description"], "Extracted At": source.extracted_at.isoformat()}
    converted, metadata = WasaltAdapter().normalize(row)
    assert converted.url == source.url
    assert converted.data["content"] == source.data["content"]
    assert converted.data["title"] == source.data["title"]
    assert converted.extracted_at == source.extracted_at
    assert metadata["timestamp_origin"] == "csv"


def test_synthetic_structured_property_columns_preserve_supplied_measurements_and_prices():
    record, _ = WasaltAdapter().normalize({
        "Listing URL": "https://wasalt.example/en/property/sale/test-villa-123",
        "Property Name": "Synthetic Test Villa", "Bedrooms": "4", "Area (SQM)": "220",
        "Price": "1,200,000", "Currency": "SAR", "Location": "Synthetic City",
    }, origin="synthetic", policy=SourcePolicy(allow_synthetic=True))
    assert record.data["page_type"] == "individual_property"
    assert "Bedrooms: 4" in record.data["content"]
    assert "Area (SQM): 220" in record.data["content"]
    assert "Price: 1,200,000" in record.data["content"]
    assert "Currency: SAR" in record.data["content"]


def test_directory_precedence_overrides_declared_property_type():
    record, _ = DarGlobalAdapter().normalize({
        "URL": "https://darglobal.co.uk/projects/properties-in-uk",
        "Title": "Directory", "Text": "A directory mentioning bedrooms, amenities, and villas.",
        "Page Type": "individual_property",
    })
    assert record.data["page_type"] == "project_directory"


def test_albert_heading_and_original_csv_title_are_preserved(actual_imports):
    result = actual_imports["darglobal"]
    position = next(index for index, record in enumerate(result.records) if "THE-ALBERT-HALL-MANSION" in record.url)
    record = result.records[position]
    assert record.data["title"] == "THE ALBERT HALL MANSION"
    assert result.review_metadata[position]["original_csv_title"] == "Buy Branded Homes | Million Dollar Houses for Sale | Darglobal"
    assert record.url.endswith("THE-ALBERT-HALL-MANSION?utm_source=chatgpt.com")
    assert "canonical_url" not in record.model_dump()


@pytest.mark.parametrize("change", [
    {"URL": ""}, {"URL": "https://wasalt.sa/en/property/sale/wrong-source-1"},
    {"Title": ""}, {"Extracted At": "invalid"}, {"Extracted At": "2026-11-19T12:00:00"},
])
def test_invalid_fields_and_source_mixing_are_rejected(change):
    row = {"URL": "https://darglobal.co.uk/the-astera", "Title": "The Astera",
        "Text": "Extracted residence information and supplied property details."}
    with pytest.raises((ValueError, TypeError, ValidationError)):
        DarGlobalAdapter().normalize({**row, **change})


def test_empty_record_is_explicitly_rejected():
    with pytest.raises(EmptyRecord):
        WasaltAdapter().normalize({"URL": "https://wasalt.sa/en/property/sale/empty-1", "Title": "Empty", "Text": "", "Description": ""})


@pytest.mark.parametrize("delimiter", [",", ";", "\t"])
def test_recursive_discovery_first_url_dedup_and_malformed_rows(tmp_path, delimiter):
    first = tmp_path / "a"
    second = tmp_path / "b"
    first.mkdir()
    second.mkdir()
    row = {"URL": "https://darglobal.co.uk/THE-ASTERA?utm_source=first", "Title": "First title", "Text": "Extracted residence details."}
    for path, value in ((first / "first.csv", row), (second / "second.csv", {**row, "URL": "https://darglobal.co.uk/the-astera?utm_source=second", "Title": "Second title"})):
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=row, delimiter=delimiter)
            writer.writeheader()
            writer.writerow(value)
    with (second / "malformed.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter=delimiter)
        writer.writerow(list(row))
        writer.writerow(["https://darglobal.co.uk/one-of-one/invalid", "Only two columns"])
    result = import_directory(tmp_path, "darglobal")
    assert len(result.files) == 3
    assert len(result.records) == 1
    assert result.records[0].url == row["URL"]
    assert result.records[0].data["title"] == row["Title"]
    assert result.duplicate_skipped == 1
    assert result.invalid_skipped == 1
    assert canonical_url(row["URL"]) == "https://darglobal.co.uk/the-astera"


def test_index_adapter_keeps_full_nested_content(actual_imports):
    record = actual_imports["darglobal"].records[-1]
    nested = extracted_record_to_index_input(record)
    assert set(nested) == {"source", "url", "data", "extracted_at"}
    assert nested["source"] == "darglobal"
    assert nested["data"]["content"] == record.data["content"]
    assert nested["data"]["page_type"] == record.data["page_type"]


def test_pipeline_rejects_unsupported_top_level_fields_and_invalid_nested_types(actual_imports):
    payload = actual_imports["darglobal"].records[0].model_dump(mode="json")
    with pytest.raises(ValueError, match="Unsupported"):
        validate_record({**payload, "canonical_url": payload["url"]})
    with pytest.raises(TypeError):
        validate_record({**payload, "data": "flat data"})


def test_review_outputs_use_actual_sources_and_keep_the_old_archive(tmp_path, profile):
    approved = ROOT / "data/import_review/extracted_records.json"
    before = approved.read_bytes()
    summary = generate_review(ROOT / "data/raw/darglobal", ROOT / "data/raw/wasalt", tmp_path,
        approved_darglobal_review=approved, profile=profile)
    assert summary["documents"] == 13
    assert approved.read_bytes() == before
    assert {path.name for path in tmp_path.iterdir()} == {
        "darglobal_import_report.md", "wasalt_import_report.md", "combined_import_report.md",
        "chunk_review.json", "proposed_ingestion_manifest.json",
    }
    preview = json.loads((tmp_path / "chunk_review.json").read_text(encoding="utf-8"))
    assert {chunk["metadata"]["source"] for chunk in preview["chunks"]} == {"darglobal", "wasalt"}
    assert all(chunk["token_count"] <= 256 for chunk in preview["chunks"])
    assert not any(chunk["metadata"]["page_type"] == "legal_reference" for chunk in preview["chunks"])
    manifest = json.loads((tmp_path / "proposed_ingestion_manifest.json").read_text(encoding="utf-8"))
    assert manifest["state"] == "review_only"
    assert manifest["persistent_collection_accessed"] is False
    assert manifest["added_count"] == 0


def test_approved_darglobal_extraction_timestamps_are_reused_without_writing_the_archive(tmp_path):
    result = import_directory(ROOT / "data/raw/darglobal", "darglobal")
    preserve_review_timestamps(result, ROOT / "data/import_review/extracted_records.json")
    assert all(metadata["timestamp_origin"] == "preserved_approved_review" for metadata in result.review_metadata)
    assert result.records[0].extracted_at == datetime(2026, 11, 19, 13, 25, 33, 655735, tzinfo=UTC)
