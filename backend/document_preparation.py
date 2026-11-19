"""Pure, shared preparation of nested source records into reproducible text chunks."""

from __future__ import annotations

import json
import re
from bisect import bisect_right
from dataclasses import dataclass
from hashlib import sha256

from backend.data_access import (
    DEFAULT_POLICY,
    SEARCHABLE_PAGE_TYPES,
    SourcePolicy,
    canonical_url,
    document_id,
    validate_record,
)
from backend.embedding import EmbeddingProfile, cached_profile
from backend.models import ExtractedRecord

PREPARATION_VERSION = "6.11.1"
HEADINGS = frozenset({
    "amenities", "facilities", "features", "specifications", "property specifications",
    "location", "floor plans", "description", "photo gallery", "why invest",
    "frequently asked questions", "faq", "faqs", "other projects", "register your interest",
    "albert hall mansions history", "a prestigious address", "our offices", "division contacts",
    "price", "pricing", "handover", "handover date", "property details",
    "المواصفات", "المميزات", "الموقع", "الأسئلة الشائعة", "السعر",
})
NOISE_HEADINGS = frozenset({"other projects", "register your interest", "photo gallery"})


class PreparationConflict(ValueError):
    """One canonical source was supplied with conflicting document contents."""


@dataclass(frozen=True)
class PreparedChunk:
    id: str
    text: str
    body: str
    metadata: dict
    token_count: int
    body_token_count: int

    def to_dict(self) -> dict:
        return {
            "id": self.id, "text": self.text, "body": self.body,
            "metadata": dict(self.metadata), "token_count": self.token_count,
            "body_token_count": self.body_token_count,
        }


def content_fingerprint(record: ExtractedRecord) -> str:
    payload = {name: record.data.get(name, "") for name in ("title", "page_type", "description", "content")}
    return sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def _heading(line: str) -> bool:
    value = line.strip()
    return value.casefold() in HEADINGS or (
        value.isupper() and 2 <= len(value) <= 90 and len(value.split()) <= 12
    )


def split_sections(content: str) -> list[tuple[str, str]]:
    """Keep source wording and paragraph/specification/FAQ blocks in their own sections."""
    sections = []
    section = "Content"
    lines = []
    for line in content.splitlines():
        if _heading(line):
            if any(item.strip() for item in lines):
                sections.append((section, "\n".join(lines).strip()))
            section = line.strip()
            lines = []
        else:
            lines.append(line)
    if any(item.strip() for item in lines):
        sections.append((section, "\n".join(lines).strip()))
    return sections


def _short_prefix(text: str, limit: int, profile: EmbeddingProfile) -> str:
    tokens = profile.tokenizer.encode(text, add_special_tokens=False, truncation=False, verbose=False)
    if len(tokens) <= limit:
        return text
    return profile.tokenizer.decode(tokens[:limit], skip_special_tokens=True)


def _windows(body: str, prefix: str, profile: EmbeddingProfile, target: int, overlap: int):
    encoded = profile.tokenizer(body, add_special_tokens=False, return_offsets_mapping=True, truncation=False, verbose=False)
    offsets = encoded["offset_mapping"]
    ends = [end for _, end in offsets]
    start = 0
    budget = min(target, profile.max_sequence_length - profile.count(prefix))
    if budget <= overlap:
        raise ValueError("The chunk prefix leaves too little space for useful body text.")
    while start < len(offsets):
        end = min(len(offsets), start + budget)
        first = offsets[start][0]
        last = offsets[end - 1][1]
        # Prefer a nearby sentence or paragraph boundary while maintaining progress.
        if end < len(offsets):
            boundaries = list(re.finditer(r"[.!?](?:\s|$)|\n\s*\n", body[first:last]))
            if boundaries:
                boundary = first + boundaries[-1].end()
                candidate = bisect_right(ends, boundary)
                if max(start + overlap + 1, end - 30) <= candidate < end:
                    end = candidate
                    last = offsets[end - 1][1]
        text = body[first:last].strip()
        while end > start + 1 and profile.count(prefix + text) > profile.max_sequence_length:
            end -= 1
            last = offsets[end - 1][1]
            text = body[first:last].strip()
        if profile.count(prefix + text) > profile.max_sequence_length:
            raise ValueError("A source span cannot fit the encoder's token limit.")
        yield text
        if end == len(offsets):
            break
        next_start = max(start + 1, end - overlap)
        # Keep a WordPiece continuation with the rest of its word when possible.
        while next_start > start + 1 and offsets[next_start - 1][1] == offsets[next_start][0]:
            next_start -= 1
        start = next_start


