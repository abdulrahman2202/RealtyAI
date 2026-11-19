"""Complete-chunk context budgets, property separation, and original-source citations."""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from urllib.parse import urlparse

from backend.data_access import document_id, normalize_source
from backend.embedding import EmbeddingProfile, cached_profile
from backend.retrieval import evidence_topics, requested_topics


@dataclass(frozen=True)
class ContextBundle:
    text: str
    records: list[dict]
    sources: list[dict]
    token_count: int
    byte_count: int


def extract_sources(records: list[dict]) -> list[dict]:
    seen = set()
    sources = []
    for record in records:
        metadata = record.get("metadata") or {}
        if not metadata.get("url") or not metadata.get("title"):
            continue
        source = normalize_source(metadata.get("source") or urlparse(metadata["url"]).hostname or "")
        identity = metadata.get("document_id") or document_id(source, metadata["url"])
        if identity in seen:
            continue
        seen.add(identity)
        sources.append({"title": metadata["title"], "url": metadata["url"], "source": source,
            "page_type": metadata.get("page_type", "unknown"), "document_id": identity})
    return sources


def _render(records: list[dict], query: str) -> str:
    grouped = OrderedDict()
    for record in records:
        metadata = record.get("metadata") or {}
        identity = metadata.get("document_id") or document_id(metadata.get("source", "darglobal"), metadata["url"])
        grouped.setdefault(identity, []).append(record)
    blocks = []
    citation = 0
    wanted = requested_topics(query)
    for identity, values in grouped.items():
        metadata = values[0]["metadata"]
        lines = [
            f"Property/document identity: {identity}", f"Title: {metadata['title']}",
            f"Source: {metadata['source']}", f"Page type: {metadata.get('page_type', 'unknown')}",
            f"Original URL: {metadata['url']}",
        ]
        available = set().union(*(evidence_topics(record) for record in values))
        if wanted - available:
            lines.append("Requested information unavailable in this source: " + ", ".join(sorted(wanted - available)))
        for record in values:
            citation += 1
            lines.extend([
                f"Evidence [{citation}], section: {record['metadata'].get('section', 'Content')}",
                f"Extraction/import timestamp ({record['metadata'].get('timestamp_origin', 'not supplied')}): {record['metadata'].get('extracted_at', 'not supplied')}",
                record.get("body") or record.get("document") or "",
            ])
        blocks.append("\n".join(lines))
    return "\n\n--- SEPARATE SOURCE DOCUMENT ---\n\n".join(blocks)


def build_context(
    records: list[dict], *, query: str = "", profile: EmbeddingProfile | None = None,
    max_tokens: int = 1500, max_bytes: int = 6000,
) -> ContextBundle:
    if max_tokens <= 0 or max_bytes <= 0:
        raise ValueError("Context token and byte budgets must be positive.")
    if not records:
        return ContextBundle("", [], [], 0, 0)
    profile = profile or cached_profile()
    selected = []
    for record in records:
        if not (record.get("metadata") or {}).get("url") or not (record.get("metadata") or {}).get("title") or not (record.get("body") or record.get("document")):
            continue
        metadata = dict(record["metadata"])
        try:
            metadata["source"] = normalize_source(metadata.get("source") or urlparse(metadata["url"]).hostname or "")
        except ValueError:
            continue
        metadata.setdefault("document_id", document_id(metadata["source"], metadata["url"]))
        record = {**record, "metadata": metadata}
        candidate = _render([*selected, record], query)
        if profile.count(candidate) <= max_tokens and len(candidate.encode("utf-8")) <= max_bytes:
            selected.append(record)
    text = _render(selected, query) if selected else ""
    return ContextBundle(text, selected, extract_sources(selected), profile.count(text) if text else 0, len(text.encode("utf-8")))


def factual_answer(query: str, bundle: ContextBundle) -> str | None:
    """Attribute questions return quoted evidence, avoiding generated or cross-property facts."""
    wanted = requested_topics(query)
    if not wanted:
        return None
    grouped = OrderedDict()
    for record in bundle.records:
        grouped.setdefault(record["metadata"]["document_id"], []).append(record)
    replies = []
    for values in grouped.values():
        metadata = values[0]["metadata"]
        matching = [record for record in values if evidence_topics(record) & wanted]
        available = set().union(*(evidence_topics(record) for record in matching)) if matching else set()
        lines = [f"**{metadata['title']}** ({metadata['source']}):", ""]
        if matching:
            lines.append("Available source evidence:")
            seen_text = set()
            for record in matching:
                body = record.get("body") or record["document"]
                # Quote complete relevant paragraphs; the context still contains every complete chunk.
                for paragraph in body.split("\n\n"):
                    if paragraph not in seen_text and evidence_topics({**record, "body": paragraph}) & wanted:
                        seen_text.add(paragraph)
                        lines.extend(["", paragraph])
        if wanted - available:
            lines.append("Information unavailable in this source: " + ", ".join(sorted(wanted - available)) + ".")
        if not matching:
            descriptive = [record for record in values if record["metadata"].get("section", "").casefold()
                in {"description", "content", "a prestigious address", "albert hall mansions history"}]
            if descriptive:
                lines.append("Other available information:")
                lines.extend(record.get("body") or record["document"] for record in descriptive[:2])
        lines.extend(["", f"Source: {metadata['url']}"])
        replies.append("\n".join(lines))
    return "\n\n".join(replies) if replies else "The requested information is unavailable in the source data."


def evidence_answer(bundle: ContextBundle) -> str:
    """A useful, verbatim fallback when a generated answer cannot be supported."""
    grouped = OrderedDict()
    for record in bundle.records:
        grouped.setdefault(record["metadata"]["document_id"], []).append(record)
    paragraphs = []
    for records in grouped.values():
        metadata = records[0]["metadata"]
        lines = [f"**{metadata['title']}** ({metadata['source']})", ""]
        seen = set()
        for record in records:
            body = record.get("body") or record["document"]
            if body not in seen:
                seen.add(body)
                lines.append(body)
                lines.append("")
        lines.append(f"Source: {metadata['url']}")
        paragraphs.append("\n".join(lines))
    return "\n\n".join(paragraphs)
