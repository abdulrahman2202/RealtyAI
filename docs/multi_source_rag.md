# Phase 6.11 — Shared DarGlobal + Wasalt RAG Pipeline

Both sources are authorized for this project by the user's explicit permission confirmation on 2026-11-19. The previous Wasalt quarantine is withdrawn. Actual CSVs from both source directories are processed. This permission is separate from permission to add records to the existing ChromaDB collection; production ingestion is still pending.

The existing seven-record DarGlobal review and processed records are retained. This implementation creates new source reports, a combined report, a chunk preview, and a proposed ingestion manifest. It does not open, clear, rebuild, migrate, or write the persistent collection while generating those outputs.

## Modules

| File | Responsibility |
| --- | --- |
| `backend/data_access.py` | Shared source identities, original-URL validation, canonical IDs, and validation of the nested ExtractedRecord schema |
| `backend/csv_importer.py` | Recursive CSV discovery, field aliases, source adapters, classification precedence, diagnostics, first-occurrence deduplication, and timestamp provenance |
| `backend/embedding.py` | Locally cached tokenizer and encoder; 256-token maximum and model/revision/dimension provenance |
| `backend/document_preparation.py` | Useful source sections, actual-token windows, 200-token body target, 32-token overlap, full text preservation, reproducible IDs and fingerprints |
| `backend/indexing.py` | Pure review plans, explicit target-bound approval, metadata/provenance preflight, conflict detection, append-only batches, lock/receipt handling, and safe retries |
| `backend/retrieval.py` | Cached lexical catalog, BM25/entity matching, semantic search, source/page-type/property scopes, relevance filtering, raw Chroma distances, and source-balanced results |
| `backend/context.py` | Complete-chunk token/byte budgets, property separation, original-URL citations, and quoted attribute evidence/unavailable responses |
| `backend/rag.py`, `backend/chatbot.py` | Backward-compatible service entry points with no implicit request-time ingestion |

## Review the actual datasets

From the project root, using the existing virtual environment:

```powershell
.venv/Scripts/python.exe -B scripts/csv_import.py
```

The command reads `data/raw/darglobal/` and `data/raw/wasalt/` recursively, processes all CSV files, and generates:

- `data/import_review/darglobal_import_report.md`
- `data/import_review/wasalt_import_report.md`
- `data/import_review/combined_import_report.md`
- `data/import_review/chunk_review.json`
- `data/import_review/proposed_ingestion_manifest.json`

The approved DarGlobal `extracted_records.json` remains unchanged. New normalized records are in `chunk_review.json.documents`, using exactly `source`, `url`, `data`, and `extracted_at` at the top level. Source identity is `darglobal` or `wasalt`; the original URL and approved title remain intact. Canonical URLs and original CSV titles are review metadata. Provided CSV timestamps are preserved; absent timestamps receive an explicitly labeled UTC import timestamp. Unchanged approved DarGlobal records keep their previous extraction timestamps.

The actual Wasalt input includes company pages, sale/rent directories, an auction catalog, and legal-reference text. The pipeline does not invent individual-property records from these pages. Legal references and unknown documents are processed for review and excluded from searchable chunks. Synthetic fixtures are used only for unit edge cases; actual authorized CSVs supply the dataset review and integration coverage.

## Retrieval and answers

The existing chat endpoint keeps its question-only contract and accepts optional `sources`, `page_types`, `document_id`, and `property_name` filters. Supported searchable page types are `company`, `project_directory`, `individual_property`, and `auction`.

```json
{"question":"Compare DarGlobal and Wasalt services","sources":["darglobal","wasalt"],"page_types":["company"]}
```

Exact individual-property aliases are matched before ranking; longer names take precedence over names nested inside them. Semantic candidates and lexical/entity matches are fused without transforming raw Chroma distances. Conservative raw-distance cutoffs are metric-specific; an unknown metric requires lexical evidence. Context selects complete chunks within a 1,500-token cached-tokenizer budget and 6,000 UTF-8 bytes, including metadata and delimiters. Every document retains its identity, source kind, original URL, and evidence sections.

Attribute questions return source excerpts with per-property missing-information statements. Visa eligibility, tax figures, and market statistics are not promoted into an individual property's price. General narrative answers use the existing Groq integration with source-grounding instructions and a guard against unsupported numbers; credentials, model/environment configuration, and frontend files are unchanged. Narrative faithfulness is still a model behavior rather than a formal guarantee. The context tokenizer is the cached SentenceTransformer tokenizer, not the Groq model's tokenizer; the additional byte cap provides a conservative second bound.

## Indexing protection and final approval

```powershell
.venv/Scripts/python.exe -B scripts/index_review.py
```

