from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, status

from backend.chatbot import chatbot
from backend.llm import (
    LLMConfigError,
    LLMConnectionError,
    LLMError,
    LLMRateLimitError,
    LLMTimeoutError,
)
from backend.rag import RetrievalError
from backend.schemas import ChatRequest, ChatResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/chat",
    response_model=ChatResponse,
    status_code=status.HTTP_200_OK,
    summary="Ask a property-related question",
    description=(
        "Submit a property-related question. The AI agent retrieves relevant "
        "property context from the local RAG database and generates an answer "
        "using Groq. Returns the answer plus source references."
    ),
)
async def chat(request: ChatRequest) -> ChatResponse:
    """Handle a chat request."""
    question = (request.question or "").strip()
    if not question:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Question must not be empty",
        )

    try:
        filters = {name: getattr(request, name) for name in ("sources", "page_types", "document_id", "property_name") if getattr(request, name) is not None}
        result = chatbot(question, **filters)
    except RetrievalError:
        logger.exception("Source retrieval is unavailable")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Source retrieval is temporarily unavailable. Please check the configured collection and local model.",
        ) from None
    except LLMRateLimitError as exc:
        logger.warning("Groq rate limit exceeded: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Groq API rate limit exceeded. Please try again later.",
        )
    except LLMConnectionError as exc:
        logger.warning("Groq connection error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unable to connect to the Groq API.",
        )
    except LLMTimeoutError as exc:
        logger.warning("Groq request timed out: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="The Groq API request timed out.",
        )
    except LLMConfigError as exc:
        logger.error("Groq configuration error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="LLM configuration is missing or invalid.",
        )
    except LLMError as exc:
        logger.error("Groq API error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Groq API error.",
        )
    except Exception:
        logger.exception("Unexpected error in chat endpoint")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error.",
        )

    return ChatResponse(
        answer=result.get("answer", ""),
        sources=result.get("sources", []),
        success=True,
    )
