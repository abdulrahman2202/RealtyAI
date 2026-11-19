# Combined DarGlobal + Wasalt Import Review — Phase 6.11

User confirmed permission from DarGlobal and Wasalt in Phase 6.11 (2026-11-19).

Both actual datasets use the same normalization, preparation, indexing, retrieval, and citation architecture. No Wasalt quarantine remains. Production ingestion is pending explicit approval.

| Source | CSV files | Rows read | Retained records | Searchable documents | Chunks |
| --- | ---: | ---: | ---: | ---: | ---: |
| darglobal | 10 | 10 | 7 | 7 | 46 |
| wasalt | 6 | 6 | 6 | 5 | 38 |

Maximum complete chunk length: 219 / 256 tokens.

All CSV files, including legal/reference files, were processed. Records unsuitable for property retrieval are listed in the manifest as exclusions. Empty and duplicate rows are documented in the source reports.

The original seven-record DarGlobal extracted_records.json and import_report.md were not overwritten. New normalized records for both sources are included in chunk_review.json.documents.

The proposed manifest contains deterministic document/chunk IDs, content fingerprints, preparation version, source lineage, and embedding provenance. Its IDs have not been checked against the existing database. Actual indexing requires target-bound IngestionApproval, verified legacy embedding provenance, and a successful conflict preflight; it only adds absent chunks.

Semantic vector search is combined with lexical/entity matching and source/page-type scopes. Exact individual-property names narrow retrieval to their own source identity. Company pages, directories, and auction catalogs remain separate knowledge kinds. Context contains complete selected chunks within tokenizer and byte budgets, with property identities and original-source citations. Missing attribute information is reported as unavailable; attribute answers quote source evidence.

Limitations: no individual-property Wasalt documents are fabricated from directories; coverage is limited to the actual provided CSV rows. The cached encoder is English-oriented, and Arabic semantic quality needs an authorized benchmark; Unicode lexical matching is supported. Persistent collection configuration and historical encoder provenance remain unverified because this phase did not open the database.

Tests and Ruff results are recorded in docs/multi_source_rag.md after final verification.