Without `--execute`, this command only prepares a review manifest and does not connect to ChromaDB. The manifest explicitly marks existing IDs and the persistent collection as unverified. Chunk identity uses source/canonical document identity, content fingerprint, preparation version, embedding provenance, and chunk index. Extraction-time changes and tracking-only URL changes do not create new chunk identities.

Execution requires `--execute`, the explicitly approved collection UUID, an approval reference, and verified legacy embedding provenance where legacy metadata lacks it. The command also checks that current preparation matches the reviewed chunk IDs. It opens only the existing `realtyai_properties` collection, never creates or reconfigures it, rejects mismatched target approval, stops on content/version/provenance conflicts, skips identical chunks, and appends only absent IDs. A lock serializes indexing processes for the same collection. Accepted batches are read back and recorded in a receipt; a failed run can be retried through the same preflight without duplicating confirmed chunks.

Matching dimensions do not prove historical model compatibility. Old rows remain untouched and can be augmented only with explicit provenance evidence. A changed source revision or preparation version requires review rather than automatic overwrite or deletion. Collection clearing and implicit processed-data ingestion entry points are disabled. Normal chat requests retrieve existing data only and return unavailable information when the collection is absent or empty.

## Verification

The full backend suite ran once: **85 passed, 1 failed, 10 deprecation warnings in 16.83 seconds**. The failure exposed market-price statistics being treated as an individual property price. The price-evidence guard was corrected, and only that failing regression was rerun: **1 passed in 0.21 seconds**. The full suite was not repeated.

Ruff ran once across the implementation and related tests with `--fix`: **40 findings, 34 fixed automatically, 6 remaining**. The six remaining items were manually corrected: two unchanged import aliases, the retry predicate, a missing `urlparse` import, a UTC fallback, and a constructed default argument. Ruff was not rerun, so a post-correction lint pass is not claimed.

Tests use authorized CSV inputs, isolated in-memory Chroma collections, cached local models, and temporary output directories. Persistent Chroma clients and real LLM requests are blocked. Legacy crawler tests also write only temporary outputs and use local fixture responses. The indexing/retrieval integration exercised both actual datasets in the same temporary collection; a retrieval test used the real cached encoder.

Review generation processed **16 actual CSV files / 16 rows**, retaining **13 normalized records** and producing **84 searchable chunks**, with a maximum complete chunk length of **219 tokens**. DarGlobal retained its seven documents, two empty skips, and one duplicate skip. Wasalt retained all six records: two company pages, two directories, an auction catalog, and a legal-reference record. The legal reference has no searchable chunks. There are **12 searchable source documents**; no synthetic documents replace the actual datasets in the review output.

SHA-256 checks confirm the original DarGlobal review files and all existing processed DarGlobal files are unchanged. The persistent database was not opened; its observed file sizes are unchanged and modification timestamps predate this implementation. No frontend, raw CSV, or Groq credential/environment files were modified, and no Git commands were used.

## Remaining decisions

- Approve final production ingestion separately after reviewing the source reports, chunk preview, and proposed manifest.
- Establish the existing collection's historical embedding revision/dimension/provenance before adding vectors. No persistent collection was opened during this phase.
- Property-level Wasalt coverage is limited to the actual supplied CSVs. Additional authorized individual-property exports can use the same adapter and pipeline.
- The cached English-oriented encoder has not been calibrated for Arabic semantic quality; Unicode lexical matching and column aliases are supported. A different embedding model would require a separate compatible-collection/migration decision, preserving the current collection.

## Changed and created files

Created shared backend modules: `backend/data_access.py`, `backend/embedding.py`, `backend/csv_importer.py`, `backend/document_preparation.py`, `backend/indexing.py`, `backend/retrieval.py`, `backend/context.py`, and `backend/review.py`.

Updated service files: `backend/rag.py`, `backend/chatbot.py`, `backend/schemas.py`, and `backend/api/routes.py`. `backend/crawler.py` received filename-hash, URL-parser, retry-predicate, UTC-fallback, and lint fixes so its isolated legacy tests no longer rely on existing processed files.

Updated `scripts/csv_import.py`; created `scripts/index_review.py`. Corrected `pytest.ini` to use pytest's supported section and list syntax.

Created `tests/conftest.py`, `tests/test_document_preparation.py`, `tests/test_indexing.py`, and `tests/test_context.py`. Updated `tests/test_csv_import.py`, `tests/test_rag.py`, `tests/test_rag_audit.py`, `tests/test_api.py`, and `tests/test_extractors.py`.

Created this document and the five requested review outputs: `data/import_review/darglobal_import_report.md`, `data/import_review/wasalt_import_report.md`, `data/import_review/combined_import_report.md`, `data/import_review/chunk_review.json`, and `data/import_review/proposed_ingestion_manifest.json`.
