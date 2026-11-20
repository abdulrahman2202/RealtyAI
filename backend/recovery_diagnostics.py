"""Stage diagnostics with fixed summaries: never emit raw exceptions or values."""

from __future__ import annotations

import logging
import ssl
import urllib.error
from contextlib import contextmanager
from dataclasses import dataclass

STAGES = frozenset({"configuration", "snapshot_recovery", "existing_database_validation", "broker_request",
    "broker_response", "ticket_validation", "download_staging", "blob_download", "target_directory",
    "archive_checksum", "filesystem_staging", "archive_header", "manifest_checksum", "manifest_validation",
    "archive_extraction", "database_validation", "filesystem_promotion", "readiness_validation",
    "chroma_initialization", "offline_model_profile", "offline_embedding_model_loading"})
_CLASS_NAMES = frozenset({"AttributeError", "KeyError", "OSError", "PermissionError", "FileNotFoundError",
    "NotADirectoryError", "IsADirectoryError", "FileExistsError", "TimeoutError", "ConnectionError",
    "ConnectionResetError", "ConnectionRefusedError", "RuntimeError", "TypeError", "ValueError", "MemoryError",
    "HTTPError", "URLError", "SSLError", "SSLCertVerificationError", "SSLEOFError", "SSLZeroReturnError",
    "JSONDecodeError", "EOFError", "ReadError",
    "CompressionError", "HeaderError", "BadGzipFile", "TarError", "HTTPException", "IncompleteRead",
    "RemoteDisconnected", "DatabaseError", "OperationalError", "IntegrityError", "ProgrammingError",
    "PackageNotFoundError", "SnapshotError", "RetrievalError", "ChromaError", "InternalError", "NotFoundError",
    "InvalidArgumentError", "InvalidDimensionException", "InvalidCollectionException", "error"})
_CONFIG_KEYS = frozenset({"REALTYAI_VECTOR_DB_DIR", "REALTYAI_SNAPSHOT_ENDPOINT", "REALTYAI_SNAPSHOT_CLIENT_TOKEN",
    "REALTYAI_SNAPSHOT_BLOB_URL", "REALTYAI_SNAPSHOT_SHA256", "REALTYAI_SNAPSHOT_MANIFEST_SHA256"})

# All of these are constant validation messages from the application. Unknown
# exception arguments are withheld, not regex-redacted (which can miss secrets).
_VALIDATION_MESSAGES = {message: message for message in (
    "Unsafe snapshot path.", "Snapshot database is missing.", "Snapshot SQLite integrity failed.",
    "Snapshot collection identity differs.", "Snapshot distance metric differs.",
    "Snapshot model/review provenance differs.", "Snapshot chunk text is invalid.",
    "Snapshot chunk provenance differs.", "Snapshot chunk/source/document counts differ.",
    "Snapshot manifest exceeds its limit.", "Snapshot manifest identity differs.", "Invalid snapshot file.",
    "Invalid snapshot file digest.", "Snapshot file manifest exceeds its limit.", "Snapshot Chroma version differs.",
    "Snapshot reviewed text, metadata or original URLs differ.", "Snapshot storage file is missing.",
    "Snapshot decompression exceeds its limit.", "An existing non-empty database will not be overwritten.",
    "Snapshot archive digest/size differs.", "Snapshot manifest must be the first regular file.",
    "Snapshot manifest digest differs.", "Unexpected, duplicate or linked snapshot file.",
    "Snapshot file size differs.", "Snapshot file digest differs.", "Snapshot storage files are incomplete.",
    "The approved HTTPS Vercel endpoint is required.", "The exact private Blob URL is required.",
    "A valid backend-only recovery credential is required.", "Pinned snapshot digests are required.",
    "A linked database target is not allowed.",
    "The existing database has no approved snapshot manifest; it is preserved.",
    "Snapshot authorization failed.", "Snapshot authorization response exceeds its limit.",
    "The snapshot ticket is expired or differs from the approved target.",
    "Snapshot ticket expiration is invalid.", "Snapshot ticket archive digest differs.",
    "Snapshot ticket collection identity differs.", "Snapshot ticket URL differs from the approved target.",
    "Snapshot download failed or exceeds its limit.", "Snapshot download exceeds its size/time limit.",
    "The approved collection is not available.", "The configured collection UUID does not match the approved target.",
    "The approved 84 chunks are not available.", "The approved cosine collection configuration is not available.",
    "The approved source counts are not available.", "The approved source documents are not available.",
    "The approved offline embedding model is not available.", "The offline model cache is incomplete.",
    "The configured source collection has not been indexed.", "The configured source collection is missing.",
    "The configured collection has incompatible embedding provenance.",
)}


