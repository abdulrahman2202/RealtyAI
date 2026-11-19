"""Automated API tests for RealtyAI.

Mocks the chatbot so no Groq API calls are made during automated testing.
"""

from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)

VALID_QUESTION = "Tell me about Albert Hall Mansions."
MOCK_RESULT = {
    "answer": "Albert Hall Mansions is a luxury property in London.",
    "sources": [
        {
            "title": "Albert Hall Mansions",
            "url": "https://darglobal.co.uk/one-of-one/THE-ALBERT-HALL-MANSION",
        }
    ],
    "success": True,
}


def test_health_endpoint_returns_success():
    """GET /health should return a successful status response."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "RealtyAI"
    assert "version" in data


def test_chat_endpoint_accepts_valid_question():
    """POST /api/chat with a valid question returns 200."""
    with patch("backend.api.routes.chatbot", return_value=MOCK_RESULT):
        response = client.post("/api/chat", json={"question": VALID_QUESTION})
    assert response.status_code == 200


def test_chat_endpoint_returns_answer_and_sources():
    """POST /api/chat returns answer, sources, and success flag."""
    with patch("backend.api.routes.chatbot", return_value=MOCK_RESULT):
        response = client.post("/api/chat", json={"question": VALID_QUESTION})
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data.get("answer")
    assert "sources" in data and isinstance(data["sources"], list)
    assert len(data["sources"]) >= 1
    assert "title" in data["sources"][0]
    assert "url" in data["sources"][0]


def test_chat_endpoint_rejects_empty_question():
    """POST /api/chat with an empty question is rejected."""
    response = client.post("/api/chat", json={"question": ""})
    assert response.status_code in (400, 422)


def test_chat_endpoint_rejects_whitespace_only_question():
    """POST /api/chat with a whitespace-only question is rejected."""
    response = client.post("/api/chat", json={"question": "   "})
    assert response.status_code in (400, 422)


def test_chat_endpoint_handles_chatbot_failure_safely():
    """POST /api/chat handles chatbot failures without exposing internals."""
    with patch(
        "backend.api.routes.chatbot",
        side_effect=RuntimeError("Groq API is down"),
    ):
        response = client.post("/api/chat", json={"question": VALID_QUESTION})
    assert response.status_code == 500
    data = response.json()
    assert "detail" in data
    # Never expose API keys or credentials
    assert "api_key" not in data["detail"].lower()
    assert (
        "groq" not in data["detail"].lower()
        or "unable to connect" in data["detail"].lower()
    )


def test_chat_endpoint_accepts_multi_source_filters():
    with patch("backend.api.routes.chatbot", return_value=MOCK_RESULT) as handler:
        response = client.post("/api/chat", json={"question": "Compare sources", "sources": ["darglobal", "wasalt"], "page_types": ["company"]})
    assert response.status_code == 200
    handler.assert_called_once_with("Compare sources", sources=["darglobal", "wasalt"], page_types=["company"])


def test_chat_endpoint_rejects_unknown_source_filter():
    response = client.post("/api/chat", json={"question": "Information", "sources": ["unrecognized"]})
    assert response.status_code == 422
