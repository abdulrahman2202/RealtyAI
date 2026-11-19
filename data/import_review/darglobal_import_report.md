# Darglobal CSV Import Review — Phase 6.11

Data-use permission: User confirmed permission from DarGlobal and Wasalt in Phase 6.11 (2026-11-19).

Actual CSV files were read recursively in deterministic full-path order. This is review output; the persistent ChromaDB collection was not opened or changed.

| Measure | Count |
| --- | ---: |
| csv_files | 10 |
| rows_read | 10 |
| records_retained | 7 |
| empty_skipped | 2 |
| duplicates_skipped | 1 |
| invalid_skipped | 0 |
| prepared_chunks | 46 |

## Classifications

- company: 4
- individual_property: 2
- project_directory: 1

## Retained records

| Title | Page type | Original URL | Timestamp origin |
| --- | --- | --- | --- |
| About Us | company | <https://darglobal.co.uk/about> | preserved_approved_review |
| Contact \| Luxury Real Estate, DarGlobal | company | <https://darglobal.co.uk/get-in-touch> | preserved_approved_review |
| DarGlobal \| International Luxury Real Estate Developer | company | <https://darglobal.co.uk/?utm_source=chatgpt.com> | preserved_approved_review |
| Trump Branded Residences Gulf \| DarGlobal Portfolio | company | <https://darglobal.co.uk/partners/the-trump-organization> | preserved_approved_review |
| Buy Modern Apartments & Exclusive Villas \| International Homes for Sale | project_directory | <https://darglobal.co.uk/projects/properties-in-uk?utm_source=chatgpt.com> | preserved_approved_review |
| The Astera, Interiors by Aston Martin \| Al Marjan Island RAK | individual_property | <https://darglobal.co.uk/the-astera?utm_source=chatgpt.com> | preserved_approved_review |
| THE ALBERT HALL MANSION | individual_property | <https://darglobal.co.uk/one-of-one/THE-ALBERT-HALL-MANSION?utm_source=chatgpt.com> | preserved_approved_review |

Original CSV title retained in review metadata: `Buy Branded Homes | Million Dollar Houses for Sale | Darglobal`.


## Files processed

- C:\Programming\RealtyAI\data\raw\darglobal\company\DarGlobal-Aboutus.csv: 1 rows; processed
- C:\Programming\RealtyAI\data\raw\darglobal\company\DarGlobal-contect.csv: 1 rows; processed
- C:\Programming\RealtyAI\data\raw\darglobal\company\DarGlobal-homepage.csv: 1 rows; processed
- C:\Programming\RealtyAI\data\raw\darglobal\company\DarGlobal-trumpOrganization.csv: 1 rows; processed
- C:\Programming\RealtyAI\data\raw\darglobal\projects\DarGlobal-project-directory.csv: 1 rows; processed
- C:\Programming\RealtyAI\data\raw\darglobal\properties\The Astera – Aston Martin.csv: 1 rows; processed
- C:\Programming\RealtyAI\data\raw\darglobal\properties\Trump Mansions.csv: 1 rows; processed
- C:\Programming\RealtyAI\data\raw\darglobal\properties\Trump-Park-Residences.csv: 1 rows; processed
- C:\Programming\RealtyAI\data\raw\darglobal\properties\page-text-2026-11-19-11-54.csv: 1 rows; processed
- C:\Programming\RealtyAI\data\raw\darglobal\properties\page-text-2026-11-19-11-55.csv: 1 rows; processed

## Validation and deduplication

- {"file": "C:\\Programming\\RealtyAI\\data\\raw\\darglobal\\properties\\Trump Mansions.csv", "line": 2, "kind": "empty", "reason": "No useful content, description, or specifications"}
- {"file": "C:\\Programming\\RealtyAI\\data\\raw\\darglobal\\properties\\Trump-Park-Residences.csv", "line": 2, "kind": "empty", "reason": "No useful content, description, or specifications"}
- {"file": "C:\\Programming\\RealtyAI\\data\\raw\\darglobal\\properties\\page-text-2026-11-19-11-54.csv", "line": 126, "kind": "duplicate", "canonical_url": "https://darglobal.co.uk/the-astera", "retained_file": "C:\\Programming\\RealtyAI\\data\\raw\\darglobal\\properties\\The Astera – Aston Martin.csv"}

## Preparation and ingestion status

Nested ExtractedRecord documents retain source, original URL, title, page type, full extracted text, and timestamp. Canonical URLs and CSV title provenance remain separate review metadata.

Each useful section is prepared with the cached tokenizer, a 200-token body target and 32-token overlap. Complete embedding inputs, including prefixes and special tokens, are at most 256 tokens. Short sections remain whole. Known navigation/registration sections are omitted from prepared text while original normalized content remains available in chunk_review.json.

CSV timestamps are preserved when supplied. Where the export has no extraction timestamp, the model's UTC import-time fallback is explicitly labeled. Unchanged DarGlobal records retain their approved Phase 6.10 extraction timestamps.

Legal-reference and unknown records are normalized and reported, but excluded from searchable chunks. Auction catalogs retain the auction page type. Directories are not converted into individual properties.

Manifest state: review_only. Existing collection IDs, embedding provenance, and conflicts are unverified until the approved ingestion preflight. No new records were added.