@dataclass(frozen=True)
class RecoveryDiagnostic:
    stage: str
    exception_class: str
    message: str
    http_status: int | None = None
    errno: int | None = None
    configuration_key: str | None = None


def describe_failure(error: Exception, stage: str) -> RecoveryDiagnostic:
    existing = getattr(error, "_realtyai_recovery_diagnostic", None)
    if isinstance(existing, RecoveryDiagnostic):
        return existing
    name = type(error).__name__
    name = name if name in _CLASS_NAMES else "Exception"
    message, status, error_number, key = "Failure details withheld to protect secrets.", None, None, None
    if isinstance(error, urllib.error.HTTPError):
        status = error.code if type(error.code) is int and 100 <= error.code <= 599 else None
        message = "Remote HTTP request was rejected."
    elif isinstance(error, ssl.SSLCertVerificationError) or (
            isinstance(error, urllib.error.URLError) and isinstance(error.reason, ssl.SSLCertVerificationError)):
        message = "TLS certificate verification failed."
    elif isinstance(error, ssl.SSLError) or (
            isinstance(error, urllib.error.URLError) and isinstance(error.reason, ssl.SSLError)):
        message = "TLS connection failed."
    elif isinstance(error, urllib.error.URLError):
        message = "Remote connection failed."
    elif isinstance(error, PermissionError):
        message = "Filesystem permission was denied."
    elif isinstance(error, FileNotFoundError):
        message = "A required recovery or offline model file is missing."
    elif isinstance(error, TimeoutError):
        message = "The operation timed out."
    elif isinstance(error, OSError):
        message = "Filesystem or network operation failed."
    elif isinstance(error, KeyError):
        message = "A required configuration or data field is missing."
        if error.args and isinstance(error.args[0], str) and error.args[0] in _CONFIG_KEYS:
            key = error.args[0]  # approved variable name only; never its value
    elif name == "JSONDecodeError":
        message = "Response or manifest is not valid JSON."
    elif name in {"DatabaseError", "OperationalError", "IntegrityError", "ProgrammingError"}:
        message = "SQLite validation failed."
    elif name in {"ReadError", "CompressionError", "HeaderError", "BadGzipFile", "TarError", "EOFError", "error"}:
        message = "Archive data could not be decoded."
    elif name in {"HTTPException", "IncompleteRead", "RemoteDisconnected"}:
        message = "HTTP response was interrupted or invalid."
    elif name in {"SnapshotError", "RetrievalError"}:
        argument = error.args[0] if error.args and isinstance(error.args[0], str) else None
        message = _VALIDATION_MESSAGES.get(argument, "Recovery validation failed; details withheld.")
    elif name in {"ChromaError", "InternalError", "NotFoundError", "InvalidArgumentError", "InvalidDimensionException", "InvalidCollectionException"}:
        message = "Chroma initialization or validation failed."
    elif isinstance(error, (RuntimeError, TypeError, ValueError, AttributeError, MemoryError)):
        message = "Recovery or model operation failed; details withheld."
    if isinstance(error, OSError) and type(error.errno) is int and 0 < error.errno < 256:
        error_number = error.errno
    return RecoveryDiagnostic(stage if stage in STAGES else "snapshot_recovery", name, message, status, error_number, key)


@contextmanager
def diagnostic_stage(stage: str):
    """Annotate the original exception at its deepest stage, then re-raise it."""
    try:
        yield
    except Exception as error:
        error._realtyai_recovery_diagnostic = describe_failure(error, stage)
        raise


def preserve_diagnostic(original: Exception, replacement: Exception, stage: str = "configuration") -> None:
    replacement._realtyai_recovery_diagnostic = describe_failure(original, stage)


def log_recovery_failure(error: Exception, *, stage: str = "snapshot_recovery", readiness: bool = False) -> None:
    diagnostic = describe_failure(error, stage)
    prefix = "Chroma readiness failed." if readiness else "Chroma snapshot recovery failed; readiness is unavailable."
    logging.getLogger("uvicorn.error").warning(
        "%s stage=%s exception=%s message=%s http_status=%s errno=%s configuration_key=%s",
        prefix, diagnostic.stage, diagnostic.exception_class, diagnostic.message,
        diagnostic.http_status, diagnostic.errno, diagnostic.configuration_key,
    )
