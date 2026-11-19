# RealtyAI — Phase 6.9: CSV-to-Document Importer Design

## Design-Only Notice

This document constitutes the complete final design for the CSV import pipeline. No Python importer will be created, no ingestion will run, and no existing records will be modified. The design defines the data flow, schema mapping, classification rules, and output format for future approval.

---

## 1. Schema Compatibility

The existing `ExtractedRecord` model in `backend/models.py:113-121` defines:

```python
class ExtractedRecord(BaseModel):
    source: str                    # e.g. "darglobal.co.uk" or "wasalt.sa"
    url: str                       # original, fully-quoted source URL
    data: dict[str, Any]           # key-value pairs of record fields
    extracted_at: datetime         # ISO extraction timestamp
```

The importer shall convert each normalized document into an `ExtractedRecord` using this exact mapping:

| Normalized field | `ExtractedRecord` field | Notes |
|------------------|------------------------|-------|
| `source` | `record["source"]` | Derived from URL domain (e.g., `"darglobal.co.uk"`). |
| `source_url` | `record["url"]` | **Original CSV URL preserved as-is** — including `utm_source=chatgpt.com` tracking params. This is the `url` field. |
| `title` | part of `record["data"]` | Included in the `data` dict under a `"title"` key. |
| `page_type` | part of `record["data"]` | Included in the `data` dict under a `"page_type"` key. |
| `description` | part of `record["data"]` | Included in the `data` dict under a `"description"` key. |
| `content` | part of `record["data"]` | Included in the `data` dict under a `"content"` key (CSV `Text` column). |
| `extracted_at` | `record["extracted_at"]` | ISO-8601 UTC timestamp (same format as existing). |

No other fields are mapped. If a record does not satisfy a property schema, the `data` dict contains whatever fields are present — missing fields are absent, not set to `null` or fabricated. Claiming compatibility without this mapping is invalid.

---

## 2. Legal Content Exclusion

Legal-reference records (terms-of-use, privacy policy, terms-and-conditions, cookie policy) must be excluded from the searchable knowledge base.

Exclusion happens before calling `rag.py:index_records()`. The design must not rely on an exclusion flag inside the RAG pipeline unless the existing implementation explicitly supports such a flag for filtering retrievability.

Procedure:
1. Classify each record's `page_type`.
2. If `page_type` is `legal_reference` → do not include in the list passed to `index_records()`.
3. If `page_type` is anything else → may be included (subject to other restrictions).
4. Legal records may be written to a separate output file for auditing, but must not be indexed into ChromaDB.

---

## 3. Wasalt Quarantine

Wasalt data must be quarantined. The importer must not read, process, copy, store, normalize, or index Wasalt listing content until authorization for collection, storage, and use is confirmed by the appropriate stakeholder.

The importer may report Wasalt filenames and their exclusion status without reading their contents.

Procedure:
1. Any CSV file identified as Wasalt-sourced (domain `wasalt.sa`, or `page_type` deriving from Wasalt CSV structure) → do not process for indexing.
2. Such records may be reported by filename and exclusion status in the import report, but their `content` field must remain unread and their data must not enter the vector store.
3. The importer must produce a report of quarantined Wasalt records and halt any processing toward the vector store until explicit authorization is confirmed.
4. If later authorized, a separate authorized batch process may be run.

---

## 4. Individual Property Classification

The design must not classify every record with substantial text as `individual_property`. Property classification requires affirmative property-specific evidence.

**Property-specific evidence criteria** (at least one required):
- A recognizable property title (not a company name, category name, or generic label), or
- A property URL pattern consistent with individual property pages (e.g., DarGlobal one-of-one or project detail paths), or
- Property-specific content (bedrooms, price mentions, property-type mentions, size in sqm, amenities list in structured form).

**Classification hierarchy** (priority order, first match wins):

| page_type | Conditions |
|-----------|------------|
| `legal_reference` | URL contains `terms-of-use`, `privacy-policy`, `terms-and-conditions`, or `cookie-policy`. **Excluded from KB.** |
| `auction` | URL contains `auction` or Title/Description explicitly mentions auction/sale of assets. |
| `project_directory` | URL path contains `/projects/` or CSV is `DarGlobal-project-directory.csv`. Title mentions "Project", "Directory", or similar. |
| `company` | URL path contains `/company/` or CSV is a DarGlobal company file. Title/about text is organization-focused, not property-specific. |
| `category` | URL contains `properties-for-sale`, `properties-for-rent`, or similar category breadth. Wasalt sale/rent category pages. |
| `individual_property` | **Only if** the record has substantial non-empty `content` **AND** has at least one reliable property-specific indicator (recognizable property title, property URL pattern, or property-specific content). |
| `unknown` | Record has substantial text but does NOT meet criteria for any above class. **Flagged for manual review.** |
| `empty` | Text/Content is empty/whitespace-only. **Skip.** |

