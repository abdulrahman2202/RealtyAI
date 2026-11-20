"""Readiness fails closed for missing deployment data without initializing storage."""

import logging

import pytest
from chromadb.errors import ChromaError
from fastapi.testclient import TestClient

from backend import deployment
from backend.embedding import cached_profile
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


def test_chroma_readiness_error_logs_safe_initialization_stage(monkeypatch, caplog):
    def unavailable():
        raise ChromaError("do-not-log-database-value https://private.invalid/?secret=value")
    monkeypatch.setattr(deployment, "_resolve_collection", unavailable)
    with caplog.at_level(logging.WARNING, logger="uvicorn.error"):
        response = TestClient(app).get("/ready")
    assert response.status_code == 503
    assert "stage=chroma_initialization" in caplog.text and "exception=ChromaError" in caplog.text
    assert "do-not-log" not in caplog.text and "https://" not in caplog.text


def test_missing_offline_profile_retains_type_stage_and_cache_interface(monkeypatch, tmp_path):
    monkeypatch.setenv("HF_HUB_CACHE", str(tmp_path / "do-not-log-cache-location"))
    cached_profile.cache_clear()
    try:
        with pytest.raises(FileNotFoundError) as caught:
            cached_profile()
        diagnostic = caught.value._realtyai_recovery_diagnostic
        assert diagnostic.stage == "offline_model_profile"
        assert diagnostic.exception_class == "FileNotFoundError"
        assert "do-not-log-cache-location" not in diagnostic.message
    finally:
        cached_profile.cache_clear()
