"""Bounded recovery of the approved Chroma snapshot; never indexes or uploads."""

from __future__ import annotations

import gzip
import hashlib
import importlib.metadata
import json
import os
import re
import shutil
import sqlite3
import tarfile
import tempfile
import time
import urllib.request
import zlib
from collections import Counter
from contextlib import closing
from dataclasses import dataclass
from datetime import UTC, datetime
from http.client import HTTPException
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit

COLLECTION = "realtyai_multisource_v1"
COLLECTION_ID = "51cdb05c-3ee9-4b04-b85c-71cbf168ff0d"
REVIEW_SHA256 = "549d281fb310a485d12ad90d81679052ab673926ed164caed8f133a11a67bdc4"
PROVENANCE = {"embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
    "embedding_revision": "1110a243fdf4706b3f48f1d95db1a4f5529b4d41",
    "embedding_dimension": 384, "embedding_max_sequence_length": 256}
MANIFEST_NAME = "snapshot-manifest.json"
MAX_DOWNLOAD = 8 * 1024 * 1024
MAX_UNPACKED = 16 * 1024 * 1024
MAX_MANIFEST = 256 * 1024


class SnapshotError(RuntimeError):
    """A safe, non-secret recovery failure."""


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def safe_path(name: str) -> str:
    path = PurePosixPath(name)
    if (not re.fullmatch(r"[A-Za-z0-9_./-]{1,200}", name) or path.is_absolute()
            or any(part in {".", ".."} for part in name.split("/")) or str(path) != name):
        raise SnapshotError("Unsafe snapshot path.")
    return name


def database_records(directory: Path) -> dict:
    """Inspect SQLite without opening Chroma or replaying/migrating its storage."""
    database = directory / "chroma.sqlite3"
    if database.is_symlink() or not database.is_file():
        raise SnapshotError("Snapshot database is missing.")
    with closing(sqlite3.connect(database.resolve().as_uri() + "?mode=ro&immutable=1", uri=True)) as connection:
        if connection.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
            raise SnapshotError("Snapshot SQLite integrity failed.")
        collections = connection.execute("SELECT id,name,dimension,schema_str FROM collections").fetchall()
        if len(collections) != 1 or collections[0][:3] != (COLLECTION_ID, COLLECTION, 384):
            raise SnapshotError("Snapshot collection identity differs.")
        schema = json.loads(collections[0][3])
        if schema["keys"]["#embedding"]["float_list"]["vector_index"]["config"]["space"] != "cosine":
            raise SnapshotError("Snapshot distance metric differs.")
        metadata = {key: next((v for v in values if v is not None), None)
            for key, *values in connection.execute(
                "SELECT key,str_value,int_value,float_value,bool_value FROM collection_metadata WHERE collection_id=?",
                (COLLECTION_ID,))}
        if any(metadata.get(key) != value for key, value in PROVENANCE.items()) or metadata.get("review_sha256") != REVIEW_SHA256:
            raise SnapshotError("Snapshot model/review provenance differs.")
        records: dict = {}
        query = """SELECT e.embedding_id,m.key,m.string_value,m.int_value,m.float_value,m.bool_value
            FROM embeddings e JOIN embedding_metadata m ON m.id=e.id
            WHERE e.segment_id IN (SELECT id FROM segments WHERE collection=?)"""
        for identity, key, *values in connection.execute(query, (COLLECTION_ID,)):
            records.setdefault(identity, {})[key] = next((v for v in values if v is not None), None)
    result = {}
    for identity, metadata in records.items():
        text = metadata.pop("chroma:document")
        if not isinstance(text, str):
            raise SnapshotError("Snapshot chunk text is invalid.")
        text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        if metadata.get("chunk_fingerprint") != text_hash or any(metadata.get(k) != v for k, v in PROVENANCE.items()):
            raise SnapshotError("Snapshot chunk provenance differs.")
        result[identity] = {"text_sha256": text_hash, "metadata": metadata}
    if (len(result) != 84 or Counter(row["metadata"]["source"] for row in result.values()) != {"darglobal": 46, "wasalt": 38}
            or len({row["metadata"]["document_id"] for row in result.values()}) != 12):
        raise SnapshotError("Snapshot chunk/source/document counts differ.")
    return result


