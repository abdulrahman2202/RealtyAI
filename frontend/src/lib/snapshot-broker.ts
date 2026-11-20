import { timingSafeEqual } from "node:crypto";

type Delegation = { delegationToken: string; clientSigningToken: string; validUntil: number };
type Issue = (options: { pathname: string; storeId: string; operations: ["get"]; validUntil: number }) => Promise<Delegation>;
type Presign = (token: Delegation, options: { pathname: string; operation: "get"; access: "private"; validUntil: number }) => Promise<{ presignedUrl: string }>;
type Environment = Record<string, string | undefined>;

const headers = { "Cache-Control": "private, no-store", "Vary": "Authorization", "X-Content-Type-Options": "nosniff" };
const collectionId = "51cdb05c-3ee9-4b04-b85c-71cbf168ff0d";
type BrokerStage = "broker_configuration" | "broker_authentication" | "broker_request_validation" | "delegation_issue" | "url_signing" | "signed_url_validation";
const safeErrorClasses = ["Error", "TypeError", "RangeError", "AbortError", "TimeoutError", "BlobError", "BlobAccessError", "BlobStoreNotFoundError", "BlobServiceNotAvailable", "BlobRateLimitError"];

function logBrokerFailure(stage: BrokerStage, message: string, error?: unknown) {
  const name = error instanceof Error ? error.name : undefined;
  const exceptionClass = error === undefined ? "None" : safeErrorClasses.find(allowed => allowed === name) || "Error";
  // Only caller-owned constant summaries are passed here. SDK errors, request
  // bodies, URLs, tokens and environment values are deliberately never printed.
  console.warn("Chroma snapshot broker failed.", { stage, exception_class: exceptionClass, message });
}

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
      logBrokerFailure("broker_configuration", "Required broker settings are missing or invalid.");
      return respond(503, { error: "Snapshot service is not configured." });
    }
    const supplied = Buffer.from(request.headers.get("Authorization") || "");
    const expected = Buffer.from(`Bearer ${secret}`);
    if (request.headers.has("Origin") || request.headers.has("Sec-Fetch-Mode")
      || supplied.length !== expected.length || !timingSafeEqual(supplied, expected)) {
      logBrokerFailure("broker_authentication", "Backend request authentication was rejected.");
      return respond(401, { error: "Unauthorized." });
    }
    if (request.method !== "GET" || new URL(request.url).search) {
      logBrokerFailure("broker_request_validation", "Only the exact configured GET request is supported.");
      return respond(400, { error: "Invalid snapshot request." });
    }
    let stage: BrokerStage = "delegation_issue";
    try {
      const now = Date.now();
      const key = `${storeId}:${pathname}`;
      if (!cached || cached.key !== key || cached.token.validUntil < now + 60_000) {
        cached = { key, token: await issue({ storeId, pathname, operations: ["get"], validUntil: now + 600_000 }) };
      }
      const expires = Math.min(now + 300_000, cached.token.validUntil);
      if (!Number.isFinite(expires) || expires <= now) throw new Error("Expired delegation");
      stage = "url_signing";
      const { presignedUrl } = await presign(cached.token, { pathname, operation: "get", access: "private", validUntil: expires });
      stage = "signed_url_validation";
      const url = new URL(presignedUrl);
      if (url.protocol !== "https:" || !url.hostname.endsWith(".private.blob.vercel-storage.com")
        || url.pathname !== `/${pathname}` || !url.search || url.username || url.password || url.hash) {
        throw new Error("Invalid delegation URL");
      }
      return respond(200, { url: presignedUrl, expires_at: new Date(expires).toISOString(), sha256, collection_id: collectionId });
    } catch (error) {
      cached = undefined;
      logBrokerFailure(stage, "Private snapshot delegation or signing failed; error details withheld.", error);
      return respond(503, { error: "Snapshot service is unavailable." });
    }
  };
}
