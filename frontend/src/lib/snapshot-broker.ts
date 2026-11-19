import { timingSafeEqual } from "node:crypto";

type Delegation = { delegationToken: string; clientSigningToken: string; validUntil: number };
type Issue = (options: { pathname: string; storeId: string; operations: ["get"]; validUntil: number }) => Promise<Delegation>;
type Presign = (token: Delegation, options: { pathname: string; operation: "get"; access: "private"; validUntil: number }) => Promise<{ presignedUrl: string }>;
type Environment = Record<string, string | undefined>;

const headers = { "Cache-Control": "private, no-store", "Vary": "Authorization", "X-Content-Type-Options": "nosniff" };
const collectionId = "51cdb05c-3ee9-4b04-b85c-71cbf168ff0d";

/** Only the authenticated backend receives a URL; this module has no browser import. */
export function createSnapshotHandler(issue: Issue, presign: Presign, environment: () => Environment = () => process.env) {
  let cached: { key: string; token: Delegation } | undefined;
  return async function handle(request: Request): Promise<Response> {
    const env = environment();
    const secret = env.REALTYAI_SNAPSHOT_CLIENT_TOKEN || "";
    const pathname = env.REALTYAI_SNAPSHOT_BLOB_PATH || "";
    const storeId = env.BLOB_STORE_ID || "";
    const sha256 = env.REALTYAI_SNAPSHOT_SHA256 || "";
    const respond = (status: number, body: object) => Response.json(body, { status, headers });
    if (!/^[A-Za-z0-9_-]{32,128}$/.test(secret) || !/^[a-f0-9]{64}$/.test(sha256)
      || !/^(store_)?[A-Za-z0-9]+$/.test(storeId)
      || !/^realtyai_multisource_v1-[a-f0-9]{64}(?:-[A-Za-z0-9]+)?\.tar(?:-[A-Za-z0-9]+)?\.gz$/.test(pathname)) {
      return respond(503, { error: "Snapshot service is not configured." });
    }
    const supplied = Buffer.from(request.headers.get("Authorization") || "");
    const expected = Buffer.from(`Bearer ${secret}`);
    if (request.headers.has("Origin") || request.headers.has("Sec-Fetch-Mode")
      || supplied.length !== expected.length || !timingSafeEqual(supplied, expected)) {
      return respond(401, { error: "Unauthorized." });
    }
    if (request.method !== "GET" || new URL(request.url).search) {
      return respond(400, { error: "Invalid snapshot request." });
    }
    try {
      const now = Date.now();
      const key = `${storeId}:${pathname}`;
      if (!cached || cached.key !== key || cached.token.validUntil < now + 60_000) {
        cached = { key, token: await issue({ storeId, pathname, operations: ["get"], validUntil: now + 600_000 }) };
      }
      const expires = Math.min(now + 300_000, cached.token.validUntil);
      if (!Number.isFinite(expires) || expires <= now) throw new Error("Expired delegation");
      const { presignedUrl } = await presign(cached.token, { pathname, operation: "get", access: "private", validUntil: expires });
      const url = new URL(presignedUrl);
      if (url.protocol !== "https:" || !url.hostname.endsWith(".private.blob.vercel-storage.com")
        || url.pathname !== `/${pathname}` || !url.search || url.username || url.password || url.hash) {
        throw new Error("Invalid delegation URL");
      }
      return respond(200, { url: presignedUrl, expires_at: new Date(expires).toISOString(), sha256, collection_id: collectionId });
    } catch {
      cached = undefined;
      return respond(503, { error: "Snapshot service is unavailable." });
    }
  };
}