def validate_manifest(data: bytes) -> dict:
    if len(data) > MAX_MANIFEST:
        raise SnapshotError("Snapshot manifest exceeds its limit.")
    manifest = json.loads(data)
    if (manifest["format"] != "realtyai-chroma-snapshot-v1" or manifest["collection_id"] != COLLECTION_ID
            or manifest["collection_name"] != COLLECTION or manifest["chroma_version"] != "1.5.9"
            or manifest["review_sha256"] != REVIEW_SHA256 or manifest["provenance"] != PROVENANCE
            or len(manifest["records"]) != 84 or not 1 <= len(manifest["files"]) <= 32):
        raise SnapshotError("Snapshot manifest identity differs.")
    total = 0
    for name, entry in manifest["files"].items():
        safe_path(name)
        if name == MANIFEST_NAME or type(entry["size"]) is not int or not 0 <= entry["size"] <= MAX_UNPACKED:
            raise SnapshotError("Invalid snapshot file.")
        if not re.fullmatch(r"[a-f0-9]{64}", entry["sha256"]):
            raise SnapshotError("Invalid snapshot file digest.")
        total += entry["size"]
    if "chroma.sqlite3" not in manifest["files"] or total > MAX_UNPACKED:
        raise SnapshotError("Snapshot file manifest exceeds its limit.")
    return manifest


def verify_database(directory: Path, manifest: dict) -> None:
    if importlib.metadata.version("chromadb") != manifest["chroma_version"]:
        raise SnapshotError("Snapshot Chroma version differs.")
    if database_records(directory) != manifest["records"]:
        raise SnapshotError("Snapshot reviewed text, metadata or original URLs differ.")
    for name in manifest["files"]:
        if not (directory / name).is_file() or (directory / name).is_symlink():
            raise SnapshotError("Snapshot storage file is missing.")


class _BoundedReader:
    def __init__(self, stream):
        self.stream = stream
        self.remaining = MAX_UNPACKED + MAX_MANIFEST + 128 * 1024

    def read(self, size: int = -1) -> bytes:
        if size < 0 or size > self.remaining:
            size = self.remaining + 1
        data = self.stream.read(size)
        self.remaining -= len(data)
        if self.remaining < 0:
            raise SnapshotError("Snapshot decompression exceeds its limit.")
        return data


def restore_archive(archive: Path, target: Path, archive_hash: str, manifest_hash: str) -> dict:
    """Stage, fully verify, and promote without overwriting a populated target."""
    if target.is_symlink() or (target.exists() and (not target.is_dir() or any(target.iterdir()))):
        raise SnapshotError("An existing non-empty database will not be overwritten.")
    if archive.stat().st_size > MAX_DOWNLOAD or digest(archive) != archive_hash:
        raise SnapshotError("Snapshot archive digest/size differs.")
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".snapshot-stage-", dir=target.parent) as stage_name:
        stage = Path(stage_name)
        with gzip.open(archive, "rb") as compressed, tarfile.open(fileobj=_BoundedReader(compressed), mode="r|") as members:
            iterator = iter(members)
            first = next(iterator, None)
            if first is None or first.name != MANIFEST_NAME or not first.isfile() or first.size > MAX_MANIFEST:
                raise SnapshotError("Snapshot manifest must be the first regular file.")
            manifest_data = members.extractfile(first).read(MAX_MANIFEST + 1)
            if hashlib.sha256(manifest_data).hexdigest() != manifest_hash:
                raise SnapshotError("Snapshot manifest digest differs.")
            manifest = validate_manifest(manifest_data)
            seen = set()
            for member in iterator:
                name = safe_path(member.name)
                if name in seen or name not in manifest["files"] or not member.isfile() or member.linkname:
                    raise SnapshotError("Unexpected, duplicate or linked snapshot file.")
                expected = manifest["files"][name]
                if member.size != expected["size"]:
                    raise SnapshotError("Snapshot file size differs.")
                destination = stage / name
                destination.parent.mkdir(parents=True, exist_ok=True)
                with members.extractfile(member) as incoming, destination.open("xb") as outgoing:
                    shutil.copyfileobj(incoming, outgoing, length=64 * 1024)
                if destination.stat().st_size != expected["size"] or digest(destination) != expected["sha256"]:
                    raise SnapshotError("Snapshot file digest differs.")
                seen.add(name)
            if seen != set(manifest["files"]):
                raise SnapshotError("Snapshot storage files are incomplete.")
        (stage / MANIFEST_NAME).write_bytes(manifest_data)
        verify_database(stage, manifest)
        if target.exists():
            target.rmdir()  # fails if any concurrent writer populated it
        stage.rename(target)
    return {"status": "recovered", "collection_id": COLLECTION_ID, "chunks": 84}


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