**Critical constraint**: Company, category, auction, and project-directory pages must never become `individual_property` records.

---

## 4. Deterministic Deduplication

Deduplication processes files in a deterministic sorted order to ensure consistent results across runs.

Procedure:
1. Walk `data/raw/darglobal/` and `data/raw/wasalt/` recursively.
2. Collect all CSV file paths.
3. Sort paths alphabetically (lexicographic) before processing.
4. Process each file in this sorted order.

Dedup logic:
- For each record, compute `canonical_url()` (strip `utm_*`, lowercase path, sort remaining query params).
- Maintain a `seen_canonical: set[str]` across the entire run (not per-file).
- First occurrence of a canonical URL is retained; subsequent occurrences are skipped.
- The importer must produce a dedup report listing:
  - Total CSV files processed
  - Total records read
  - Duplicates skipped (canonical URL + original file path that was skipped)
  - First-occurrence file paths retained

Original URL preservation:
- The original CSV URL (with all query params including `utm_source=chatgpt.com`) must always be preserved in the output document's `source_url` field.
- The `canonical_url` is computed for dedup but the raw original URL is what goes into `ExtractedRecord["url"]`.

---

## 5. Review Report

The importer produces a human-readable import report that is reviewable, not automatically ingesting records. The report includes these metrics (no assumption that every CSV contains exactly one data row):

- **Total CSV files** — Count of all `.csv` files found in `data/raw/darglobal/` and `data/raw/wasalt/`.
- **Records read** — Number of CSV records successfully parsed.
- **Empty records skipped** — Count of records where `Text`/content was empty or whitespace-only.
- **Duplicates skipped** — Count of records skipped due to canonical URL already seen. Includes a listing of which canonical URLs were duplicated and which file paths were retained vs. skipped.
- **Classifications** — Tally of records per `page_type`: `individual_property`, `project_directory`, `company`, `category`, `auction`, `legal_reference`, `unknown`, `empty`.
- **Quarantined records** — Count of Wasalt records excluded from processing and indexing (not read, processed, or indexed; reported by filename only).
- **Excluded records** — Count of `legal_reference` records excluded from the KB.
- **Eligible for manual review** — Count of `unknown` records flagged for manual review, with a sample listing (title + canonical URL + reason for uncertainty).
- **Eligible for indexing after approval** — Count of records that passed all filters and classification and would be passed to `index_records()` if the operator so decides.
- **Schema compliance** — Count of records that successfully convert to `ExtractedRecord` format vs. those that fail (e.g., missing required fields).

Report format: Human-readable Markdown or plain text. The report must not automatically ingest records into ChromaDB. It is purely a review document. The operator decides which (if any) records to pass to `index_records()` after reviewing the report.

---

## 6. Restrictions Honor Statement

| Restriction | How It Is Honored |
|-------------|-------------------|
| Documentation only. | All content is descriptive; no Python importer created. |
| Modify only docs/csv-import-design.md. | Only this file is changed. |
| Do not create Python files. | No Python code is written or executed. |
| Do not read or process Wasalt CSV contents. | Wasalt records are identified by filename/domain only; contents are not read. |
| Do not run ingestion or modify ChromaDB. | No ingestion code is run; ChromaDB is untouched. |
| Do not modify raw CSVs, processed records, frontend, or Groq configuration. | Raw CSV files unchanged; no other files modified. |
| Do not run Git commands or create commits. | Standard operating procedure. |

---

## 7. Summary

This design defines the complete pipeline for safe, deduplicated CSV import into the RealtyAI RAG knowledge base. Key principles:

- **Schema compatibility** is defined by exact field mapping to `ExtractedRecord`; compatibility is not assumed without implementation.
- **Wasalt data is quarantined** — no contents are read, processed, or indexed until explicit authorization for collection, storage, and use is confirmed.
- **Legal-reference content is excluded** before `index_records()` is called.
- **Property classification requires evidence** — `individual_property` needs substantial content plus at least one reliable property-specific indicator; insufficient evidence → `unknown` → manual review.
- **Deterministic deduplication** uses sorted file paths and retains first-occurrence canonical URLs.
- **Four outcome categories** for every record: eligible for manual review, eligible for indexing after approval, excluded, or quarantined.
- **No implementation or ingestion has been performed**. This document is the deliverable, submitted for stakeholder approval.

---
*Design prepared for RealtyAI Phase 6.9. Design-Only — no code will be run until explicit approval is given. Based on analysis of `backend/models.py`, `backend/rag.py`, `backend/processor.py`, `backend/chatbot.py`, and `docs/raw-data-validation-report.md`. All raw CSV files in `data/raw/` remain unchanged.*