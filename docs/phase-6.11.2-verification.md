# Phase 6.11.2 verification and ingestion plan

**Status:** Retrieval and answer fixes are verified using the actual new data in an isolated collection. Persistent ingestion and activation await explicit approval. Remaining manual verification was limited to the two questions requested by the user.

## Root cause and changes

The frontend correctly calls `POST /api/chat`. The persistent `realtyai_properties` collection contains only two legacy DarGlobal records; the 84 prepared chunks were never ingested. The legacy Albert Hall document is only `Albert Hall Mansions. THE ALBERT HALL MANSION`, so it cannot supply the new descriptive information. Neither legacy record contains a verified embedding model revision. Historical documentation and the shared 384-dimensional shape do not establish compatibility. Its effective stored distance configuration is L2; the old `hnw_distance_method=cosine` metadata does not configure the index.

The numeric answer guard also confused model citation numbers and document IDs with unsupported facts, replacing whole answers with an unavailable response. A 512-token completion limit truncated some Groq answers. General service queries admitted unrelated knowledge types and weak chunks that displaced useful descriptions.

The fixes scope company/auction questions, improve descriptive ranking, preserve raw distances and complete context chunks, resolve valid evidence citations to original URLs, retain useful source excerpts when generation fails numeric grounding, and increase the completion budget to 1,800 tokens. Attribute answers quote relevant complete paragraphs; missing dates do not suppress other available descriptions. Configured retrieval failures return HTTP 503, distinct from successful empty retrieval.

Changed implementation: `backend/chatbot.py`, `backend/context.py`, `backend/retrieval.py`, `backend/rag.py`, `backend/api/routes.py`; added `backend/collection_setup.py` and `scripts/index_multisource.py`. Updated `tests/conftest.py`, `tests/test_context.py`; added `tests/test_chat_retrieval.py`, diagnostic/API/browser verification scripts, `.env.example` selection comments, and a Git ignore for the new database directory. Frontend components, Groq credentials, existing indexing safeguards, and the prepared Phase 6.11 artifacts were not changed.

## Two-question frontend verification

Both questions were submitted through the existing Next.js UI to the real FastAPI endpoint and Groq, using an isolated collection containing the actual 84 prepared chunks.

| Question | Retrieval/context | Verified answer and citations |
| --- | --- | --- |
| What services does Wasalt provide? | 8 retrieved, 7 context chunks; 1,251 tokens / 5,040 bytes | Useful information about verified property search, auctions, projects/masterplans, broker connections, mobile apps, and listing services. Source cards link to the actual Wasalt corporate page and homepage. |
| What information is available about THE ALBERT HALL MANSION? | 6 retrieved, 6 context chunks; 716 tokens / 2,933 bytes | South Kensington/Royal Albert Hall location, Richard Norman Shaw, 1879–1886 construction, Queen Anne revival architecture, and residences 7 & 8. Missing floor-plan details are qualified without suppressing available information. Source card retains the original exported DarGlobal URL. |

Every selected chunk body reached the captured context and the actual Groq request. Browser checks confirmed useful rendered answers, expected source facts, original URLs from the new review documents, correct source-card titles, and no chat errors. No frontend redesign was needed.

Full request context, raw Groq output, final answers, selected chunks, and citations are in `data/import_review/phase6112_chat_verification.json`; browser results are in `data/import_review/phase6112_frontend_verification.json`.

Relevant backend/API regression checks passed: **57 passed**, 23 deprecation warnings, 9.91 seconds. Ruff passed across all changed Python implementation, test, and verification files. Frontend type checking, ESLint, and production build passed. The repository-wide preexisting Ruff backlog recorded in the readiness report was outside this change.

## Concrete persistent collection proposal

The reviewable plan is `data/import_review/phase6112_collection_plan.json`.

| Setting | Proposed value |
| --- | --- |
| Collection | `realtyai_multisource_v1` |
| Database directory | `C:/Programming/RealtyAI/data/vector_db_multisource` |
| Distance | Cosine, configured through Chroma's HNSW configuration |
| Embedding model | `sentence-transformers/all-MiniLM-L6-v2` |
| Revision | `1110a243fdf4706b3f48f1d95db1a4f5529b4d41` |
| Dimension / maximum input | 384 / 256 tokens |
| Preparation version | `6.11.1`, preserving the existing deterministic IDs |
| Data | 84 chunks: DarGlobal 46, Wasalt 38; 12 searchable source documents |

Creation is explicit and separate from normal requests. The execution command validates the approved plan, original review hash, all chunk texts/IDs, model provenance, and cosine configuration. Every append retains the existing actual-collection-UUID approval, conflict preflight, append-only batches, locking, and receipts. A repeat against the approved UUID skips identical chunks; isolated tests confirmed 84 additions followed by zero additions on retry.

After approval, execute:

```powershell
.venv/Scripts/python.exe -B scripts/index_multisource.py --execute --create-collection --approved-plan data/import_review/phase6112_collection_plan.json --approval-reference "User approval for Phase 6.11.2 ingestion and activation"
```

Then select the resulting collection using these non-secret backend settings and restart the backend:

```dotenv
REALTYAI_VECTOR_DB_DIR=data/vector_db_multisource
REALTYAI_COLLECTION_NAME=realtyai_multisource_v1
```

The legacy database directory remains separate. SHA-256, file-size, and modification-time comparisons confirm all legacy files are unchanged. No legacy records were deleted, modified, or re-embedded. The new persistent database does not yet exist, and the original review manifest still records zero additions.

Approval is required by `backend/indexing.py`: “Execution requires an injected collection and explicit ingestion approval,” followed by `approval.require_target(collection)`. Once approved, persistent ingestion and activation are the remaining steps; verification will remain limited to the same two questions. Narrative answer faithfulness remains model-dependent, with the recorded source evidence available for review. Dockerization and deployment have not started.
