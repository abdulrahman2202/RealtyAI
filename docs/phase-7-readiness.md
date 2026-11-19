# Phase 7 readiness

**Reviewed:** 2026-11-19. **Status:** Ready to plan Docker implementation; lint is not clean and container builds remain unverified. No critical Phase 6.11 issue was identified.

## Verification results

Read [multi_source_rag.md](multi_source_rag.md) and all five Phase 6.11 outputs in `data/import_review/`: `darglobal_import_report.md`, `wasalt_import_report.md`, `combined_import_report.md`, `chunk_review.json`, and `proposed_ingestion_manifest.json`.

| Check | Result |
| --- | --- |
| Recorded pytest | Full backend suite: **85 passed, 1 failed**, 10 deprecation warnings, 16.83 seconds. After correcting property-price evidence, the failing regression alone passed: **1 passed**, 0.21 seconds. Results are present, so pytest was not rerun. A passing final full-suite run is not recorded. |
| Recorded Ruff | **40 findings, 34 automatically fixed, 6 manually corrected**; no subsequent lint pass recorded. |
| Ruff verification today | Ran `.venv/Scripts/python.exe -m ruff check --no-cache backend tests scripts/csv_import.py scripts/index_review.py` **once**, without fixes: **112 findings, exit 1**, 93 automatically fixable. Includes existing extractor/model/processor issues and `F821` for `path` in `backend/processor.py:107`. The original lint command/scope is unspecified, so the totals are not directly comparable. |
| Artifact consistency | **13 normalized records**, **12 searchable documents**, **84 chunks**: DarGlobal 46, Wasalt 38. IDs, text fingerprints, manifest metadata, and embedding provenance agree. Maximum recorded chunk length: **219/256 tokens**. The Wasalt legal reference is excluded from chunks. |
| Ingestion state | Both JSON artifacts remain `review_only`; production ingestion is false, persistent collection access is false, and `added_count` is **0**. Existing collection identity/provenance remain unverified. |

The price guard and regression test are present. Historical outcomes lack raw logs and exact pytest commands. DarGlobal's URLs, titles, content, and timestamps are preserved, with normalized source identity and added provenance. SHA-256 comparison confirms **61 preexisting backend, test, script, documentation, configuration, and dataset files remain unchanged** during this task.

## Existing setup

| Area | Current state |
| --- | --- |
| Backend | Python **3.12.2**, FastAPI **0.115.0**, Uvicorn **0.54.0**. Entry point `backend.main:app`; `GET /health`, `POST /api/chat`, `/docs`. Health checks do not call Groq or establish database/model readiness. |
| Frontend | Next.js **14.2.3**, React 18, App Router; `npm run build` and `npm start`. Lockfile exists. Standalone output is not enabled. Browser requests use `NEXT_PUBLIC_API_URL`; local value is `http://127.0.0.1:8000`. Inter is downloaded by `next/font/google` during builds. |
| Docker | No Dockerfiles, `.dockerignore`, Compose files, or container runbook. Installed CLI: Docker **28.3.2**, Compose **2.39.1-desktop.1**. Docker daemon/Linux-container operation was not tested. |
| Environment | Root `.env` contains Groq and legacy AgentRouter settings; frontend `.env.local` contains the public API URL. These local files are untracked/ignored. `.env.example` lacks CORS, storage, model-cache, and Docker settings. `backend/main.py` and `backend/llm.py` load dotenv with `override=True`. Secret values were redacted during inspection. |
| ChromaDB | Embedded `PersistentClient`, ChromaDB **1.5.9**; collection `realtyai_properties`. `REALTYAI_VECTOR_DB_DIR` already overrides `data/vector_db`. SQLite exists (**659,456 bytes**) alongside two segment directories. Only filesystem metadata was inspected; latest observed write: **2026-11-19 11:40:51.455 UTC**. |
| Embeddings | CPU-only inference using locally cached `sentence-transformers/all-MiniLM-L6-v2`, **384 dimensions**, revision `1110a243fdf4706b3f48f1d95db1a4f5529b4d41`. The local snapshot and `refs/main` exist. Containers must receive this cache because the loader requires local files. |

## Missing requirements and exact implementation steps

