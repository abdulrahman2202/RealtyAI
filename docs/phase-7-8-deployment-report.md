# Phase 7–8 Dockerization and deployment status

**Latest investigation: the user reports production Render startup with failed snapshot recovery and readiness 503. The underlying production exception is not available in the supplied logs. Safe diagnostics have been added; no deployment or hosting-account access was performed during this investigation.** The earlier implementation and local-test evidence below is preserved. Actual public URLs have not been supplied or tested by the agent.

## Production recovery failure investigation

### Proven findings and limits

The only production evidence supplied is `Chroma snapshot recovery failed; readiness is unavailable.`, HTTP 503 from `/ready`, and successful server startup. The user confirmed no additional exception/stage logs are available. These observations prove the startup recovery function failed and the readiness gate stayed closed. They do **not** identify which configuration, broker, download, checksum, extraction or SQLite operation failed. No production root cause is guessed, and this update does not claim to have repaired the underlying deployed failure.

**Proven diagnostic defect:** [recover_from_environment](../backend/snapshot.py) previously caught filesystem/network/validation exceptions and raised a new generic `SnapshotError` with `from None`. [The lifespan handler](../backend/main.py) then caught that replacement and logged only the generic warning. The original class, error reason and failing stage were absent from logs. A separate `/ready` handler also returned generic 503 without logging its validation exception.

The recovery warning occurs **before Chroma client initialization and offline profile loading on `/ready`** in this implementation. Recovery verifies the installed Chroma package version and SQLite/manifest contents without opening a `PersistentClient` or loading model weights. Since `snapshot_ready` remains false, the middleware answers `/ready` and `/api/chat` with 503 before their normal handlers run. Chroma/Python library imports occur before lifespan; successful application startup alone does not certify the local cache, but model weight loading is not a step of the failed recovery function.

### Complete flow and diagnostic stages

| Stage | Operation and preserved check |
| --- | --- |
| `configuration` | Read required settings, validate HTTPS Vercel endpoint/exact private Blob URL, service credential format and both pinned hashes |
| `existing_database_validation` | Refuse a linked/unapproved populated target; validate its approved stored manifest and existing data without replacing it |
| `broker_request` | GET the configured Vercel route with backend service authentication; redirects remain blocked |
| `broker_response` | Bound response size and parse JSON; response text and headers are never logged |
| `ticket_validation` | Validate expiry, approved archive hash, collection UUID and exact signed destination; signed URL/query are never logged |
| `download_staging` / `blob_download` | Create a disposable download location, fetch the signed private Blob, enforce status/size/time limits |
| `target_directory` / `archive_checksum` | Preserve any nonempty target and verify archive size/SHA-256 |
| `filesystem_staging` / `archive_header` | Create a non-root staging directory, decode gzip/tar and require the first manifest member |
| `manifest_checksum` / `manifest_validation` | Check the pinned manifest SHA-256, approved identity/provenance and complete bounded file list |
| `archive_extraction` | Reject unsafe paths, duplicates, links and unexpected files; verify each file size and SHA-256 |
| `database_validation` | Check Chroma 1.5.9, read-only SQLite integrity, exact UUID/counts, reviewed text hashes, full metadata/original URLs and storage files |
| `filesystem_promotion` | Promote only the fully validated directory; never replace a populated database |
| `chroma_initialization` / `readiness_validation` | After successful recovery, `/ready` opens the existing collection and checks UUID, 84 chunks, 46/38 sources, 12 documents and cosine |
| `offline_model_profile` | Validate/read the offline tokenizer/configuration, approved revision/dimension and required cache files, including calls made while resolving the collection |
| `offline_embedding_model_loading` | On a later chat request, initialize cached SentenceTransformer weights locally; normal embedding failure types/cache behavior remain unchanged |

The Vercel broker now logs constant summaries for `broker_configuration`, `broker_authentication`, `broker_request_validation`, `delegation_issue`, `url_signing` and `signed_url_validation`. This distinguishes an upstream 503 from the broker's own configuration check versus its OIDC/delegation/signing code when the user inspects both providers' logs.

### Safe logging changes

Added [recovery_diagnostics.py](../backend/recovery_diagnostics.py). Stage contexts attach a safe record to the **original** exception and re-raise its original type. The generic public `SnapshotError` retains this diagnostic record before replacing the raw exception. Startup and later readiness warnings include stage, approved exception-class name, fixed/allowlisted message, numeric HTTP status/errno when present, and an approved missing configuration **key name** when applicable.

