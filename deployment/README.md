# Local production and Vercel + Render deployment

Hosting is fixed to **Vercel Hobby + Render Free, ₹0/month**. Option B private-snapshot recovery is approved and implemented. The current [manual deployment guide](MANUAL_DEPLOYMENT.md) supersedes the earlier provider setup steps below. The user handles dashboard deployment; no hosting authentication or provisioning is performed by the agent. Render's working directory remains ephemeral; the independently stored private Blob snapshot supplies recovery.

## Existing data and local Docker

Use collection `realtyai_multisource_v1`, UUID `51cdb05c-3ee9-4b04-b85c-71cbf168ff0d`, from `data/vector_db_multisource`. The legacy `data/vector_db` is never mounted in the containers. Database content is excluded from both build contexts and images. No startup script indexes or creates collections.

The backend image contains the approved offline model snapshot, revision `1110a243fdf4706b3f48f1d95db1a4f5529b4d41`, with a read-only cache. Prepare it from the existing local cache:

```powershell
.venv/Scripts/python.exe -B scripts/prepare_container_assets.py
```

For a fresh isolated test snapshot, stop the local backend before copying, choose a new empty target, and run:

```powershell
.venv/Scripts/python.exe -B scripts/prepare_container_assets.py --snapshot-dir .tmp/phase78/vector_db --backend-stopped
```

This copies existing database files without embedding or ingestion and prepares private `deployment/local.env` using the unchanged existing Groq settings. Existing targets are not overwritten. The test snapshot used in this session already exists; retain it or use a different fresh target for another export.

For normal local operation, configure `deployment/local.env` from `deployment/local.env.example`. Set `REALTYAI_DB_HOST_PATH` to the existing database directory or a verified copy. On Linux, its directory must be writable by container UID/GID 10001. Keep real keys out of example files, source control, frontend variables and image build arguments.

```powershell
docker compose --project-name realtyai-phase78 --env-file deployment/local.env config --quiet
docker compose --project-name realtyai-phase78 --env-file deployment/local.env build
docker compose --project-name realtyai-phase78 --env-file deployment/local.env up -d --wait
```

Local frontend: `http://localhost:13000`. Backend: `http://127.0.0.1:18000`. `/health` checks application liveness; `/ready` verifies the existing approved UUID, 84 chunks, source counts, 12 documents, cosine metric and offline model cache. Missing data returns HTTP 503.

Persistent storage is a host bind mount with `create_host_path: false`. Container recreation retains that directory:

```powershell
docker compose --project-name realtyai-phase78 --env-file deployment/local.env up -d --force-recreate --wait
.venv/Scripts/python.exe -B scripts/verify_container_stack.py --after-recreation
```

For a consistent backup, stop all database writers and copy the entire directory, including SQLite and segment files. Keep backups outside image build contexts. Do not run ingestion scripts, clear collections, or use volume deletion as an update procedure.

## Render Free configuration

`render.yaml` is an **image-backed deployment template**, not an applied service. Its registry URL is a placeholder. It uses `plan: free`, the backend image, and `/ready` as the health path. The image respects Render's `PORT`; it runs one Uvicorn worker as a non-root user.

After a durable-storage design is approved and verified:

1. Authenticate the intended Render account and a no-charge container registry. Publish the tested backend image without adding database content:

   ```powershell
   docker tag realtyai-backend:local YOUR_EXISTING_REGISTRY/realtyai-backend:phase7
   docker push YOUR_EXISTING_REGISTRY/realtyai-backend:phase7
   ```

2. In Render, create a Web Service from **Existing Image**, or replace the placeholder in `render.yaml` and use the Blueprint. Choose **Free**. Image-backed deployment avoids Git operations.
3. Set the existing `GROQ_API_KEY`, `GROQ_BASE_URL`, and `GROQ_MODEL` only in backend settings. Set the exact approved collection path/name/UUID and the exact Vercel origin in `CORS_ORIGINS`. The offline cache is already bundled; do not download or re-embed on startup.
4. Provide only the explicitly approved durable data mechanism. The `REALTYAI_VECTOR_DB_DIR` setting alone does not persist files. No disk is configured in this free template; applying it today would leave `/ready` unhealthy because the database is absent.
5. Deploy, capture the actual HTTPS Render URL, verify `/ready` and both source questions, then confirm the same collection and data survive a real service lifecycle event. Do not upload the database with each deployment.

Render Free has 512 MB RAM and 0.1 CPU, 750 monthly free instance-hours per workspace, and idle spin-down after 15 minutes. Its filesystem changes are lost on restarts/redeploys/spin-down, and persistent disks are unavailable. A local simulation passed two serial chat requests at these resource limits, but first successful readiness took about 130 seconds. Cold starts may exceed the current frontend's 120-second chat timeout. Actual Render concurrency and memory behavior are not yet tested.

## Vercel frontend configuration

`frontend/vercel.json` selects Next.js and the existing npm build/install commands. `.vercelignore` excludes local environment files and build/dependency directories. The tested app uses Next.js 14.2.35 and Node 22; select Node 22 in project settings. The existing Inter font is bundled locally with unchanged font bytes.

Once the Render backend is live and durable storage is verified:

1. Authenticate the intended Vercel account, select the no-charge Hobby plan, and create/link the frontend project using directory `frontend`.
2. Set **Production and Preview** `NEXT_PUBLIC_API_URL` to the actual Render HTTPS URL. This is public and embedded during build; do not set Groq secrets in Vercel or any `NEXT_PUBLIC_*` variable.
3. Deploy the frontend files using Vercel's file-upload deployment API if Git operations remain disallowed. Use the project configuration above and preserve the ignore list. No deployment token is available in the current workspace.
4. Record the actual Vercel production URL, add its exact origin to Render's `CORS_ORIGINS`, and redeploy/restart the backend configuration as required.
5. Test both questions through that actual HTTPS frontend and inspect source cards, network errors and persistent data. A local URL or a template hostname is not a deployed application URL.

No Vercel or Render service was created in this session, no charges were incurred, and no working public URL is available yet. A ₹0 storage architecture change requires user approval before it is proposed or implemented.

Official references: [Render Free](https://render.com/docs/free), [persistent disks](https://render.com/docs/disks), [image-backed services](https://render.com/docs/deploy-an-image), [Blueprint specification](https://render.com/docs/blueprint-spec), [Vercel configuration](https://vercel.com/docs/project-configuration), [Vercel Hobby](https://vercel.com/docs/plans/hobby), and [file-upload deployment API](https://vercel.com/docs/rest-api/reference/endpoints/deployments/create-a-new-deployment).
