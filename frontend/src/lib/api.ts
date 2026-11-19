import { ChatResponse } from "@/types";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

class ApiError extends Error {
  status: number;
  detail: string;

  constructor(message: string, status: number, detail: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

async function handleResponse<T>(response: Response): Promise<T> {
  const text = await response.text();
  let body: unknown;
  try {
    body = text ? JSON.parse(text) : undefined;
  } catch {
    if (response.ok) {
      throw new ApiError("The API returned invalid JSON. Please try again.", response.status, "Invalid JSON response");
    }
  }
  if (!response.ok) {
    const detail = getErrorDetail(body) || text.trim() || response.statusText || "Request failed";
    throw new ApiError(
      `API request failed (HTTP ${response.status}): ${detail}`,
      response.status,
      detail
    );
  }
  if (body === undefined) {
    throw new ApiError("The API returned an empty response. Please try again.", response.status, "Empty response");
  }
  return body as T;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function getErrorDetail(body: unknown): string | undefined {
  if (!isRecord(body)) return undefined;
  const detail = body.detail || body.error || body.message;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail.map(item => {
      if (!isRecord(item)) return String(item);
      const field = Array.isArray(item.loc) ? item.loc.join(".") : "Request";
      return `${field}: ${String(item.msg || "Invalid value")}`;
    }).join("; ");
  }
  return undefined;
}

export async function sendChat(question: string): Promise<ChatResponse> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
      signal: AbortSignal.timeout(120000),
    });
  } catch (error) {
    if (error instanceof Error && (error.name === "TimeoutError" || error.name === "AbortError")) {
      throw new Error("The chat request timed out after 120 seconds. Please try again.");
    }
    throw new Error(`Unable to reach the chat API at ${API_BASE_URL}. ${error instanceof Error ? error.message : "Check your connection and try again."}`);
  }
  const body = await handleResponse<unknown>(response);
  if (isRecord(body) && body.success === false) {
    const detail = getErrorDetail(body) || "The API reported that the chat request failed. Please try again.";
    throw new ApiError(detail, response.status, detail);
  }
  if (!isRecord(body) || body.success !== true) {
    throw new ApiError("The API returned an invalid chat response: expected success: true.", response.status, "Invalid chat response");
  }
  if (typeof body.answer !== "string" || !body.answer.trim()) {
    throw new ApiError("The API returned no answer. Please try again.", response.status, "Missing or empty answer");
  }
  if (!Array.isArray(body.sources) || !body.sources.every(source =>
    isRecord(source) && typeof source.title === "string" && typeof source.url === "string"
  )) {
    throw new ApiError("The API returned invalid source references. Please try again.", response.status, "Invalid sources");
  }
  return { answer: body.answer, sources: body.sources, success: true };
}

export async function checkHealth(): Promise<{ status: string; service: string; version: string }> {
  const response = await fetch(`${API_BASE_URL}/health`, {
    signal: AbortSignal.timeout(10000),
  });
  return handleResponse(response);
}

export { ApiError };
