"""One CSV import engine with source-specific field and classification adapters."""

from __future__ import annotations

import csv
import json
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

from pydantic import ValidationError

from backend.data_access import (
    DEFAULT_POLICY,
    PAGE_TYPES,
    SourcePolicy,
    canonical_url,
    normalize_source,
    validate_record,
)
from backend.models import ExtractedRecord

FIELD_ALIASES = {
    "url": ("url", "sourceurl", "originalurl", "propertyurl", "listingurl", "link", "رابط", "الرابط", "رابطالعقار"),
    "title": ("title", "propertytitle", "listingtitle", "propertyname", "name", "heading", "h1", "العنوان", "اسمالعقار"),
    "description": ("description", "summary", "metadescription", "وصف", "الوصف"),
    "content": ("text", "content", "fulltext", "pagetext", "body", "details", "تفاصيل", "التفاصيل"),
    "page_type": ("pagetype", "pagecategory", "documenttype"),
    "extracted_at": ("extractedat", "extractiontimestamp", "scrapedat", "capturedat", "extractiondate"),
}
SPEC_FIELDS = frozenset({
    "bedrooms", "beds", "bathrooms", "price", "currency", "city", "country", "location", "neighborhood",
    "neighbourhood", "propertytype", "size", "sizesqm", "areasqm", "area", "landareasqm", "buildingareasqm",
    "amenities", "facilities", "handover", "handoverdate", "completiondate", "reference", "referencenumber",
    "propertyid", "listingid", "status", "غرفالنوم", "السعر", "العملة", "المساحة", "المدينة", "الحي",
})
COMPANY_FILENAMES = frozenset({
    "DarGlobal-Aboutus.csv", "DarGlobal-contect.csv", "DarGlobal-homepage.csv", "DarGlobal-trumpOrganization.csv",
    "Wasalt-homepage.csv", "corporate-information.csv",
})


class EmptyRecord(ValueError):
    """A row has no useful extracted text or supplied specifications."""


def header_key(value: str) -> str:
    return "".join(character for character in value.casefold().strip() if character.isalnum())


def classify_page(source: str, url: str, title: str, content: str, filename: str = "", declared: str = "") -> tuple[str, str]:
    path = urlparse(url).path.casefold().rstrip("/")
    lower_url = url.casefold()
    if any(term in lower_url for term in ("terms-of-use", "privacy-policy", "terms-and-conditions", "cookie-policy")):
        return "legal_reference", "Legal/reference URL; excluded from retrieval"
    if declared and declared not in PAGE_TYPES:
        raise ValueError(f"Unknown declared page type: {declared}")
    if "auction" in (urlparse(url).hostname or "") or "/auction" in path:
        return "auction", "Auction catalog; not an individual property"
    if "/projects" in path or "project-directory" in filename.casefold():
        return "project_directory", "Project directory URL or filename"
    if filename in COMPANY_FILENAMES or path in {"", "/en", "/ar", "/en/corporate", "/ar/corporate"} or any(
        indicator in path for indicator in ("/about", "/contact", "get-in-touch", "trump-organization", "/company")
    ):
        return "company", "Company/homepage URL or filename"
    if any(term in path for term in ("properties-for-", "villas-for-", "apartments-for-", "lands-for-", "/sale/search", "/rent/search")):
        return "project_directory", "Listing/category directory; not an individual property"
    if declared:
        return declared, "Explicit page type, after directory/company/reference precedence"
    if any(term in title.casefold() for term in ("directory", "project listings", "projects for sale")):
        return "project_directory", "Directory title"
    detail_path = (
        any(term in path for term in ("/one-of-one/", "/the-astera", "/rayana/", "/trump-plaza/"))
        if source == "darglobal" else bool(re.search(r"/(?:en/|ar/)?property/(?:sale|rent)/", path))
    )
    evidence = bool(re.search(r"bedroom|bathroom|sqm|sqft|amenities|residence|villa|غرف|مساحة", content, re.IGNORECASE))
    if content.strip() and (detail_path or evidence):
        return "individual_property", "Individual URL or property-specific extracted evidence"
    return "unknown", "Useful text without sufficient classification evidence; manual review required"


