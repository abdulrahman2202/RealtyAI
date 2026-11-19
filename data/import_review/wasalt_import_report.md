# Wasalt CSV Import Review — Phase 6.11

Data-use permission: User confirmed permission from DarGlobal and Wasalt in Phase 6.11 (2026-11-19).

Actual CSV files were read recursively in deterministic full-path order. This is review output; the persistent ChromaDB collection was not opened or changed.

| Measure | Count |
| --- | ---: |
| csv_files | 6 |
| rows_read | 6 |
| records_retained | 6 |
| empty_skipped | 0 |
| duplicates_skipped | 0 |
| invalid_skipped | 0 |
| prepared_chunks | 38 |

## Classifications

- auction: 1
- company: 2
- legal_reference: 1
- project_directory: 2

## Retained records

| Title | Page type | Original URL | Timestamp origin |
| --- | --- | --- | --- |
| Real Estate, Vehicle & Movable Asset Auctions \| Wasalt | auction | <https://auction.wasalt.sa/en?utm_source=chatgpt.com> | import_time |
| Properties For Sale and Rent in Saudi Arabia \| Wasalt | company | <https://wasalt.sa/en> | import_time |
| Wasalt Real Estate Services | company | <https://wasalt.sa/en/corporate?utm_source=chatgpt.com> | import_time |
| Properties for Sale in Saudi Arabia \| Wasalt | project_directory | <https://wasalt.sa/en/properties-for-sale-in-saudi-arabia?utm_source=chatgpt.com> | import_time |
| Properties for Rent in Saudi \| Wasalt | project_directory | <https://wasalt.sa/en/properties-for-rent-in-saudi-arabia?utm_source=chatgpt.com> | import_time |
| Wasalt Real Estate Services | legal_reference | <https://auction.wasalt.sa/en/terms-of-use?utm_source=chatgpt.com> | import_time |

## Files processed

- C:\Programming\RealtyAI\data\raw\wasalt\auctions\auction.csv: 1 rows; processed
- C:\Programming\RealtyAI\data\raw\wasalt\company\Wasalt-homepage.csv: 1 rows; processed
- C:\Programming\RealtyAI\data\raw\wasalt\company\corporate-information.csv: 1 rows; processed
- C:\Programming\RealtyAI\data\raw\wasalt\listings\WasaltProperties for sale.csv: 1 rows; processed
- C:\Programming\RealtyAI\data\raw\wasalt\listings\properties-for-rent.csv: 1 rows; processed
- C:\Programming\RealtyAI\data\raw\wasalt\reference\terms-of-use.csv: 1 rows; processed

## Validation and deduplication

No malformed, duplicate, or empty rows were found.

## Preparation and ingestion status

Nested ExtractedRecord documents retain source, original URL, title, page type, full extracted text, and timestamp. Canonical URLs and CSV title provenance remain separate review metadata.

Each useful section is prepared with the cached tokenizer, a 200-token body target and 32-token overlap. Complete embedding inputs, including prefixes and special tokens, are at most 256 tokens. Short sections remain whole. Known navigation/registration sections are omitted from prepared text while original normalized content remains available in chunk_review.json.

CSV timestamps are preserved when supplied. Where the export has no extraction timestamp, the model's UTC import-time fallback is explicitly labeled. Unchanged DarGlobal records retain their approved Phase 6.10 extraction timestamps.

Legal-reference and unknown records are normalized and reported, but excluded from searchable chunks. Auction catalogs retain the auction page type. Directories are not converted into individual properties.

Manifest state: review_only. Existing collection IDs, embedding provenance, and conflicts are unverified until the approved ingestion preflight. No new records were added.
