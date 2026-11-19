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
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = (await response.json()) as { detail?: string };
      detail = body.detail || detail;
    } catch {
      // ignore parse errors, use statusText
    }
    throw new ApiError(
      `API request failed: ${detail}`,
      response.status,
      detail
    );
  }
  return response.json();
}

export async function sendChat(question: string): Promise<ChatResponse> {
  const response = await fetch(`${API_BASE_URL}/api/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ question }),
    signal: AbortSignal.timeout(120000),
  });
  return handleResponse<ChatResponse>(response);
}

export async function checkHealth(): Promise<{ status: string; service: string; version: string }> {
  const response = await fetch(`${API_BASE_URL}/health`, {
    signal: AbortSignal.timeout(10000),
  });
  return handleResponse(response);
}

export { ApiError };
