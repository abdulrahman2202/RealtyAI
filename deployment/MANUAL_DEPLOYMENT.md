# Manual Vercel Hobby + Render Free deployment

The agent prepares and tests the application locally. **You perform all account access, image publishing, private Blob setup and public deployment.** No Vercel/Render/registry credentials are required by the agent. There is no deployed public URL yet.

## 1. Check eligibility and prevent charges

RealtyAI is a personal portfolio and technical job-assignment demonstration, not a commercial service or revenue-generating application. This stated use is consistent with [Vercel Terms §4](https://vercel.com/legal/terms), which permits personal or non-commercial Hobby use. Vercel retains discretion over eligibility; do not describe a commercial use as personal. Reassess before any commercial operation.

In Vercel, select **Hobby**, not a trial or Pro. Check your account's remaining Blob and frontend quotas. Before uploading source/data, review the account's model-training setting and opt out as appropriate under Terms §3. In Render select the **Hobby workspace / Free instance**, no disk/add-on, and check the billing page. Render can charge bandwidth overages when a payment method is linked: use a configuration with no chargeable payment method. If account verification requires a charge, a paid plan, or you cannot prevent overage charges, **stop**. Do not proceed on an assumption of zero billing.

Relevant published allowances: Vercel Blob 1 GB-month storage, 10 GB monthly Blob transfer, 10,000 simple and 2,000 advanced operations; frontend/CDN allowances are shared. Render Free has 512 MB RAM, 0.1 CPU, 750 workspace instance-hours/month, and Hobby outbound bandwidth of 5 GB/month. Check the actual dashboards; these are not account-specific quota confirmations. Quota exhaustion can suspend access. Render can suspend excessive external traffic. Do not add keep-alive traffic or upgrade automatically.

## 2. Keep the data outside source uploads and images

Preserve `data/vector_db` and `data/vector_db_multisource`. Do not ingest, rebuild, migrate or clear either database. Neither directory is part of the Docker image. The offline approved embedding model is already staged at `deployment/model-cache/hub` and included in the backend image; no runtime model download is needed.

The approved upload is this **single archive**, created from a verified quiescent copy:

```text
.tmp/phase78-optionb/approved-snapshot/realtyai_multisource_v1-63ffdfe00886556eb5af27ab0a8a8ac74c54f061e3eb1a50717a9360e9bd4fa5.tar.gz
```

Archive bytes: **469,080**. SHA-256: `63ffdfe00886556eb5af27ab0a8a8ac74c54f061e3eb1a50717a9360e9bd4fa5`.

Manifest SHA-256: `a0189b6db2432cfdd43edfccb821250302fb7457ba73b7686422e64104c77ffc`.

The archive contains all five database files and `snapshot-manifest.json`, with 84 exact reviewed chunk identities, full metadata, text hashes, 46/38 source counts, 12 documents, the collection UUID and embedding provenance. The standalone manifest and `archive-receipt.json` remain beside it for local integrity evidence. Keep the archive/copy as an independent backup. Upload **only the `.tar.gz`** to Blob, once. Do not put it into GitHub, the frontend, a public asset directory, a container image, or every application deployment.

You handle GitHub/source upload yourself. Retain the ignore files: `.tmp`, both databases, local `.env` files, staged model assets and dependency/build caches are excluded. Never include credentials in a dashboard source upload.

## 3. Build and publish the backend image yourself

The locally tested image is `realtyai-backend:optionb`. For a fresh build from the repository root:

```powershell
docker build -f backend/Dockerfile -t realtyai-backend:optionb .
```

Use your own no-charge image-registry account and verify its free limits. With Docker Hub, the manual commands are:

```powershell
docker login
docker tag realtyai-backend:optionb YOUR-NAMESPACE/realtyai-backend:optionb
docker push YOUR-NAMESPACE/realtyai-backend:optionb
```

Do not put the database or secrets in the image. The user supplies registry authentication only in their own Docker/Render tools. Keep the pushed immutable image digest for the Render deployment. Image-backed Render deployment is needed because the offline model cache is intentionally absent from source control; importing a source-only Docker build would omit that cache.

## 4. Create the Vercel project and private Blob store

In Vercel **Add New → Project**, import your source using your chosen dashboard workflow. Set:

| Project setting | Value |
| --- | --- |
| Plan | Hobby |
| Root directory | `frontend` |
| Framework | Next.js |
| Node.js | 22.x |
| Install command | `npm ci` |
| Build command | `npm run build` |
| Output directory | Framework default |

Next.js uses Vercel's managed runtime; no custom start command is required. Local production start is `npm start`; the frontend Docker image starts `node server.js`.

The final tested frontend uses **Next.js 15.5.29**, React 18.3.1 and Node 22. Next.js and transitive PostCSS/Zod were patched after a real npm audit found vulnerabilities; the final audit is clear. Keep the lockfile and overrides. `next lint` is deprecated but still supported in this release; no lint-tool migration or frontend redesign was introduced.

Vercel's build requires `NEXT_PUBLIC_API_URL` to be HTTPS. If the actual Render URL has already been assigned, use it now. Otherwise a **bootstrap-only** value such as `https://backend-not-configured.invalid` allows project creation; chat will not work until it is replaced with the real Render URL and the frontend is rebuilt. Never treat that bootstrap deployment as a working chatbot. Record the actual project production domain from **Settings → Domains**.

Ensure the **Production** deployment is publicly accessible in **Settings → Deployment Protection**; Vercel platform-login protection must not block Render's request to the production broker route. Preview deployments may remain protected. The broker still requires its own backend service credential, and the Blob store remains Private. Do not add a platform-bypass token or share Vercel login credentials with the agent.

Before the upload, open **Storage → Create Storage → Blob**, create a **dedicated Private** store, and connect it to this project for **Production** with **OIDC enabled**. The SDK is `@vercel/blob` 2.9.0. Do not create a public store. Connected OIDC settings supply `BLOB_STORE_ID`; Render must never receive the Blob read-write token or Vercel OIDC token.

In the private store's file browser, upload the exact `.tar.gz` from section 2 **once**, using its content-addressed filename. Leave TTL unset; confirm no expiration in file details. Do not select overwrite/replace for an existing object. Keep overwrite protection enabled (`allowOverwrite=false`); use a fresh object rather than replacing one. If the dashboard cannot confirm Private/no-expiration/new-object settings, stop instead of assuming. Keep the original upload unchanged for subsequent code deployments.

Copy the file's **private Blob URL** and exact **pathname** from its details. Dashboard uploads may add a random suffix; use the exact resulting pathname, not a guessed filename. The broker accepts the approved hash filename with normal suffix placement. The URL belongs in backend settings only, not browser code. Retain the local archive/hash receipt for comparison.

## 5. Generate and place the recovery secret

Generate a high-entropy service token locally without printing it to logs/chat:

```powershell
.venv/Scripts/python.exe -B -c "from pathlib import Path; import secrets; p=Path('deployment/recovery.local.env'); p.open('x').write('REALTYAI_SNAPSHOT_CLIENT_TOKEN='+secrets.token_urlsafe(48)+'\n'); p.chmod(0o600)"
```

The ignored file is deliberately created with exclusive mode: do not overwrite an existing token. Copy its value privately into both providers' **server environment settings**. Do not send it to the agent. The local Docker TLS fixture uses an unrelated test credential and is never deployed.

Vercel **Settings → Environment Variables → Production**:

| Variable | Value / placement |
| --- | --- |
| `BLOB_STORE_ID` | Dedicated private store ID from its connected OIDC settings |
| `REALTYAI_SNAPSHOT_BLOB_PATH` | Exact uploaded archive pathname from file details |
| `REALTYAI_SNAPSHOT_CLIENT_TOKEN` | Generated server-only token |
| `REALTYAI_SNAPSHOT_SHA256` | `63ffdfe00886556eb5af27ab0a8a8ac74c54f061e3eb1a50717a9360e9bd4fa5` |
| `NEXT_PUBLIC_API_URL` | Actual Render HTTPS URL; the only public setting |

Do not set Groq keys in Vercel. Redeploy after environment/store changes. The broker route is **`GET /api/internal/chroma-snapshot`**. It requires the service credential, rejects browser-origin requests and caller-selected paths, and returns a five-minute private GET-only URL to the authenticated backend. Its ten-minute delegation is cached within a running function instance. Do not inspect/share authenticated ticket bodies or log signed URLs. An unauthenticated browser request should receive 401 (503 if not yet configured), never a URL.

## 6. Create Render Free from the existing image

In Render **New → Web Service → Existing Image**, select your published backend image/digest. Choose **Free**, your preferred available region, and **no persistent disk**. Use **`/ready`** for Health Check Path. Leave Docker command override blank: the image entrypoint runs:

```text
python -m uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1
```

Render supplies `PORT`. No build command is used for an Existing Image service. Record the actual service HTTPS URL from the dashboard. `render.yaml` is a reference template only; it has not been applied.

Set these Render environment variables:

| Variable | Exact value / placement |
| --- | --- |
| `GROQ_API_KEY` | Existing unchanged key, backend secret only |
| `GROQ_BASE_URL`, `GROQ_MODEL` | Existing unchanged values from your root `.env` |
| `CORS_ORIGINS` | Exact actual Vercel production origin, no wildcard |
| `REALTYAI_VECTOR_DB_DIR` | `/var/lib/realtyai/chroma` |
| `REALTYAI_COLLECTION_NAME` | `realtyai_multisource_v1` |
| `REALTYAI_COLLECTION_ID` | `51cdb05c-3ee9-4b04-b85c-71cbf168ff0d` |
| `REALTYAI_SNAPSHOT_ENDPOINT` | `https://ACTUAL-PROJECT.vercel.app/api/internal/chroma-snapshot` |
| `REALTYAI_SNAPSHOT_CLIENT_TOKEN` | Same generated server-only token as Vercel |
| `REALTYAI_SNAPSHOT_BLOB_URL` | Exact private Blob URL, without a signed query |
| `REALTYAI_SNAPSHOT_SHA256` | `63ffdfe00886556eb5af27ab0a8a8ac74c54f061e3eb1a50717a9360e9bd4fa5` |
| `REALTYAI_SNAPSHOT_MANIFEST_SHA256` | `a0189b6db2432cfdd43edfccb821250302fb7457ba73b7686422e64104c77ffc` |
| `HF_HUB_CACHE` | `/opt/models/hub` |
| `HF_HUB_OFFLINE`, `TRANSFORMERS_OFFLINE` | `1` |
| `OMP_NUM_THREADS`, `MKL_NUM_THREADS` | `1` |

The embedding model remains `sentence-transformers/all-MiniLM-L6-v2`, revision `1110a243fdf4706b3f48f1d95db1a4f5529b4d41`, dimension 384, cosine metric. No ingestion/startup indexing command is permitted.

Initial service startup may be unhealthy while the Vercel endpoint/environment is incomplete. Complete Vercel configuration and redeploy it, then restart/redeploy Render. Recovery failures keep `/ready` and `/api/chat` at 503. Logs include only `Chroma snapshot startup: recovered`, `existing_verified`, or a generic failure; no service secrets or signed URLs.

Once Render has its actual URL, set that URL as Vercel Production `NEXT_PUBLIC_API_URL` and redeploy the frontend. Public API values are embedded at build time. Confirm Render CORS uses the actual Vercel production domain. Enable Preview only with intentional endpoint/CORS settings; production secrets need not be shared with every preview.

## 7. Verify the actual deployed application

1. Open `https://ACTUAL-RENDER.onrender.com/health`, then `/ready`. Readiness must return HTTP 200, `realtyai_multisource_v1`, UUID `51cdb05c-3ee9-4b04-b85c-71cbf168ff0d`, and 84 chunks. Its checks also enforce 46/38 source counts, 12 documents, cosine and offline model provenance. Startup additionally verifies complete reviewed metadata, original URLs and SQLite integrity.
2. Open the actual Vercel production website. Check for browser/network/CORS errors. Ask only the two approved questions: **What services does Wasalt provide?** and **What information is available about THE ALBERT HALL MANSION?** Confirm useful evidence-based answers and source-card titles/links against `data/import_review/chunk_review.json`. Do not interpret HTTP 200 alone as answer/citation correctness.
3. In Render perform an actual manual restart/lifecycle event. Its free filesystem is ephemeral. Wait for `Chroma snapshot startup: recovered`, check `/ready` again, and test the frontend. This verifies fixed-snapshot recovery; it does not prove writable disk persistence. Do not upload the archive again or ingest anything.
4. Check Vercel Blob storage/transfer/operations and Render memory/bandwidth/instance-hours after the lifecycle test. Verify plans still show Hobby/Free and no charges. Keep a private record of results, without authenticated ticket responses.
5. Share only the ordinary Vercel and Render public URLs with the agent for final live verification. Do not share tokens, Blob signed URLs or environment dumps. Public deployment success remains unclaimed until live tests pass.

## Limits and troubleshooting

Render sleeps after 15 idle minutes. Cold starts can take several minutes; the browser chat deadline is 240 seconds. Warm `/ready` before initial manual chat tests. There is no always-on availability guarantee, and actual Render behavior must still be measured. A full/expired quota can make the otherwise intact Blob unavailable. Invalid/expired credentials or blocked network access cause readiness 503; inspect only safe status messages and privately check the two providers' server configuration. Do not disable TLS/hash/provenance checks or upgrade automatically.

The remote snapshot is the durable fixed corpus; Render's local copy is disposable. No runtime writes are synchronized back to Blob. Any future source update needs separate approval and a new versioned archive. Vercel account termination/deletion can remove stored objects; keep the original databases and an independent archive backup. This is a ₹0 portfolio deployment, not an unconditional permanent-storage or production-uptime guarantee.

For local recovery tests only, the retained fixture override is `deployment/compose.recovery-test.yaml`; it uses an isolated TLS fixture and test containers on ports 13800/18800. The completed isolated stack was stopped to release memory; its two recovered directories and evidence remain. The original stack on 13000/18000 was preserved. To repeat with the retained fixture:

```powershell
docker compose --project-name realtyai-optionb --env-file .tmp/phase78-optionb/local-second.env -f compose.yaml -f deployment/compose.recovery-test.yaml up -d --wait --wait-timeout 360
```

The local test certificate is short-lived and must be regenerated before repeating after expiry. It is never used in production; the local trust bundle combines standard public CAs with the fixture CA. Never publish the fixture settings, test private key, archive or `.tmp` files as application source.
