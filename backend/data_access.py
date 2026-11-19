"""Shared source identity and validation for the two user-authorized datasets."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

from backend.models import ExtractedRecord

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ALIASES = {
    "darglobal": ("darglobal", "darglobal.co.uk", "www.darglobal.co.uk", "darglobal.com"),
    "wasalt": ("wasalt", "wasalt.sa", "www.wasalt.sa", "auction.wasalt.sa", "wasalt.com", "www.wasalt.com"),
}
SEARCHABLE_PAGE_TYPES = frozenset({"company", "project_directory", "individual_property", "auction"})
PAGE_TYPES = SEARCHABLE_PAGE_TYPES | {"unknown", "empty", "legal_reference"}


class DataAccessError(PermissionError):
    """An input violates source identity or declared data-origin boundaries."""


def normalize_source(source: str) -> str:
    if not isinstance(source, str):
        raise TypeError("Source identity must be text.")
    value = source.strip().casefold()
    for name, aliases in SOURCE_ALIASES.items():
        if value in aliases:
            return name
    raise ValueError(f"Unsupported source: {source}")


def canonical_url(url: str) -> str:
    """Preserve the approved URL identity policy; never replace the citation URL."""
    parsed = urlparse(url)
    query = {key: values for key, values in parse_qs(parsed.query).items() if not key.startswith("utm_")}
    suffix = urlencode(sorted(query.items()), doseq=True)
    base = f"{parsed.scheme}://{parsed.netloc}{parsed.path.lower()}"
    return f"{base}?{suffix}" if suffix else base


def document_id(source: str, url: str) -> str:
    identity = f"{normalize_source(source)}\n{canonical_url(url)}"
    return sha256(identity.encode("utf-8")).hexdigest()


def is_synthetic_url(url: str) -> bool:
    host = (urlparse(url).hostname or "").casefold()
    return host.endswith((".example", ".test", ".invalid")) or host in {"localhost", "example.test"}


@dataclass(frozen=True)
class SourcePolicy:
    allow_synthetic: bool = False
    authorization_reference: str = "User confirmed permission from DarGlobal and Wasalt in Phase 6.11 (2026-11-19)."

    def require_origin(self, source: str, origin: str) -> None:
        normalize_source(source)
        if origin not in {"raw", "review", "synthetic", "authorized_fixture", "legacy"}:
            raise DataAccessError("Unknown data origin.")
        if origin == "synthetic" and not self.allow_synthetic:
            raise DataAccessError("Synthetic fixtures must be explicitly enabled.")

    def require_path(self, source: str, path: Path, origin: str) -> None:
        self.require_origin(source, origin)
        resolved = path.resolve()
        for name in SOURCE_ALIASES:
            raw_root = (PROJECT_ROOT / "data" / "raw" / name).resolve()
            if resolved.is_relative_to(raw_root) and (normalize_source(source) != name or origin == "synthetic"):
                raise DataAccessError("Raw source paths cannot be relabeled as another source or synthetic fixtures.")

    def require_url(self, source: str, url: str, origin: str = "legacy") -> None:
        source = normalize_source(source)
        self.require_origin(source, origin)
        if not isinstance(url, str) or any(character.isspace() for character in url):
            raise ValueError("Source URLs must be text without whitespace.")
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("An original HTTP(S) source URL without embedded credentials is required.")
        if parsed.port is not None and not 1 <= parsed.port <= 65535:
            raise ValueError("Invalid source URL port.")
        if origin == "synthetic":
            if not is_synthetic_url(url):
                raise DataAccessError("Synthetic fixture URLs must use reserved example/test domains.")
        elif (parsed.hostname or "").casefold() not in SOURCE_ALIASES[source]:
            raise ValueError("The URL host does not match the declared source.")

    def require_record(self, record: ExtractedRecord) -> None:
        source = normalize_source(record.source)
        origin = record.data.get("data_origin", "review" if source == "darglobal" else "raw")
        self.require_url(source, record.url, origin)

    def source_branches(self, sources: list[str] | None = None) -> list[dict]:
        requested = list(dict.fromkeys(normalize_source(source) for source in (sources or SOURCE_ALIASES)))
        branches = []
        for source in requested:
            clause = {"source": {"$in": list(SOURCE_ALIASES[source])}}
            branches.append(clause)
        return branches


DEFAULT_POLICY = SourcePolicy()


def validate_record(record: ExtractedRecord | dict, policy: SourcePolicy = DEFAULT_POLICY) -> ExtractedRecord:
    if isinstance(record, dict):
        extra = set(record) - {"source", "url", "data", "extracted_at"}
        if extra:
            raise ValueError(f"Unsupported ExtractedRecord fields: {sorted(extra)}")
        if not isinstance(record.get("data"), dict):
            raise TypeError("ExtractedRecord.data must be a dictionary.")
        policy.require_origin(normalize_source(record.get("source", "")), record["data"].get("data_origin", "review"))
        record = ExtractedRecord.model_validate(record)
    policy.require_record(record)
    if record.extracted_at.utcoffset() is None:
        raise ValueError("Extraction timestamps must include a timezone.")
    data = dict(record.data)
    if not isinstance(data.get("title"), str):
        raise TypeError("The extracted title must be text.")
    if not data["title"].strip():
        raise ValueError("A non-empty extracted title is required.")
    if data.get("page_type") not in PAGE_TYPES:
        raise ValueError("A recognized page_type is required.")
    for name in ("description", "content"):
        value = data.get(name)
        if value is not None and not isinstance(value, str):
            raise TypeError(f"{name} must be extracted text.")
        data[name] = value or ""
    if not data["content"].strip() and not data["description"].strip():
        raise ValueError("Empty records cannot enter document preparation.")
    return record.model_copy(update={"source": normalize_source(record.source), "data": data})
