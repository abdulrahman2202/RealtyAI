from __future__ import annotations

from pydantic import BaseModel, Field


class Source(BaseModel):
    """A retrieved property source reference."""

    title: str = Field(description="Property title")
    url: str = Field(description="Canonical source URL")


class ChatRequest(BaseModel):
    """Request body for the chat endpoint."""

    question: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Property-related question to ask the AI agent",
        examples=["Tell me about Albert Hall Mansions."],
    )


class ChatResponse(BaseModel):
    """Response body for the chat endpoint."""

    answer: str = Field(description="Generated answer from the AI agent")
    sources: list[Source] = Field(description="Source property references")
    success: bool = Field(default=True, description="Whether the request succeeded")


class HealthResponse(BaseModel):
    """Response body for the health endpoint."""

    status: str = Field(description="Application status")
    service: str = Field(description="Service name")
    version: str = Field(description="API version")


class ErrorResponse(BaseModel):
    """Standard error response body."""

    error: str = Field(description="Human-readable error message")
    status_code: int = Field(description="HTTP status code")