Raw exception messages, tracebacks, cause chains, filesystem paths, HTTP bodies/headers, API keys, service/delegation tokens, signed URLs, query parameters and environment values are never logged. Unknown messages/types are withheld. TLS certificate verification is reported specifically only when the exception identifies that condition; other SSL failures get a generic TLS-connection summary. Broker SDK errors are represented by a permitted class name and a caller-owned constant summary.

Example **illustrative diagnostic, not evidence of the current production cause**:

```text
Chroma snapshot recovery failed; readiness is unavailable. stage=broker_request exception=HTTPError message=Remote HTTP request was rejected. http_status=401 errno=None configuration_key=None
```

The authentication, URL/redirect restrictions, expiry bounds, SHA-256 pins, member/file limits, source/model provenance checks, nonempty-target protection and readiness/chat 503 behavior are unchanged. Existing embedding exception types and cache interfaces are preserved. No source ingestion, database/model migration, validation bypass, new environment logging setting, or paid resource was introduced.

### Exact manual redeployment and next diagnostic steps

1. In the user's existing Vercel project, redeploy the updated broker source with the same Production server configuration and private store connection. Keep Node 22, `npm ci` and `npm run build`. Do not expose or print authenticated ticket responses or change service credentials merely to investigate.
2. Rebuild the backend locally from this source using `docker build -f backend/Dockerfile -t YOUR-NAMESPACE/realtyai-backend:recovery-diagnostics .`; publish that image using the user's existing registry workflow. The existing approved offline model assets remain in the image; neither database nor the archive belongs in the image.
3. In the user's Render dashboard, deploy that new image/digest on the existing **Free** service. Keep the existing entrypoint, `/ready` health path, approved collection/path/UUID, both pinned hashes and all Groq settings. No snapshot re-upload, replacement, ingestion or data deletion is required.
4. Inspect the first safe failure line after startup, containing **stage, exception, message, HTTP status/errno**. If its stage is `broker_request` with 401/403/redirect status, inspect the corresponding Vercel authentication/routing log; with 503, inspect the new Vercel broker stage. `blob_download` identifies downstream object/network access; `archive_checksum`/`manifest_checksum` identifies a pin mismatch; `filesystem_staging`/`filesystem_promotion` with `PermissionError` identifies a denied filesystem operation; `database_validation` identifies archive content/SQLite validation. These are interpretation rules, not claims about the present cause.
5. Correct only the condition demonstrated by those diagnostics. Preserve the approved archive and hash values; do not make a failing archive pass by changing pins, publishing the store, weakening GET-only authentication, disabling TLS, clearing a target or bypassing readiness.
6. If recovery succeeds but `/ready` subsequently fails, use `chroma_initialization`, `readiness_validation` or `offline_model_profile` diagnostics to investigate that distinct failure. Model weights initialize on chat after readiness. Share only the newly sanitized failure line if further analysis is needed; credentials, configuration values and URLs are unnecessary.

No redeployment, account access, production network probe or hosting credential request was performed. Exact production classification remains **pending new safe diagnostics from the user's redeployment**. The initial underlying production exception cannot be reconstructed from the old generic warning.

### Scoped verification and preservation

Ran the relevant backend/API/RAG/recovery suite once after these changes: **105 passed**, 23 existing deprecation warnings, 18.94 seconds. The five broker tests, frontend TypeScript check and ESLint check passed. Scoped Ruff passed after one test-import ordering correction; only lint was repeated for that correction. No Docker build, deployment or live provider test was performed for this diagnostic-only change.

Focused regressions cover broker 401/503 versus Blob 403 stage identification, preservation of original HTTP/permission/JSON exception classes through the generic startup wrapper, missing configuration-key names without values, archive and manifest mismatch stages, permission errors without file paths, TLS classification without guessing, non-JSON broker responses without body logging, hostile exception arguments, deepest-stage preservation, separate Chroma/offline-profile errors, and Vercel configuration/signing failures without SDK message leakage. Startup failure tests confirm `/health` remains available, `/ready` and `/api/chat` remain 503, and downstream readiness/model initialization is not invoked after failed recovery.

All **18 protected files** matched before-work hashes, sizes and modification times: both original database directories, the approved archive and manifest, chunk review and ingestion manifest. Approved archive/manifest hashes remain the values already recorded below. No snapshot was regenerated or replaced outside isolated test fixtures, no existing Chroma database was opened for writing, and no data or security safeguard changed. See [diagnostic verification](../.tmp/phase78-render-diagnostics/verification.json).

## Final Option B implementation

