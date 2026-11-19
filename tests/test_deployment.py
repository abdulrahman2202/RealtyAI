"""Readiness fails closed for missing deployment data without initializing storage."""

from fastapi.testclient import TestClient

from backend import deployment
from backend.main import app
from backend.rag import RetrievalError


def test_readiness_reports_missing_data_without_creating_storage():
    response = TestClient(app).get("/ready")
    assert response.status_code == 503
    assert response.json()["detail"] == "The approved RAG database or offline model is not ready."


def test_readiness_does_not_expose_internal_configuration_errors(monkeypatch):
    def unavailable():
        raise RetrievalError("private filesystem/configuration detail")
    monkeypatch.setattr(deployment, "_resolve_collection", unavailable)
    response = TestClient(app).get("/ready")
    assert response.status_code == 503
    assert "private" not in response.text
