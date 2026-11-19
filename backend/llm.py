from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from openai import APIConnectionError, APIError, OpenAI, RateLimitError

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env", override=True)

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_BASE_URL = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

# Module-level Grok client (OpenAI SDK pointed at Groq).
_client: OpenAI | None = None


class LLMError(Exception):
    """Base exception for LLM (Groq) failures."""

    status_code: int = 500


class LLMConfigError(LLMError):
    """Raised when LLM configuration is missing or invalid."""

    status_code: int = 500


class LLMRateLimitError(LLMError):
    """Raised when the Groq API rate limit is exceeded."""

    status_code: int = 429


class LLMConnectionError(LLMError):
    """Raised when the Groq API cannot be reached."""

    status_code: int = 502


class LLMTimeoutError(LLMError):
    """Raised when the Groq API request times out."""

    status_code: int = 504


def get_client() -> OpenAI:
    """Lazily initialise and return the Groq-backed OpenAI client."""
    global _client
    if _client is None:
        if not GROQ_API_KEY:
            raise LLMConfigError("GROQ_API_KEY is not set in the environment")
        _client = OpenAI(
            api_key=GROQ_API_KEY,
            base_url=GROQ_BASE_URL,
            timeout=60.0,
        )
    return _client


def generate(
    messages: list[dict[str, str]],
    model: str | None = None,
    temperature: float = 0.0,
    max_completion_tokens: int = 512,
) -> str:
    """Generate a chat completion from the supplied messages.

    Returns the assistant message content. Raises RuntimeError with a clear
    message on API or network failures.
    """
    client = get_client()
    model_name = model or GROQ_MODEL
    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=messages,
            temperature=temperature,
            max_completion_tokens=max_completion_tokens,
        )
        return response.choices[0].message.content or ""
    except RateLimitError as error:
        raise LLMRateLimitError(f"Groq rate limit exceeded: {error}") from error
    except APIConnectionError as error:
        raise LLMConnectionError(f"Groq connection error: {error}") from error
    except APIError as error:
        raise LLMError(
            f"Groq API error (status {error.status_code}): {error.message}"
        ) from error
    except TimeoutError as error:
        raise LLMTimeoutError(f"Groq request timed out: {error}") from error
    except Exception as error:
        raise LLMError(
            f"Unexpected Groq error: {type(error).__name__}: {error}"
        ) from error