- Added [snapshot recovery](../backend/snapshot.py) and [archive preparation](../scripts/prepare_chroma_snapshot.py). Startup performs bounded HTTPS downloads from the configured Vercel endpoint, accepts only the exact configured private Blob URL, rejects redirects/expired tickets, pins archive and manifest SHA-256, rejects unsafe/duplicate/link/oversized archive entries, verifies every extracted file, checks SQLite integrity and all 84 reviewed text hashes/full metadata/original URLs, and promotes a fully verified staging directory.
- A populated target is never overwritten. With the approved stored manifest, its existing corpus is verified without downloading/replacing it. Missing/invalid snapshot configuration, data or recovery leaves `/ready` and `/api/chat` at 503 while `/health` remains available. Corrupt/null SQLite text is rejected explicitly. No collection creation, indexing, dataset embedding, migration, automated write-back or original-database modification is performed by recovery.
- Added the [Vercel server route](../frontend/src/app/api/internal/chroma-snapshot/route.ts) and [broker](../frontend/src/lib/snapshot-broker.ts). It requires a backend-only service token, rejects browser-origin requests and caller-selected paths, and requests only private `get` permission for the exact archive. Signed URLs expire after five minutes; delegated credentials are cached for up to ten minutes. Blob credentials remain on Vercel with OIDC; Render receives no Blob write/delete credential. Authenticated tickets must never be logged or shared with the browser.
- Updated backend startup/readiness gating, writable non-root staging permissions, the unapplied Render template, server environment examples and ignore rules. Default local Compose keeps recovery disabled and uses its existing database bind mount. Added an isolated [TLS recovery-test override](../deployment/compose.recovery-test.yaml), configurable maintained verifiers and adversarial recovery/broker tests.
- Patched the frontend to **Next.js 15.5.29**, preserving React **18.3.1** and existing components/font/design. Pinned PostCSS **8.5.33** and transitive Zod **4.6.7**; retained the exact lockfile and overrides. Final npm audit: **zero advisories**. Next added TypeScript target ES2017. The chat deadline is now **240 seconds** for free-tier cold starts. RAG retrieval, context, prompts, indexing safeguards, approved data and Groq settings are unchanged.

## Archive and integrity

| Item | Verified local result |
| --- | --- |
| Approved source | `data/vector_db_multisource`, copied while quiescent; never archived from the running container's mount |
| Upload file | `.tmp/phase78-optionb/approved-snapshot/realtyai_multisource_v1-63ffdfe00886556eb5af27ab0a8a8ac74c54f061e3eb1a50717a9360e9bd4fa5.tar.gz` |
| Archive size / SHA-256 | **469,080 bytes** / `63ffdfe00886556eb5af27ab0a8a8ac74c54f061e3eb1a50717a9360e9bd4fa5` |
| Manifest SHA-256 | `a0189b6db2432cfdd43edfccb821250302fb7457ba73b7686422e64104c77ffc` |
| Contents | Five original SQLite/HNSW files plus the pinned manifest; all **84 chunks**, **46 DarGlobal / 38 Wasalt**, **12 documents** |
| Collection | `realtyai_multisource_v1`, UUID `51cdb05c-3ee9-4b04-b85c-71cbf168ff0d` |
| Model/storage | Chroma 1.5.9; cosine; MiniLM revision `1110a243fdf4706b3f48f1d95db1a4f5529b4d41`; 384 dimensions |
| Source preservation | Original active and legacy databases and Groq configuration match their before-work hashes; database modification times unchanged |
| Recovery | Two independently empty disposable runtime directories recovered successfully; same UUID, all IDs/text/metadata/original URLs and source/document counts |
| Cloud Blob | **Not created or uploaded.** Dedicated Private/no-TTL/overwrites-disabled setup is described for the user, not claimed as completed |

Evidence: [archive receipt](../.tmp/phase78-optionb/approved-snapshot/archive-receipt.json), [first recovery](../.tmp/phase78-optionb/storage-after-recovery.json), [second recovery](../.tmp/phase78-optionb/storage-after-second-recovery.json), and [preservation verification](../.tmp/phase78-optionb/preservation-final.json). Original databases, the approved archive and both recovered copies remain intact.

## Final local verification