Implement these in Phase 7, in order:

1. **Protect configuration and build contexts.** Add root and frontend `.dockerignore` files excluding secrets, `.env*`, `.git`, virtual environments, caches, `node_modules`, `.next`, and host datasets/database files. Ignore new private environment files in Git, retaining examples. Update `.env.example` with the settings below. Inject only required Groq settings into the backend at runtime; require `${GROQ_API_KEY:?GROQ_API_KEY is required}`. Keep credentials out of build arguments and `NEXT_PUBLIC_*`. Change dotenv loading to `override=False` in both backend configuration modules so injected values take precedence.

2. **Create `backend/Dockerfile`.** Use `python:3.12-slim-bookworm` with a recorded image digest, `/app`, `libgomp1`, and dependency installation before copying `backend/`. Check pinned Linux wheels and compatible CPU Torch wheels; existing requirements also contain development tools. Run as a non-root user with writable storage. Start `python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --workers 1`, without reload or indexing commands.

3. **Supply the approved model cache.** Mount the relevant hub cache read-only at `/opt/hf/hub`, including `refs/main`, the approved snapshot, tokenizer, weights, and pooling configuration. Preserve referenced blobs or dereference files. Verify the revision above and offline inference.

4. **Create `frontend/Dockerfile` and enable standalone output.** Use `node:22-bookworm-slim` with a recorded digest: `npm ci`, `npm run build`, then a non-root runner containing `.next/standalone` and `.next/static`. Set `output: "standalone"` in `frontend/next.config.js`. Start `node server.js` with `HOSTNAME=0.0.0.0`, `PORT=3000`. Allow build-time Google Fonts access or bundle Inter locally.

5. **Create `compose.yaml` with two services.** Build backend from repository context using `backend/Dockerfile`, and frontend from `./frontend`. Publish `127.0.0.1:8000:8000` and `127.0.0.1:3000:3000`. Add Python and Node HTTP probes for `/health` and `/` respectively; make frontend depend on backend with `condition: service_healthy`, allowing time for Python imports. Keep Chroma embedded.

   | Setting/mount | Required value |
   | --- | --- |
   | Backend runtime | `GROQ_API_KEY` required; retain existing `GROQ_BASE_URL` and `GROQ_MODEL` |
   | CORS | `CORS_ORIGINS=http://localhost:3000` |
   | Database | `REALTYAI_VECTOR_DB_DIR=/app/data/vector_db` |
   | Persistent bind mount | `${VECTOR_DB_HOST_PATH:-./data/vector_db}` to `/app/data/vector_db`, read/write, long syntax with `bind.create_host_path: false` |
   | Model bind mount | `${MODEL_CACHE_HOST_PATH:?MODEL_CACHE_HOST_PATH is required}` to `/opt/hf/hub`, read-only, `bind.create_host_path: false` |
   | Offline model settings | `HF_HUB_CACHE=/opt/hf/hub`, `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1` |
   | Frontend build argument | `NEXT_PUBLIC_API_URL=http://localhost:8000`; set it before `next build` |

   Preserve the entire database directory, including SQLite and all segment files. Confirm mount permissions using a disposable copy before using the existing database. Browser requests need a browser-reachable URL; Docker service name `backend` cannot serve as the public API URL. Next.js embeds `NEXT_PUBLIC_API_URL` at build time, so runtime environment changes alone will not update it.

6. **Document and validate.** Record prerequisites, private configuration, backups with writers stopped, mounts, startup/shutdown, and persistence. Use `docker compose config --quiet` to avoid printing secrets. For future checks, set `VECTOR_DB_HOST_PATH` to an existing disposable directory or consistent database copy before `docker compose build` and `docker compose up -d --wait`. Check health, browser chat/CORS, offline models, empty-database unavailable responses, and persistence across recreation. Chroma reads can write SQLite metadata, so database smoke checks must use the disposable copy. Run relevant backend and frontend type/lint/build checks after changes; address the lint backlog explicitly.

No CSV review generation, indexing, collection initialization, ingestion, builds, container starts, or deployment occurred. Future ingestion requires separate collection-bound approval and verified legacy embedding provenance. Stop here until Phase 7 implementation is requested.
