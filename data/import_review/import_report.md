# DarGlobal CSV Import Review Report

**Generated:** 2026-11-19 18:55:33
**Stage:** Phase 6.10.2 — final output schema audit; ingestion approval pending.
**Total CSV files:** 10
**Total records read:** 10
**Empty records skipped:** 2
**Duplicates skipped:** 1
**Retained review records:** 7

The schema audit rebuilt the saved review JSON without rereading CSVs. Original import counts, record order, source URLs, descriptions, content, and extraction timestamps were preserved.

## Schema Compatibility

Every item in `extracted_records.json.records` is validated and serialized with the existing `backend.models.ExtractedRecord` model. Its only top-level fields are `source`, `url`, `data`, and `extracted_at`.

| Input | ExtractedRecord field |
| --- | --- |
| Source website | `source` |
| Original source URL, including original casing and query parameters | `url` |
| Display title, classification, description, extracted text | `data.title`, `data.page_type`, `data.description`, `data.content` |
| Original extraction timestamp | `extracted_at` |

`canonical_url` and the existing review `key` are stored in the separate `review_metadata` array, matched to records by `source` and the original `url`. They are never passed into ExtractedRecord. Any original CSV title replaced by an extracted heading is also preserved in review metadata.

## Compatibility with index_records

Static inspection of `backend/rag.py:index_records` confirms that it accepts a list of flat dictionaries and reads top-level `title`, `description`, `source`, and `url`. It skips records with a blank title or URL. Passing the nested ExtractedRecord JSON directly would skip these records because there is no top-level title.

After approval, `scripts.csv_import.extracted_record_to_index_input` can prepare those four flat fields from a validated ExtractedRecord in memory. It preserves the original source URL and reads the title and description from `data`. The current indexer uses title and description for embeddings; it does not consume `data.content`, `page_type`, or `extracted_at`. The helper does not import RAG, call indexing, or initialize ChromaDB.

## Classification Tally (Retained Records)

- **company:** 4
- **empty:** 0
- **individual_property:** 2
- **legal_reference:** 0
- **project_directory:** 1
- **unknown:** 0

## Records Eligible for Manual Review

None.

## Records Eligible for Indexing After Approval

| Display title | Page type | Original source URL |
| --- | --- | --- |
| About Us | company | <https://darglobal.co.uk/about> |
| Contact \| Luxury Real Estate, DarGlobal | company | <https://darglobal.co.uk/get-in-touch> |
| DarGlobal \| International Luxury Real Estate Developer | company | <https://darglobal.co.uk/?utm_source=chatgpt.com> |
| Trump Branded Residences Gulf \| DarGlobal Portfolio | company | <https://darglobal.co.uk/partners/the-trump-organization> |
| Buy Modern Apartments & Exclusive Villas \| International Homes for Sale | project_directory | <https://darglobal.co.uk/projects/properties-in-uk?utm_source=chatgpt.com> |
| The Astera, Interiors by Aston Martin \| Al Marjan Island RAK | individual_property | <https://darglobal.co.uk/the-astera?utm_source=chatgpt.com> |
| THE ALBERT HALL MANSION | individual_property | <https://darglobal.co.uk/one-of-one/THE-ALBERT-HALL-MANSION?utm_source=chatgpt.com> |

## Display Title Normalization

- **Display title:** `THE ALBERT HALL MANSION`
- **Original CSV title:** `Buy Branded Homes | Million Dollar Houses for Sale | Darglobal`
- **Evidence:** the first non-empty line of the record's existing `data.content`; the extracted heading is preserved verbatim.

## Deduplication and Review Boundary

Classification priority and canonical URL deduplication are unchanged. Canonicalization removes `utm_*` query parameters and lowercases the URL path; the first occurrence in sorted CSV file order is retained. Empty records remain excluded. The recorded duplicate and empty counts above are separate from the retained-record classification tally.

All output remains in the review stage. `index_records` was not called; ChromaDB, existing processed data, raw CSVs, frontend files, and Groq configuration were not modified. Wasalt CSV contents were not read or processed.

Schema validation occurs during output generation. Ingestion awaits explicit approval.

Tests for model validation, the saved seven records, deduplication, heading provenance, and the statically inspected indexing contract were added but not run, per the final instruction.