| Check | Actual result |
| --- | --- |
| Relevant backend/API/RAG/recovery regressions | **88 passed**, 23 deprecation warnings, 11.97 seconds |
| Python lint | Passed for RAG runtime/API modules, recovery implementation/helpers and recovery tests; unused crawler/extractor lint backlog is outside this scope |
| Frontend TypeScript / ESLint / production build | All passed on Next.js 15.5.29 |
| Broker security tests | **3 passed**: unauthorized/browser exclusion, exact private GET-only scope and reuse, sanitized errors |
| npm security audit | **0 vulnerabilities**; final JSON retained |
| Docker builds | Final backend and frontend images built: `realtyai-backend:optionb`, `realtyai-frontend:optionb` |
| Compose health | Isolated backend, frontend and TLS fixture became healthy; original backend remained healthy |
| Adversarial recovery | Passed invalid hashes/manifests/unsafe/link/duplicate/oversized archive cases, genuine interrupted network read, expired tickets/provider credentials, redirects, nonempty-directory preservation, altered URLs/provenance/null text and readiness/chat 503 checks |
| Final image integrity | Final rebuilt backend image verified the recovered SQLite database and complete reviewed metadata through a read-only mount |
| Render-limit simulation | Two serial real frontend chat requests passed at **512 MiB, no swap, 0.1 CPU**; Docker usage after requests **417.3 MiB**, no OOM |
| Wasalt frontend question | HTTP 200, useful search/auction/project/mobile/broker/Matchmaker answer; correct corporate/homepage source cards and original URLs |
| Albert Hall frontend question | HTTP 200, useful South Kensington/Royal Albert Hall, Richard Norman Shaw, 1879–1886, architectural and waiting-list information; correct original title/URL source card; wording qualification below |

Full answers/screenshots: [frontend verification](../.tmp/phase78-optionb/frontend-verification.json). Commands, scope and results: [local verification](../.tmp/phase78-optionb/local-verification.json). The only real LLM manual questions were the two approved questions; regression tests use protected test collections/stubbed generation.

Verification retries are recorded honestly: an initial sandbox build could not spawn workers; an initial broker helper assumed the wrong working directory; Docker installation exposed real dependency advisories, prompting patched versions and frontend rechecks. The first Docker chat returned 502 because the fixture CA replaced public trust; a credential-free TLS probe confirmed certificate verification failure, and the fixture was corrected to include public roots without disabling TLS. A later regression run exhausted host model-allocation memory during Docker rebuilding; after releasing the completed isolated test stack, the final sequential run passed all 88 tests. These were not counted as initial passes. The original stack was never stopped; only completed isolated test containers were stopped, and their data/evidence were retained.

## Cleanup

The project inventory and maintained-reference searches were reviewed before removal. **Exactly two files were deleted**:

| Exact path | Reason |
| --- | --- |
| `C:/Programming/RealtyAI/.tmp/phase78/verify_frontend.cjs` | Superseded temporary copy of the maintained frontend verifier; URL/output/screenshot settings now have maintained configuration |
| `C:/Programming/RealtyAI/.tmp/phase78/verify_render_limits.cjs` | Same obsolete verifier copy with resource-test output paths; its historical outputs/screenshots and execution settings remain preserved |

Both contents/diffs/hashes and their original execution settings were captured before deletion; no maintained references were found. See [cleanup review](../.tmp/phase78-optionb/cleanup-review.json) and [project inventory](../.tmp/phase78-optionb/project-inventory.txt). No phase report, source data, database, manifest, integrity evidence, current verification output, original maintained source, lockfile or uncertain file was deleted.

## Manual deployment and remaining limits

Follow [the complete manual deployment guide](../deployment/MANUAL_DEPLOYMENT.md) for exact dashboard settings, registry/image commands, production visibility, Private Blob/no-TTL upload timing, OIDC, server secret placement, HTTPS API/CORS, startup settings, public chat checks and an actual Render lifecycle recovery test. [render.yaml](../render.yaml) and the Vercel configuration remain prepared and unapplied. No account authentication or hosting credential search is required for the user's manual workflow.

The stated personal portfolio/job-assignment demonstration matches the current Hobby personal/non-commercial clause on the supplied facts; this is a [documented eligibility assessment](../.tmp/phase78-optionb/eligibility-review.json), not provider account approval. The user must check actual Hobby/Free eligibility, training opt-out, available shared quotas and non-chargeable Render billing settings before provisioning. Stop if a paid plan/trial/upgrade, chargeable verification, or different architecture is required.

**Vercel public status/URL:** not deployed by the agent; none provided. **Render public status/URL:** not deployed by the agent; none provided. **Public chatbot and actual Render restart tests:** pending the user's deployments/URLs. **Incurred hosting charges:** ₹0. No private Blob or paid resource was provisioned, and no snapshot was uploaded externally.

Persistence is recovery of the fixed approved corpus, not synchronization of Render filesystem writes. Private Blob quota/account deletion and Render idle sleep/restarts can interrupt service. The 512 MiB test covers two serial requests, not concurrency or actual Render conditions. Cold startup took minutes locally; actual free-tier cold starts can still exceed the browser deadline. No always-on or unconditional permanent-retention guarantee is claimed.

