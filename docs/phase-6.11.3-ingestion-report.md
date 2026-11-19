# Phase 6.11.3 persistent ingestion, activation and cleanup

**Completed:** approved ingestion, activation, the two frontend checks, and safe cleanup. The user explicitly approved this plan in Phase 6.11.3. Verification used the actual Next.js frontend and ordinary `backend.main:app` server.

## Persistent ingestion

| Check | Actual result |
| --- | --- |
| Database directory | `C:/Programming/RealtyAI/data/vector_db_multisource` |
| Collection | `realtyai_multisource_v1` |
| Actual collection UUID | `51cdb05c-3ee9-4b04-b85c-71cbf168ff0d` |
| Stored chunks | **84** |
| DarGlobal / Wasalt | **46 / 38** |
| Searchable source documents | **12** |
| Distance metric | **Cosine**, verified in the HNSW configuration |
| Embedding model | `sentence-transformers/all-MiniLM-L6-v2` |
| Revision | `1110a243fdf4706b3f48f1d95db1a4f5529b4d41` |
| Dimensions | **384**; every stored vector is finite and normalized |
| Approved review SHA-256 | `549d281fb310a485d12ad90d81679052ab673926ed164caed8f133a11a67bdc4` |

The existing approved ingestion script completed with 84 additions. It validated the plan, current cached profile, complete reviewed chunk text/IDs, target metadata and cosine configuration, and bound the protected append to the newly created collection UUID. Indexing safeguards were unchanged.

Read-back checks confirmed the exact reviewed IDs, complete texts and metadata for all 84 chunks. Every document identity was recomputed from source and canonical URL, while stored citation URLs and titles exactly matched the original reviewed values. All 12 searchable documents are represented; excluded legal-reference material was not ingested.

The subsequent indexing preflight found **84 identical chunks, zero pending additions, zero additions, and zero conflicts**. No additional ingestion was needed.

Evidence: [ingestion receipt](../data/import_review/phase6112_ingestion_receipt.json), [storage verification](../data/import_review/phase6113_storage_verification.json), and [repeat preflight](../data/import_review/phase6113_indexing_preflight.json).

## Legacy preservation and activation

All nine files in `data/vector_db` matched the earlier Phase 6.11.2 baseline and the baseline captured before this ingestion, including SHA-256, file sizes and modification times. The legacy `realtyai_properties` collection and its two records were not opened through Chroma, modified, re-embedded, migrated or deleted. A read-only immutable SQLite check confirmed collection UUID `2de231c0-8e11-41b7-9962-4e3a24ad4be7` and exactly two records.

Only these backend environment selections were updated:

```dotenv
REALTYAI_VECTOR_DB_DIR=data/vector_db_multisource
REALTYAI_COLLECTION_NAME=realtyai_multisource_v1
```

Hashes confirm all other existing environment values, including Groq credentials and configuration, are unchanged. No frontend environment variables were changed. The prior isolated test backend was stopped and the actual backend restarted with:

```powershell
.venv/Scripts/python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Backend configuration resolved the new collection UUID and 84 stored chunks. `/health` returned HTTP 200; the existing Next.js application on port 3000 returned HTTP 200. Both services remain running for local use.

Evidence: [preservation baseline](../data/import_review/phase6113_preservation_baseline.json) and [activation verification](../data/import_review/phase6113_activation_verification.json).

## Actual frontend verification

| Question | Result |
| --- | --- |
| What services does Wasalt provide? | **Passed, HTTP 200.** The rendered answer described verified property search, online/hybrid and timed auctions, projects/masterplans, plot reservations, mobile apps, broker connections and Matchmaker. Source cards correctly linked the Wasalt corporate page and homepage using the original reviewed URLs. |
| What information is available about THE ALBERT HALL MANSION? | **Passed, HTTP 200.** The rendered answer provided South Kensington/Royal Albert Hall context, Richard Norman Shaw, 1879–1886 construction, Queen Anne revival architecture, and the waiting-list qualification for missing floor-plan details. The source card preserved the original exported DarGlobal title and URL. |

The browser checks confirmed useful answers, expected source facts, matching source-card titles and URLs, and no chat or browser errors. The responses used the new persistent collection. Frontend components were unchanged.

Evidence: [browser results and full answers](../data/import_review/phase6113_frontend_verification.json), [Wasalt screenshot](../data/import_review/phase6113_frontend-0.png), and [Albert Hall screenshot](../data/import_review/phase6113_frontend-1.png). Earlier Phase 6.11.2 verification files remain unchanged and describe their earlier isolated checks.

## Cleanup review and information preservation

**Deleted: 26 files** — 22 obsolete test-run fixtures/outputs, one superseded Phase 6.10.3 audit, one redundant legacy hash snapshot, and two completed/unused temporary verifier copies. Only empty obsolete scratch directories were removed. Post-cleanup comparison confirmed **108 retained existing files unchanged**, no unexpected changes, all planned deletion paths absent, and the legacy database still intact. See [final verification](../data/import_review/phase6113_final_verification.json).

Each deletion candidate was inspected and hashed before deletion. Searches found no maintained source, test, script, README or current-document dependency on its exact path. Temporary fixtures were distinguished from original raw CSVs and processed application records; temporary receipts identify isolated test collections, not the live collection.

The retained authoritative review contains the same source knowledge, chunk IDs, chunk texts and embedding provenance as the redundant Phase 6.11 test preview. Its three temporary Markdown reports are byte-identical copies of retained source reports. Differences in the temporary JSON outputs are generation/timestamp review metadata, not new source knowledge.

Important information from the superseded Phase 6.10.3 audit is preserved here and in [the cleanup review](../data/import_review/phase6113_cleanup_review.json): title/description-only embeddings omitted full content/page type; five of seven full source records exceeded the 256-token encoder limit; `hnw_distance_method` did not configure the distance metric; the old distance conversion was discontinuous; request-time ingestion and unverified legacy embedding provenance required correction. Current shared preparation, retrieval and protected indexing address those findings, and the approved separate collection preserves legacy storage.

The retired audit recorded **30 passed, 12 skipped in 12.95 seconds**, exit 0, and a passing Ruff check over its four selected importer/audit files. Its seven token-measurement rows are preserved in the cleanup review JSON. Its Astera size caution is also retained: `682 - 12,277 SQFT` and `61 to 265 sqm` are separate source ranges whose relationship was not established; no conversion or reconciliation was performed.

The legacy hash snapshot's complete nine-file data is preserved in the new baseline, which records the successful comparison. Maintained diagnostic scripts, their currently referenced output files, current reports/designs, original data, both database directories, source code, tests and README are preserved. `data/import_review/import_report.md` is retained because the current review generator and combined report reference it.

## Remaining issues

No ingestion, count, provenance, metadata, idempotency, activation or chat-error blocker was found. Groq wording still needs source review: in the live Albert Hall answer it described nearby Hyde Park/museum/shopping access as views, while the source establishes access and specifically overlooking the Royal Albert Hall. Source cards are correct, but sentence-level narrative entailment is not formally guaranteed by the existing guard. No implementation changes were introduced in this phase.

The mandatory earlier reports retain their historical review-only/pending-approval statements. This report and the current ingestion receipt record the approved executed state. Dockerization, deployment and Git commands were not started.

## Exact cleanup paths and reasons

All 26 paths below were listed and reviewed before deletion, matched their inspected hashes immediately before removal, and were verified absent afterward. Paths are absolute in the workspace; hashes, reasons, inspection results and completion status are preserved in the cleanup review JSON.

| Exact path | Reason |
| --- | --- |
| `C:/Programming/RealtyAI/.tmp/phase6103-pytest-4fa9b5598b02470e9ef693c09136edcb/test_importer_writes_nested_re0/review/extracted_records.json` | Superseded Phase 6.10.2 test-generated schema-review output for one explicitly synthetic record; schema/design, source data, and tests are preserved. |
| `C:/Programming/RealtyAI/.tmp/phase6103-pytest-4fa9b5598b02470e9ef693c09136edcb/test_importer_writes_nested_re0/review/import_report.md` | Superseded Phase 6.10.2 test-generated schema-review output for one explicitly synthetic record; schema/design, source data, and tests are preserved. |
| `C:/Programming/RealtyAI/.tmp/phase6103-pytest-4fa9b5598b02470e9ef693c09136edcb/test_importer_writes_nested_re0/synthetic_darglobal/01-first.csv` | Runtime-generated synthetic importer fixture from an obsolete test run; original raw CSVs and maintained tests are preserved. |
| `C:/Programming/RealtyAI/.tmp/phase6103-pytest-4fa9b5598b02470e9ef693c09136edcb/test_importer_writes_nested_re0/synthetic_darglobal/02-duplicate.csv` | Runtime-generated synthetic importer fixture from an obsolete test run; original raw CSVs and maintained tests are preserved. |
| `C:/Programming/RealtyAI/.tmp/phase6103-pytest-4fa9b5598b02470e9ef693c09136edcb/test_importer_writes_nested_re0/synthetic_darglobal/03-empty.csv` | Runtime-generated synthetic importer fixture from an obsolete test run; original raw CSVs and maintained tests are preserved. |
| `C:/Programming/RealtyAI/.tmp/phase611-final-tests-ec0c61b1a45f4c7aa26921328955c40c/test_both_actual_sources_appen0/receipt.json` | Obsolete receipt for an isolated ephemeral test collection, not application ingestion; current persistent receipt and preflight are preserved. |
| `C:/Programming/RealtyAI/.tmp/phase611-final-tests-ec0c61b1a45f4c7aa26921328955c40c/test_crawler_produces_json_out0/darglobal/429d90ae2a80.json` | Disposable crawler-fixture output from a completed test run; local HTML fixture, crawler test, and actual processed records are preserved. |
| `C:/Programming/RealtyAI/.tmp/phase611-final-tests-ec0c61b1a45f4c7aa26921328955c40c/test_partial_failure_can_resum0/receipt.json` | Obsolete receipt for an isolated ephemeral test collection, not application ingestion; current persistent receipt and preflight are preserved. |
| `C:/Programming/RealtyAI/.tmp/phase611-final-tests-ec0c61b1a45f4c7aa26921328955c40c/test_recursive_discovery_first0/a/first.csv` | Runtime-generated delimiter/deduplication/malformed-row fixture from a completed test run; maintained tests recreate it and original raw CSVs are preserved. |
| `C:/Programming/RealtyAI/.tmp/phase611-final-tests-ec0c61b1a45f4c7aa26921328955c40c/test_recursive_discovery_first0/b/malformed.csv` | Runtime-generated delimiter/deduplication/malformed-row fixture from a completed test run; maintained tests recreate it and original raw CSVs are preserved. |
| `C:/Programming/RealtyAI/.tmp/phase611-final-tests-ec0c61b1a45f4c7aa26921328955c40c/test_recursive_discovery_first0/b/second.csv` | Runtime-generated delimiter/deduplication/malformed-row fixture from a completed test run; maintained tests recreate it and original raw CSVs are preserved. |
| `C:/Programming/RealtyAI/.tmp/phase611-final-tests-ec0c61b1a45f4c7aa26921328955c40c/test_recursive_discovery_first1/a/first.csv` | Runtime-generated delimiter/deduplication/malformed-row fixture from a completed test run; maintained tests recreate it and original raw CSVs are preserved. |
| `C:/Programming/RealtyAI/.tmp/phase611-final-tests-ec0c61b1a45f4c7aa26921328955c40c/test_recursive_discovery_first1/b/malformed.csv` | Runtime-generated delimiter/deduplication/malformed-row fixture from a completed test run; maintained tests recreate it and original raw CSVs are preserved. |
| `C:/Programming/RealtyAI/.tmp/phase611-final-tests-ec0c61b1a45f4c7aa26921328955c40c/test_recursive_discovery_first1/b/second.csv` | Runtime-generated delimiter/deduplication/malformed-row fixture from a completed test run; maintained tests recreate it and original raw CSVs are preserved. |
| `C:/Programming/RealtyAI/.tmp/phase611-final-tests-ec0c61b1a45f4c7aa26921328955c40c/test_recursive_discovery_first2/a/first.csv` | Runtime-generated delimiter/deduplication/malformed-row fixture from a completed test run; maintained tests recreate it and original raw CSVs are preserved. |
| `C:/Programming/RealtyAI/.tmp/phase611-final-tests-ec0c61b1a45f4c7aa26921328955c40c/test_recursive_discovery_first2/b/malformed.csv` | Runtime-generated delimiter/deduplication/malformed-row fixture from a completed test run; maintained tests recreate it and original raw CSVs are preserved. |
| `C:/Programming/RealtyAI/.tmp/phase611-final-tests-ec0c61b1a45f4c7aa26921328955c40c/test_recursive_discovery_first2/b/second.csv` | Runtime-generated delimiter/deduplication/malformed-row fixture from a completed test run; maintained tests recreate it and original raw CSVs are preserved. |
| `C:/Programming/RealtyAI/.tmp/phase611-final-tests-ec0c61b1a45f4c7aa26921328955c40c/test_review_outputs_use_actual0/chunk_review.json` | Redundant Phase 6.11 test review output; authoritative source reports, reviewed text/IDs, original source knowledge, and ingestion plan are preserved. |
| `C:/Programming/RealtyAI/.tmp/phase611-final-tests-ec0c61b1a45f4c7aa26921328955c40c/test_review_outputs_use_actual0/combined_import_report.md` | Redundant Phase 6.11 test review output; authoritative source reports, reviewed text/IDs, original source knowledge, and ingestion plan are preserved. |
| `C:/Programming/RealtyAI/.tmp/phase611-final-tests-ec0c61b1a45f4c7aa26921328955c40c/test_review_outputs_use_actual0/darglobal_import_report.md` | Redundant Phase 6.11 test review output; authoritative source reports, reviewed text/IDs, original source knowledge, and ingestion plan are preserved. |
| `C:/Programming/RealtyAI/.tmp/phase611-final-tests-ec0c61b1a45f4c7aa26921328955c40c/test_review_outputs_use_actual0/proposed_ingestion_manifest.json` | Redundant Phase 6.11 test review output; authoritative source reports, reviewed text/IDs, original source knowledge, and ingestion plan are preserved. |
| `C:/Programming/RealtyAI/.tmp/phase611-final-tests-ec0c61b1a45f4c7aa26921328955c40c/test_review_outputs_use_actual0/wasalt_import_report.md` | Redundant Phase 6.11 test review output; authoritative source reports, reviewed text/IDs, original source knowledge, and ingestion plan are preserved. |
| `C:/Programming/RealtyAI/data/import_review/rag_content_audit.md` | Superseded Phase 6.10.3 compatibility audit; its findings, measured token counts, size-range caution, and historical verification results are preserved in the current ingestion report and cleanup review. |
| `C:/Programming/RealtyAI/.tmp/phase6112/legacy_baseline.json` | Redundant prior legacy-file hash snapshot; the current preservation baseline contains the same nine hashes/sizes/timestamps and records a successful comparison to this snapshot. |
| `C:/Programming/RealtyAI/.tmp/phase6113/verify_chat_probe.py` | Unused temporary copy of the API verifier; the actual backend was started directly with Uvicorn and the maintained source verifier is preserved. |
| `C:/Programming/RealtyAI/.tmp/phase6113/verify_frontend_probe.cjs` | Completed temporary browser-verifier copy used to preserve prior reports; current browser results/screenshots and the maintained source verifier are preserved. |