@dataclass(frozen=True)
class RecoveryConfig:
    target: Path
    endpoint: str
    token: str
    blob_url: str
    archive_hash: str
    manifest_hash: str

    def validate(self) -> None:
        endpoint, blob = urlsplit(self.endpoint), urlsplit(self.blob_url)
        if (endpoint.scheme != "https" or not (endpoint.hostname or "").endswith(".vercel.app")
                or endpoint.path != "/api/internal/chroma-snapshot" or endpoint.query or endpoint.fragment
                or endpoint.username or endpoint.password):
            raise SnapshotError("The approved HTTPS Vercel endpoint is required.")
        if (blob.scheme != "https" or not (blob.hostname or "").endswith(".private.blob.vercel-storage.com")
                or blob.query or blob.fragment or blob.username or blob.password):
            raise SnapshotError("The exact private Blob URL is required.")
        safe_path(blob.path.lstrip("/"))
        if not re.fullmatch(r"[A-Za-z0-9_-]{32,128}", self.token):
            raise SnapshotError("A valid backend-only recovery credential is required.")
        if any(not re.fullmatch(r"[a-f0-9]{64}", value) for value in (self.archive_hash, self.manifest_hash)):
            raise SnapshotError("Pinned snapshot digests are required.")


def recover(config: RecoveryConfig, *, opener=None) -> dict:
    config.validate()
    target = config.target
    if target.is_symlink():
        raise SnapshotError("A linked database target is not allowed.")
    if target.exists() and any(target.iterdir()):
        manifest_path = target / MANIFEST_NAME
        if not manifest_path.is_file() or manifest_path.is_symlink() or digest(manifest_path) != config.manifest_hash:
            raise SnapshotError("The existing database has no approved snapshot manifest; it is preserved.")
        verify_database(target, validate_manifest(manifest_path.read_bytes()))
        return {"status": "existing_verified", "collection_id": COLLECTION_ID, "chunks": 84}
    opener = opener or urllib.request.build_opener(_NoRedirect())
    request = urllib.request.Request(config.endpoint, headers={"Authorization": "Bearer " + config.token})
    with opener.open(request, timeout=20) as response:
        if response.status != 200:
            raise SnapshotError("Snapshot authorization failed.")
        body = response.read(8193)
        if len(body) > 8192:
            raise SnapshotError("Snapshot authorization response exceeds its limit.")
        ticket = json.loads(body)
    expiry = datetime.fromisoformat(ticket["expires_at"])
    lifetime = (expiry - datetime.now(UTC)).total_seconds()
    signed = urlsplit(ticket["url"])
    approved = urlsplit(config.blob_url)
    if (not 0 < lifetime <= 600 or ticket["sha256"] != config.archive_hash or ticket["collection_id"] != COLLECTION_ID
            or (signed.scheme, signed.netloc, signed.path) != (approved.scheme, approved.netloc, approved.path)
            or not signed.query or signed.fragment):
        raise SnapshotError("The snapshot ticket is expired or differs from the approved target.")
    with tempfile.TemporaryDirectory(prefix="realtyai-download-") as download_directory:
        archive = Path(download_directory) / "snapshot.tar.gz"
        with opener.open(urllib.request.Request(ticket["url"]), timeout=30) as response, archive.open("xb") as output:
            if response.status != 200 or int(response.headers.get("Content-Length", "0")) > MAX_DOWNLOAD:
                raise SnapshotError("Snapshot download failed or exceeds its limit.")
            total, started = 0, time.monotonic()
            while block := response.read(64 * 1024):
                total += len(block)
                if total > MAX_DOWNLOAD or time.monotonic() - started > 90:
                    raise SnapshotError("Snapshot download exceeds its size/time limit.")
                output.write(block)
        return restore_archive(archive, target, config.archive_hash, config.manifest_hash)


def recover_from_environment() -> dict:
    if not os.getenv("REALTYAI_SNAPSHOT_ENDPOINT"):
        return {"status": "disabled"}
    try:
        return recover(RecoveryConfig(Path(os.environ["REALTYAI_VECTOR_DB_DIR"]),
            os.environ["REALTYAI_SNAPSHOT_ENDPOINT"], os.environ["REALTYAI_SNAPSHOT_CLIENT_TOKEN"],
            os.environ["REALTYAI_SNAPSHOT_BLOB_URL"], os.environ["REALTYAI_SNAPSHOT_SHA256"],
            os.environ["REALTYAI_SNAPSHOT_MANIFEST_SHA256"]))
    except (AttributeError, KeyError, OSError, RuntimeError, ValueError, TypeError, sqlite3.Error, tarfile.TarError,
            EOFError, HTTPException, zlib.error):
        raise SnapshotError("Approved snapshot recovery failed; database preserved and readiness unavailable.") from None