**Answer qualification:** the Albert Hall answer again described access to Hyde Park/museums/Knightsbridge as views, reproducing the source-fidelity issue already recorded in Phase 6.11.3. Useful answer, correct source cards and expected facts passed the browser checks; sentence-level factual correctness is not fully certified. No RAG/prompt refactor was introduced. Verify this wording against the source during public testing.

## Historical Dockerization and storage investigation

The earlier sections below are preserved as historical evidence. Their pending-approval/deployment statements describe the earlier investigation; the final approval and manual-only deployment scope above govern the current state.

## Implementation

- FastAPI: pinned Python base, CPU-only Torch, pinned runtime dependencies, non-root user, single-worker entrypoint, runtime Groq environment injection, liveness and database/model readiness checks.
- Next.js: pinned Node base, dependency/build/runtime stages, standalone production output, non-root user and health check. Next.js was security-patched within the existing 14.2 series to **14.2.35**. The existing Inter font was bundled unchanged; frontend design/components were preserved.
- Compose: private environment file, loopback port bindings, health-based startup ordering, read-only root filesystems, dropped capabilities, no-new-privileges, resource limits and a persistent database bind mount that refuses to create missing host directories.
- Offline cache: the existing approved MiniLM snapshot was copied into the image as read-only assets. No runtime model downloads are required.
- Deployment templates: [render.yaml](../render.yaml), [Vercel configuration](../frontend/vercel.json), ignore rules and production environment examples. Render uses a free image-backed Docker service, so deployment need not use Git.

Groq credentials and configuration were preserved. The database is absent from the images; neither database was rebuilt or re-ingested. Original active database files still match the verified snapshot hashes. Legacy database hashes, sizes and timestamps still match the earlier preservation baseline.

## Local production verification

| Check | Result |
| --- | --- |
| Production image builds | FastAPI and Next.js images built successfully |
| Backend/API regression suite | **59 passed**, 23 deprecation warnings, 11.32 seconds; run once |
| Python lint | Passed; one initial broad exception finding corrected and lint rechecked |
| Frontend checks | TypeScript and ESLint passed; production build passed |
| Readiness | Both containers healthy; approved UUID and offline cache verified |
| Existing database | **84 chunks**, **46 DarGlobal / 38 Wasalt**, **12 documents**, UUID `51cdb05c-3ee9-4b04-b85c-71cbf168ff0d` |
| Stored data | All reviewed IDs, complete text, metadata and original URLs match |
| Recreation/persistence | Recreated containers retained the same UUID, 84 chunks and exact reviewed content/metadata |
| Wasalt question | Useful service answer and correct source cards through the Docker frontend |
| Albert Hall question | Useful descriptive answer and correct original-source card through the Docker frontend |
| Preservation | Original active database and legacy database unchanged; no indexing performed |

Local production frontend: **http://localhost:13000**. This is a local URL, not a public deployment. Backend: `http://127.0.0.1:18000`.

Evidence is retained in `.tmp/phase78/`: `container-storage.json`, `persistence-after-recreation.json`, `frontend-verification.json`, `render-limit-frontend.json`, `render-limit-results.json`, and `preservation-results.json`. The isolated database snapshot remains at `.tmp/phase78/vector_db`.

## Render Free resource and persistence findings

The same two frontend questions passed in a local container constrained to **512 MB RAM, no swap and 0.1 CPU**, with no OOM kill. Docker reported approximately **411.9 MiB** after the requests. Process RSS/high-water was approximately **593 MiB**, including mapped/shared file pages, so it differs from Docker's reported usage; actual Render behavior and concurrent load are not certified. The first successful health probe was approximately **130 seconds** after startup, which can exceed the frontend's existing 120-second timeout on cold starts.

Render Free has an ephemeral filesystem and cannot attach persistent disks. Its docs state that local SQLite/filesystem changes are lost on redeploys, restarts and idle spin-down. It provides 750 monthly free instance-hours and spins down after 15 idle minutes. The existing `PersistentClient` database directory therefore cannot be permanently retained on Render Free with the unchanged architecture.

The database was not added to the image, uploaded with deployments, or restored/re-ingested automatically. No external storage or alternative provider was introduced. A user-approved ₹0 storage architecture is required before deployment can produce a durable working chatbot.

## Storage investigation — 2026-11-20 IST

The user authorized investigation only. The readiness and Phase 6.11.3 ingestion reports were read first. This update preserves the implementation and prior verification results above.