class SourceAdapter:
    def __init__(self, source: str):
        self.source = normalize_source(source)

    def normalize(
        self, row: dict, *, filename: str = "", imported_at: datetime | None = None,
        origin: str = "raw", policy: SourcePolicy = DEFAULT_POLICY,
    ) -> tuple[ExtractedRecord, dict]:
        policy.require_origin(self.source, origin)
        values = {header_key(key): value for key, value in row.items() if isinstance(key, str)}
        if values.get("source") and normalize_source(values["source"]) != self.source:
            raise ValueError("CSV source does not match the selected source adapter.")
        if values.get("data"):
            nested = json.loads(values["data"])
            if not isinstance(nested, dict):
                raise ValueError("A JSON data column must contain an object.")
            for key, value in nested.items():
                values.setdefault(header_key(key), value)

        def get(name: str):
            return next((values[key] for key in FIELD_ALIASES[name] if values.get(key) not in (None, "")), "")

        url, title, description, content = (get(name) for name in ("url", "title", "description", "content"))
        if not all(isinstance(value, str) for value in (url, title, description, content)):
            raise TypeError("URL, title, description, and content columns must contain text.")
        supplied_specs = {key: value for key, value in row.items() if isinstance(key, str) and header_key(key) in SPEC_FIELDS and value not in (None, "")}
        spec_text = "\n".join(f"{key}: {value}" for key, value in supplied_specs.items())
        if not content.strip() and not description.strip() and not spec_text:
            raise EmptyRecord("No useful content, description, or specifications")
        if not title.strip():
            raise ValueError("Missing title")
        if not url or url != url.strip():
            raise ValueError("Missing or whitespace-padded original URL")
        original_title = title
        if self.source == "darglobal" and urlparse(url).path.casefold().rstrip("/") == "/one-of-one/the-albert-hall-mansion":
            heading = next((line.strip() for line in content.splitlines() if line.strip()), "")
            if heading.casefold() == "the albert hall mansion":
                title = heading
        if spec_text:
            content = f"{content}\n\nSpecifications\n{spec_text}".strip()
        declared_value = get("page_type")
        if not isinstance(declared_value, str):
            raise TypeError("Page type must be text.")
        declared = declared_value.strip().casefold().replace("-", "_").replace(" ", "_")
        page_type, reason = classify_page(self.source, url, title, content or description, filename, declared)
        timestamp = get("extracted_at") or imported_at or datetime.now(UTC)
        record = validate_record(ExtractedRecord(
            source=self.source, url=url, extracted_at=timestamp,
            data={"title": title, "page_type": page_type, "description": description, "content": content, "data_origin": origin,
                "timestamp_origin": "csv" if get("extracted_at") else "import_time"},
        ), policy)
        metadata = {
            "source": self.source, "url": url, "canonical_url": canonical_url(url),
            "classification_reason": reason,
            "timestamp_origin": "csv" if get("extracted_at") else "import_time",
        }
        if original_title != title:
            metadata["original_csv_title"] = original_title
            metadata["title_normalization_note"] = "Verbatim extracted page heading"
        return record, metadata


class DarGlobalAdapter(SourceAdapter):
    def __init__(self):
        super().__init__("darglobal")


class WasaltAdapter(SourceAdapter):
    def __init__(self):
        super().__init__("wasalt")


@dataclass
class ImportResult:
    source: str
    records: list[ExtractedRecord] = field(default_factory=list)
    review_metadata: list[dict] = field(default_factory=list)
    files: list[dict] = field(default_factory=list)
    issues: list[dict] = field(default_factory=list)
    rows_read: int = 0
    empty_skipped: int = 0
    duplicate_skipped: int = 0
    invalid_skipped: int = 0

    def summary(self) -> dict:
        return {
            "source": self.source, "csv_files": len(self.files), "rows_read": self.rows_read,
            "records_retained": len(self.records), "empty_skipped": self.empty_skipped,
            "duplicates_skipped": self.duplicate_skipped, "invalid_skipped": self.invalid_skipped,
            "classification_counts": dict(Counter(record.data["page_type"] for record in self.records)),
        }


def import_directory(
    root: Path, source: str, *, policy: SourcePolicy = DEFAULT_POLICY, origin: str = "raw",
    imported_at: datetime | None = None,
) -> ImportResult:
    source = normalize_source(source)
    policy.require_path(source, root, origin)
    if not root.is_dir():
        raise FileNotFoundError(f"CSV input directory is unavailable: {root}")
    result = ImportResult(source)
    imported_at = imported_at or datetime.now(UTC)
    adapter = DarGlobalAdapter() if source == "darglobal" else WasaltAdapter()
    paths = sorted((path for path in root.rglob("*") if path.is_file() and path.suffix.casefold() == ".csv"), key=lambda path: path.as_posix())
    seen = {}
    for path in paths:
        policy.require_path(source, path, origin)
        file_info = {"file": str(path), "rows_read": 0, "status": "processed"}
        result.files.append(file_info)
        try:
            with path.open(encoding="utf-8-sig", newline="") as handle:
                sample = handle.read(4096)
                handle.seek(0)
                try:
                    dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
                except csv.Error:
                    try:
                        dialect = csv.Sniffer().sniff(sample.splitlines()[0], delimiters=",;\t")
                    except (csv.Error, IndexError):
                        dialect = csv.excel
                reader = csv.DictReader(handle, dialect=dialect, strict=True)
                headers = reader.fieldnames or []
                keys = [header_key(name) for name in headers]
                if not keys or len(set(keys)) != len(keys):
                    raise ValueError("Missing or duplicate CSV headers")
                for row in reader:
                    result.rows_read += 1
                    file_info["rows_read"] += 1
                    try:
                        if None in row or any(value is None for value in row.values()):
                            raise ValueError("Malformed CSV row: column count does not match header")
                        record, metadata = adapter.normalize(row, filename=path.name, imported_at=imported_at, origin=origin, policy=policy)
                        identity = canonical_url(record.url)
                        if identity in seen:
                            result.duplicate_skipped += 1
                            result.issues.append({"file": str(path), "line": reader.line_num, "kind": "duplicate", "canonical_url": identity, "retained_file": seen[identity]})
                            continue
                        seen[identity] = str(path)
                        metadata.update({"file": str(path), "line": reader.line_num})
                        result.records.append(record)
                        result.review_metadata.append(metadata)
                    except EmptyRecord as error:
                        result.empty_skipped += 1
                        result.issues.append({"file": str(path), "line": reader.line_num, "kind": "empty", "reason": str(error)})
                    except (ValueError, TypeError, ValidationError) as error:
                        result.invalid_skipped += 1
                        result.issues.append({"file": str(path), "line": reader.line_num, "kind": "invalid", "reason": str(error)})
        except (OSError, UnicodeError, csv.Error, ValueError) as error:
            file_info["status"] = "error"
            result.issues.append({"file": str(path), "kind": "file_error", "reason": str(error)})
    return result
