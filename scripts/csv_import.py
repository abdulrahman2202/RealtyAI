#!/usr/bin/env python3
"""Phase 6.11 CSV review command: process both actual sources without production ingestion."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.csv_importer import DarGlobalAdapter, WasaltAdapter, classify_page
from backend.data_access import canonical_url as canonical_source_url
from backend.data_access import validate_record
from backend.models import ExtractedRecord
from backend.review import generate_review

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_ROOT / "data" / "raw" / "darglobal"
WASALT_RAW_DIR = PROJECT_ROOT / "data" / "raw" / "wasalt"
OUTPUT_DIR = PROJECT_ROOT / "data" / "import_review"


def canonical_url(raw_url: str) -> str:
    return canonical_source_url(raw_url)


def row_to_extracted_record(row: dict, page_type: str, source: str = "darglobal") -> dict:
    adapter = DarGlobalAdapter() if source == "darglobal" else WasaltAdapter()
    record, _ = adapter.normalize({**row, "Page Type": page_type})
    return record.model_dump(mode="json")


def classify_record(row: dict, filename: str) -> tuple:
    return classify_page("darglobal", row.get("URL", ""), row.get("Title", ""), row.get("Text", ""), filename)


def extracted_record_to_index_input(record: ExtractedRecord) -> dict:
    """The new indexer consumes the validated nested record, including full content."""
    return validate_record(record).model_dump(mode="json")


def main(argv: list[str] | None = None) -> dict:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--darglobal-root", type=Path, default=RAW_DIR)
    parser.add_argument("--wasalt-root", type=Path, default=WASALT_RAW_DIR)
    parser.add_argument("--output", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args(argv)
    summary = generate_review(args.darglobal_root, args.wasalt_root, args.output,
        approved_darglobal_review=OUTPUT_DIR / "extracted_records.json")
    print(summary)
    return summary


if __name__ == "__main__":
    main()