**Evidence levels:** container inspection and file comparisons below are newly observed local facts; existing chat/build/resource results above are historical local tests; provider capabilities below are documented facts from official pages fetched on **2026-11-19 UTC**. No Vercel/Render account, remote Blob store, archive restoration, or live application was tested. Account eligibility, remaining quotas, archive compatibility after restoration, and actual cold-start behavior remain unverified.

### Options within Vercel + Render

| Option | Persistence and recovery | Trade-offs |
| --- | --- | --- |
| **A. Private Vercel Blob snapshot; Render downloads directly** | Upload one consistent archive of the existing Chroma directory once, independently of application deployments. Restore it into disposable Render storage when the working directory is absent. The stored snapshot survives Render lifecycle events. | Fewest moving parts. Official private-Blob HTTP access works outside Vercel using a server-side `BLOB_READ_WRITE_TOKEN`. That token permits writes/deletion as well as reads; a compromised backend could damage the remote snapshot. Restrict it to a dedicated store and retain an independent local backup. |
| **B. Private Blob snapshot; authenticated Vercel endpoint issues GET-only signed URLs — recommended** | Same snapshot and recovery behavior as A. A small server route in the existing Next.js project authenticates Render, then issues a short-lived URL for exactly the approved archive. Render downloads directly from Blob. | Blob credentials stay on Vercel; its SDK can use rotating OIDC credentials. Render holds only an application download credential, which cannot authorize Blob writes/deletion. Adds one internal endpoint and a startup dependency on Vercel. Signed delegation expires within **7 days maximum**, so a fixed URL in Render configuration is insufficient; obtain a fresh short-lived URL when needed. |
| **C. Client-encrypted snapshot in public Vercel Blob** | The encrypted archive survives Render restarts; Render fetches and decrypts its disposable copy using a backend-only key. No Blob write credential is needed on Render. | Same storage/transfer allowances, but ciphertext is publicly downloadable. Requires authenticated encryption, separate key backup, integrity verification, and key rotation procedures. Public downloads can exhaust the Hobby quota. Provider-managed encryption alone does not make a public Blob private. More operational burden than B. |

These are **snapshot recovery designs**, not a durable writable Chroma filesystem. All preserve the approved corpus without a database migration or new embeddings. Runtime database changes on Render would disappear on restart; no automatic write-back, ingestion, or snapshot replacement is proposed. Future corpus changes require a separately approved, versioned snapshot. Do not mount Blob as a SQLite/HNSW filesystem or copy individual changing database files to it.

The native alternatives reviewed do not meet indefinite ₹0 persistence: Render Free cannot attach a disk; Free Postgres becomes inaccessible after **30 days** and is deleted after its **14-day** upgrade grace period, with no free backups; Free Key Value loses all state on restart. Vercel runtime caches and deployment artifacts are not a persistent writable Chroma directory. A database inside each image/deployment would violate the agreed deployment constraints. Another datastore provider or database migration is outside the recommended design; neither was introduced.

### Guarantees, free-tier limits and privacy

