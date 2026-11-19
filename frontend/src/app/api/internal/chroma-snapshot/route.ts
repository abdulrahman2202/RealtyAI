import { issueSignedToken, presignUrl } from "@vercel/blob";
import { createSnapshotHandler } from "@/lib/snapshot-broker";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export const GET = createSnapshotHandler(issueSignedToken, presignUrl);
