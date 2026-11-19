"""Exercise recovery against the actual approved archive and adversarial inputs."""

from __future__ import annotations

import io
import json
import sqlite3
import subprocess
import sys
import tarfile
import urllib.error
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend import main, snapshot

ROOT = Path(__file__).resolve().parents[1]
TOKEN = "fixture_only_credential_12345678901234567890"
ENDPOINT = "https://snapshot-test.vercel.app/api/internal/chroma-snapshot"
BLOB = "https://fixture.private.blob.vercel-storage.com/snapshot.tar.gz"


@pytest.fixture(scope="session")
def approved_archive(tmp_path_factory):
    output = tmp_path_factory.mktemp("approved") / "archive"
    result = subprocess.run([sys.executable, "-B", "-m", "scripts.prepare_chroma_snapshot",
        "--output-dir", str(output), "--source-quiescent"], cwd=ROOT, capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


@pytest.fixture
def config(approved_archive, tmp_path):
    return snapshot.RecoveryConfig(tmp_path / "chroma", ENDPOINT, TOKEN, BLOB,
        approved_archive["archive_sha256"], approved_archive["manifest_sha256"])


class Response(io.BytesIO):
    status = 200

    def __init__(self, body):
        super().__init__(body)
        self.headers = {"Content-Length": str(len(body))}


class Opener:
    def __init__(self, archive, config, *, expired=False, corrupt=False):
        self.archive = archive
        self.calls = []
        self.ticket = {"url": BLOB + "?vercel-blob-signature=fixture",
            "sha256": config.archive_hash, "collection_id": snapshot.COLLECTION_ID,
            "expires_at": (datetime.now(UTC) + timedelta(seconds=-1 if expired else 300)).isoformat()}
        self.corrupt = corrupt

    def open(self, request, **kwargs):
        self.calls.append(request)
        if len(self.calls) == 1:
            return Response(json.dumps(self.ticket).encode())
        return Response(b"interrupted" if self.corrupt else Path(self.archive).read_bytes())


def test_actual_archive_restores_all_84_reviewed_chunks(config, approved_archive):
    opener = Opener(approved_archive["archive"], config)
    assert snapshot.recover(config, opener=opener)["chunks"] == 84
    manifest = snapshot.validate_manifest((config.target / snapshot.MANIFEST_NAME).read_bytes())
    assert snapshot.database_records(config.target) == manifest["records"]
    for name, expected in manifest["files"].items():
        assert snapshot.digest(config.target / name) == expected["sha256"]
    assert opener.calls[0].get_header("Authorization") == "Bearer " + TOKEN
    assert opener.calls[1].get_header("Authorization") is None
    assert snapshot.recover(config, opener=opener)["status"] == "existing_verified"
    assert len(opener.calls) == 2


@pytest.mark.parametrize("field", ["archive_hash", "manifest_hash"])
def test_wrong_hash_never_promotes_database(config, approved_archive, field):
    invalid = replace(config, **{field: "0" * 64})
    with pytest.raises(snapshot.SnapshotError):
        snapshot.restore_archive(Path(approved_archive["archive"]), invalid.target, invalid.archive_hash, invalid.manifest_hash)
    assert not config.target.exists()


def test_nonempty_database_is_preserved_without_network(config, approved_archive):
    config.target.mkdir()
    sentinel = config.target / "existing-data"
    sentinel.write_bytes(b"preserve exactly")
    opener = Opener(approved_archive["archive"], config)
    with pytest.raises(snapshot.SnapshotError):
        snapshot.recover(config, opener=opener)
    assert sentinel.read_bytes() == b"preserve exactly" and not opener.calls


@pytest.mark.parametrize("attack", ["expired", "wrong_url", "wrong_id", "interrupted"])
def test_invalid_ticket_or_partial_download_fails_closed(config, approved_archive, attack):
    opener = Opener(approved_archive["archive"], config, expired=attack == "expired", corrupt=attack == "interrupted")
    if attack == "wrong_url":
        opener.ticket["url"] = "https://attacker.invalid/private?secret=fixture"
    if attack == "wrong_id":
        opener.ticket["collection_id"] = "other-collection"
    with pytest.raises(snapshot.SnapshotError):
        snapshot.recover(config, opener=opener)
    assert not config.target.exists()


@pytest.mark.parametrize("name,typeflag", [("../outside", tarfile.REGTYPE), ("/absolute", tarfile.REGTYPE),
    ("C:/outside", tarfile.REGTYPE), ("chroma.sqlite3", tarfile.SYMTYPE), ("chroma.sqlite3", tarfile.LNKTYPE),
    (snapshot.MANIFEST_NAME, tarfile.REGTYPE)])
def test_unsafe_or_duplicate_archive_members_are_rejected(config, approved_archive, tmp_path, name, typeflag):
    archive = tmp_path / "malicious.tar.gz"
    manifest = Path(approved_archive["archive"]).parent / snapshot.MANIFEST_NAME
    with tarfile.open(archive, "w:gz") as output:
        first = tarfile.TarInfo(snapshot.MANIFEST_NAME)
        data = manifest.read_bytes()
        first.size = len(data)
        output.addfile(first, io.BytesIO(data))
        entry = tarfile.TarInfo(name)
        entry.type, entry.linkname = typeflag, "outside" if typeflag != tarfile.REGTYPE else ""
        output.addfile(entry, io.BytesIO(b""))
    with pytest.raises(snapshot.SnapshotError):
        snapshot.restore_archive(archive, config.target, snapshot.digest(archive), config.manifest_hash)
    assert not config.target.exists() and not (tmp_path / "outside").exists()


def test_oversized_archive_is_rejected_before_reading(config, tmp_path):
    archive = tmp_path / "oversized.tar.gz"
    with archive.open("wb") as output:
        output.truncate(snapshot.MAX_DOWNLOAD + 1)
    with pytest.raises(snapshot.SnapshotError):
        snapshot.restore_archive(archive, config.target, config.archive_hash, config.manifest_hash)
    assert not config.target.exists()


@pytest.mark.parametrize("endpoint", ["http://snapshot-test.vercel.app/api/internal/chroma-snapshot",
    "https://evil.invalid/api/internal/chroma-snapshot", ENDPOINT + "?path=other"])
def test_only_configured_https_provider_endpoint_is_accepted(config, endpoint):
    with pytest.raises(snapshot.SnapshotError):
        replace(config, endpoint=endpoint).validate()


def test_http_redirects_are_not_followed():
    assert snapshot._NoRedirect().redirect_request(None, None, 302, None, None, "https://evil.invalid") is None


def test_recovery_failure_serves_503_without_secrets_or_chat(monkeypatch):
    monkeypatch.setenv("REALTYAI_SNAPSHOT_ENDPOINT", ENDPOINT)
    def fail():
        raise snapshot.SnapshotError("fixture-private-detail")
    monkeypatch.setattr(main, "recover_from_environment", fail)
    with TestClient(main.app) as client:
        assert client.get("/health").status_code == 200
        for response in [client.get("/ready"), client.post("/api/chat", json={"question": "What services does Wasalt provide?"})]:
            assert response.status_code == 503
            assert "fixture-private-detail" not in response.text and TOKEN not in response.text


def test_expired_provider_credential_error_is_sanitized(monkeypatch, config):
    monkeypatch.setenv("REALTYAI_SNAPSHOT_ENDPOINT", ENDPOINT)
    def fail(_config):
        raise urllib.error.HTTPError("private-signed-url", 403, "private-token", {}, None)
    monkeypatch.setattr(snapshot, "recover", fail)
    for name, value in {"REALTYAI_VECTOR_DB_DIR": str(config.target), "REALTYAI_SNAPSHOT_CLIENT_TOKEN": TOKEN,
            "REALTYAI_SNAPSHOT_BLOB_URL": BLOB, "REALTYAI_SNAPSHOT_SHA256": config.archive_hash,
            "REALTYAI_SNAPSHOT_MANIFEST_SHA256": config.manifest_hash}.items():
        monkeypatch.setenv(name, value)
    with pytest.raises(snapshot.SnapshotError, match="Approved snapshot recovery failed") as caught:
        snapshot.recover_from_environment()
    assert "private-token" not in str(caught.value) and "private-signed-url" not in str(caught.value)


def test_actual_network_interruption_does_not_promote(config, approved_archive):
    class Interrupted(Response):
        def read(self, size=-1):
            if self.tell():
                raise OSError("fixture connection interrupted")
            return super().read(size)
    class InterruptingOpener(Opener):
        def open(self, request, **kwargs):
            if self.calls:
                return Interrupted(Path(self.archive).read_bytes())
            return super().open(request, **kwargs)
    with pytest.raises(OSError, match="interrupted"):
        snapshot.recover(config, opener=InterruptingOpener(approved_archive["archive"], config))
    assert not config.target.exists()


@pytest.mark.parametrize("kind", ["url", "provenance", "null-text"])
def test_existing_metadata_and_provenance_tampering_is_detected(config, approved_archive, kind):
    snapshot.recover(config, opener=Opener(approved_archive["archive"], config))
    with sqlite3.connect(config.target / "chroma.sqlite3") as connection:
        if kind == "url":
            connection.execute("UPDATE embedding_metadata SET string_value='https://incorrect.invalid' WHERE key='url'")
        elif kind == "provenance":
            connection.execute("UPDATE collection_metadata SET str_value='wrong-revision' WHERE key='embedding_revision'")
        else:
            connection.execute("UPDATE embedding_metadata SET string_value=NULL WHERE key='chroma:document'")
    with pytest.raises(snapshot.SnapshotError):
        snapshot.recover(config, opener=Opener(approved_archive["archive"], config))