- **Object durability:** [Vercel Blob](https://vercel.com/docs/vercel-blob) advertises S3-backed **99.999999999% durability** and **99.99% availability**. Blob storage is independent of Render's ephemeral disk. Its SDK documents indefinite retention when TTL is absent/removed. CDN cache expiry is separate from object deletion; retain the archive with **no TTL**.
- **Guarantee boundary:** those object-storage claims do not guarantee unlimited Hobby access or permanent account retention. [Vercel Terms §§4 and 19.1](https://vercel.com/legal/terms) allow Hobby changes/discontinuation and account termination, including inactivity; content may be permanently deleted on termination. Blob deletion is irreversible. Content-addressed paths and disabled overwrites provide application safeguards, not provider-enforced object locking. Keep the original database and an independent archive backup. No Hobby-specific contractual uptime guarantee was established; the published [SLA](https://vercel.com/legal/sla) is titled Enterprise Service Level Agreement.
- **Hobby allowance:** [Blob pricing](https://vercel.com/docs/vercel-blob/usage-and-pricing) includes **1 GB-month storage**, **10 GB Blob data transfer**, **10,000 simple operations** and **2,000 advanced operations**. Private and public stores have the same storage/operation pricing. CDN requests and origin transfer have additional shared allowances. When Hobby limits are exceeded, Blob access is blocked until the documented reset period; there is no paid overage on Hobby. Do not enable a Pro trial or paid plan.
- **Sizing:** newly observed file metadata totals **1,384,612 bytes (~1.32 MiB)** across five active-database files. This is the uncompressed directory size, not a measured archive size. As an estimate, 3,000 restorations of a 1.5 MB archive would transfer 4.5 GB before retries/overhead and other account usage. Actual archive size, download counts, signed-token usage accounting and remaining shared quotas must be checked before provisioning. No archive was created or uploaded during this investigation.
- **Eligibility/privacy:** Terms §4 permits Hobby only for **personal or non-commercial use**; RealtyAI's eligibility has not been established. Terms §3 also permits Hobby content use/sharing for model training with an account-setting opt-out. Confirm the appropriate opt-out before any data upload. Private access controls do not override those provider terms. If this is a commercial deployment, the proposed Hobby designs are not eligible; no paid alternative is authorized.
- **Render limits:** [Free services](https://render.com/docs/free) share 750 monthly instance-hours, sleep after 15 idle minutes and may restart at any time. [Outbound bandwidth](https://render.com/docs/outbound-bandwidth) includes **5 GB/workspace/month** on Hobby. Without a payment method, exhausted bandwidth suspends services; with one, Render can bill overages. Verify a non-chargeable Free account configuration before any provisioning. High service-initiated external traffic can also trigger suspension; restoring a small snapshot does not exempt the service from this policy. No keep-alive traffic is proposed.
- **Recovery time:** offline model assets remain in the existing image. Historical 512 MB/0.1 CPU tests passed, but readiness took approximately 130 seconds against a 120-second frontend chat timeout. Network restoration adds startup work. Stream bounded downloads/extraction before loading the model, then test the full cold-start path; neither Render memory headroom nor recovery latency is certified. A missing, invalid or inaccessible snapshot must leave `/ready` at 503.

### Recommended plan awaiting approval

Choose **B** for this fixed 84-chunk corpus, conditional on Hobby eligibility and available quotas. It keeps the database format, source evidence, providers and frontend design, while limiting Render to snapshot downloads. This is practical durable recovery for a low-traffic hobby application; it cannot provide uninterrupted production availability or persist new runtime writes at ₹0.

After explicit architecture approval, the implementation would proceed as follows; **none of these steps has been executed**:

1. Confirm personal/non-commercial Hobby eligibility, training opt-out, free account quotas and non-chargeable Render billing settings. Architecture implementation approval would cover the private snapshot setup below; a public deployment remains separately unauthorized. This investigation authorizes neither implementation nor provisioning/uploading.
2. Use an approved quiescent copy of `data/vector_db_multisource`, verified against `deployment/model-cache/manifest.json`. Package the **entire** SQLite/HNSW directory with a file-hash/size manifest, without opening the original through Chroma. Do not archive the live container-mounted copy while it is in use. Do not include legacy data or environment files. Keep both original database directories unchanged.
3. Create a dedicated **private** Vercel Blob store on Hobby, then upload the approved archive once with no TTL and overwrites disabled. Use a versioned, content-addressed name such as `realtyai/snapshots/realtyai_multisource_v1/sha256-<approved-archive-hash>.tar.gz`. Verify the uploaded bytes; retain the local archive and the original directory. Application image builds and subsequent deployments never upload database content.
4. Add only an authenticated server endpoint, proposed `GET /api/internal/chroma-snapshot`, to the existing Vercel project. Require a backend-only service credential, pin the single archive path, and issue only `get` permission with a short expiry. Reject caller-selected paths and operations. Use Vercel OIDC for Blob access. Do not expose the archive, download credential or signed URL in browser variables, frontend responses or logs. Do not forward Groq credentials to Vercel.
5. Add opt-in Render snapshot settings: proposed `REALTYAI_SNAPSHOT_ENDPOINT`, `REALTYAI_SNAPSHOT_CLIENT_TOKEN` (secret), and `REALTYAI_SNAPSHOT_SHA256`; retain `REALTYAI_VECTOR_DB_DIR=/var/lib/realtyai/chroma`, `REALTYAI_COLLECTION_NAME=realtyai_multisource_v1` and UUID `51cdb05c-3ee9-4b04-b85c-71cbf168ff0d`. The existing offline MiniLM revision remains `1110a243fdf4706b3f48f1d95db1a4f5529b4d41`, cosine, 384 dimensions. Leave normal local Compose behavior unchanged unless recovery is explicitly enabled.
6. Before opening Chroma, restore only into an absent/empty disposable target, using bounded streaming, pinned SHA-256, safe archive paths, no links, approved file/size limits and a staging directory writable by the non-root user. Verify all file hashes and promote the complete directory atomically. Refuse to overwrite any existing nonempty database. Validate SQLite integrity on the disposable copy, pinned Chroma **1.5.9**, UUID, 84 chunks, 46/38 source counts, 12 documents, model provenance, reviewed IDs/text/metadata and original citation URLs. Do not call collection creation/indexing, rebuild HNSW, re-embed, or automatically write back to Blob. Fail closed on any mismatch.
7. Test restore, interrupted/invalid downloads, existing-directory protection, expired credentials, offline embeddings and resource/cold-start behavior locally before public deployment. Existing Docker containers must not be stopped or deleted without separate approval. Once public deployment is authorized, use only Vercel Hobby and Render Free, configure HTTPS API/CORS, test the two approved frontend questions, and verify snapshot recovery after an actual Render lifecycle event. Account/limit failures block progress rather than trigger paid upgrades.

## Why Docker shows two backend containers

**Newly inspected:** `2026-11-19 UTC`; two retained backend container objects, **one running backend**. Both use `realtyai-backend:local`, exact image ID `sha256:05d699e03ea85727caefce9a7a9e1aab223aff2ca0fe94e632d3acda33f1451a`, and `/app/backend/container-entrypoint.sh`.

| Container | Compose association and purpose | Current status | Required? |
| --- | --- | --- | --- |
| `realtyai-phase78-backend-1` (`2713f0788262`) | Actual `backend` service in Compose project `realtyai-phase78`, configured by `compose.yaml` and the private local environment file. Network `realtyai-phase78_default`; 1 GiB RAM/1 CPU; restart policy `unless-stopped`. | **Running, healthy**, no OOM. Active `127.0.0.1:18000 → 8000` port. | **Yes**, for the current local Docker frontend at port 13000. |
| `realtyai-render-free-probe` (`85412dac3139`) | Separate manually created `docker run` resource probe from earlier tests: 512 MiB RAM, equal memory+swap limit (no additional swap), 0.1 CPU; network `bridge`; restart policy `no`. It carries `project=realtyai-phase78` / `service=backend` labels. | **Exited (0)**, no OOM; no active listening port. Retains cached `unhealthy` status after exit, although the last two recorded health checks exited 0 and prior test evidence records successful chat checks. | **No** for normal operation; retain only if another resource probe is wanted. No cleanup performed. |

**Verified cause of grouping:** the image itself contains `com.docker.compose.project=realtyai-phase78`, `com.docker.compose.service=backend` and `com.docker.compose.version=2.39.1`. The manually started probe inherited these labels. It lacks the actual Compose container's config-hash, container-number and configuration-file labels. It is not a second service declared in `compose.yaml`. Docker Desktop grouping by those labels is an inference; the image/container label identity is directly inspected.

Both mount only `C:/Programming/RealtyAI/.tmp/phase78/vector_db` at `/var/lib/realtyai/chroma`, **not either original database**. The exited probe retains a configured host port of 18000, so restarting it unchanged would conflict with the running service and reuse its database copy. No container was started, stopped, restarted, removed or relabeled in this investigation.

Sanitized evidence: [container inventory](../.tmp/phase78/storage-research/backend-container-inventory.json). Public-document text snapshots and URL/fetch-time/SHA-256 metadata are retained in `.tmp/phase78/storage-research/`.

## Deployment steps, cost and remaining requirements

Follow [the exact local and provider deployment runbook](../deployment/README.md). The Vercel and Render templates contain placeholders for the actual image/project/service URLs. Use backend-only Groq secrets, the actual Render HTTPS URL for frontend `NEXT_PUBLIC_API_URL`, and the exact Vercel production origin for CORS. The frontend build checks that Vercel's API URL is HTTPS.

**Budget and incurred hosting charges: ₹0.** Templates specify Render Free and Vercel Hobby only, with no paid disk. No hosting credentials are configured in the current workspace. Investigation is now authorized and complete; the recommended storage design requires explicit implementation approval. Public deployment remains separately unauthorized and would require live URL/persistence testing before a success claim. Existing deployment configuration remains unchanged and unapplied.

The investigation rechecked the original active database against the Phase 7–8 manifest and all nine legacy files against the Phase 6.11.3 hashes, sizes and modification times: **unchanged**. A final comparison confirmed **112 protected files unchanged**, including application source, tests, scripts, configuration, prior reports and both databases. Report links and 14 official-document text snapshots also passed verification; see [investigation verification](../.tmp/phase78/storage-research/investigation-verification.json) and [source index](../.tmp/phase78/storage-research/sources.json). No database was opened through Chroma, migrated, archived, uploaded or ingested. Only this deployment report and new investigation evidence were written; no application implementation, deployment configuration or existing report was otherwise changed. Prior test/lint results were preserved; suites/builds were not rerun for this documentation-only investigation.

**Working public URL: none.** Deployment success is not claimed. No Git commands were run. Existing narrative answer wording remains model-dependent, as noted in the Phase 6.11.3 report; no RAG refactor or new product features were introduced.