def prepare_record(
    payload: ExtractedRecord | dict, *, profile: EmbeddingProfile | None = None,
    policy: SourcePolicy = DEFAULT_POLICY, body_tokens: int = 200, overlap_tokens: int = 32,
) -> list[PreparedChunk]:
    record = validate_record(payload, policy)
    if record.data["page_type"] not in SEARCHABLE_PAGE_TYPES:
        return []
    if not 180 <= body_tokens <= 210 or not 25 <= overlap_tokens <= 40:
        raise ValueError("Use 180–210 body tokens and 25–40 overlap tokens.")
    profile = profile or cached_profile()
    identity = document_id(record.source, record.url)
    fingerprint = content_fingerprint(record)
    sections = split_sections(record.data["content"])
    description = record.data["description"].strip()
    collapsed_content = " ".join(record.data["content"].split())
    if description and " ".join(description.split()) not in collapsed_content:
        sections.insert(0, ("Description", description))
    if not sections and description:
        sections = [("Description", description)]
    chunks = []
    for section, body in sections:
        if section.casefold() in NOISE_HEADINGS:
            continue
        body = "\n".join(line for line in body.splitlines() if line.strip() not in {".", "•"}).strip()
        if not body:
            continue
        title_prefix = _short_prefix(record.data["title"], 48, profile)
        section_prefix = _short_prefix(section, 24, profile)
        prefix = f"Title: {title_prefix}\nSection: {section_prefix}\n\n"
        for window in _windows(body, prefix, profile, body_tokens, overlap_tokens):
            text = prefix + window
            index = len(chunks)
            chunk_identity = f"{identity}:{fingerprint}:{PREPARATION_VERSION}:{profile.model}:{profile.revision}:{index}"
            metadata = {
                "source": record.source, "url": record.url, "canonical_url": canonical_url(record.url),
                "title": record.data["title"], "page_type": record.data["page_type"],
                "document_id": identity, "chunk_index": index, "section": section,
                "extracted_at": record.extracted_at.isoformat(),
                "timestamp_origin": record.data.get("timestamp_origin", "provided"),
                "content_fingerprint": fingerprint,
                "chunk_fingerprint": sha256(text.encode("utf-8")).hexdigest(),
                "preparation_version": PREPARATION_VERSION,
                "data_origin": record.data.get("data_origin", "review"),
                **profile.provenance(),
            }
            chunks.append(PreparedChunk(
                sha256(chunk_identity.encode("utf-8")).hexdigest(), text, window, metadata,
                profile.count(text), len(profile.tokenizer.encode(window, add_special_tokens=False, verbose=False)),
            ))
    return chunks


def prepare_documents(
    records: list[ExtractedRecord | dict], *, profile: EmbeddingProfile | None = None,
    policy: SourcePolicy = DEFAULT_POLICY,
) -> list[PreparedChunk]:
    seen = {}
    chunks = []
    for payload in records:
        record = validate_record(payload, policy)
        identity = document_id(record.source, record.url)
        fingerprint = content_fingerprint(record)
        if identity in seen:
            if seen[identity] != fingerprint:
                raise PreparationConflict("Conflicting contents for one canonical source URL.")
            continue
        seen[identity] = fingerprint
        chunks.extend(prepare_record(record, profile=profile, policy=policy))
    return chunks
