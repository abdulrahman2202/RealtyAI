"""Make a deterministic archive from a verified quiescent copy, without Chroma."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import shutil
import tarfile
from pathlib import Path

from backend.snapshot import (
    COLLECTION,
    COLLECTION_ID,
    MANIFEST_NAME,
    PROVENANCE,
    REVIEW_SHA256,
    canonical_json,
    database_records,
    digest,
    safe_path,
    validate_manifest,
)

ROOT = Path(__file__).resolve().parents[1]


def file_manifest(directory: Path) -> dict:
    result = {}
    for path in sorted(directory.rglob("*")):
        if path.is_symlink():
            raise ValueError("Linked source files are forbidden.")
        if path.is_file():
            name = safe_path(path.relative_to(directory).as_posix())
            result[name] = {"size": path.stat().st_size, "sha256": digest(path)}
    if any(name.endswith(("-wal", "-shm", "-journal")) for name in result):
        raise ValueError("Checkpoint and close all source writers before copying.")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--source-quiescent", action="store_true", required=True)
    args = parser.parse_args()
    output = args.output_dir.resolve()
    if not output.is_relative_to(ROOT / ".tmp") or output.exists():
        raise ValueError("Choose a fresh output directory under .tmp; existing files are never overwritten.")
    source = ROOT / "data/vector_db_multisource"
    before = file_manifest(source)
    baseline = json.loads((ROOT / "deployment/model-cache/manifest.json").read_text(encoding="utf-8"))
    expected_hashes = {name.replace("\\", "/"): value for name, value in baseline["database_source_hashes"].items()}
    if {name: entry["sha256"] for name, entry in before.items()} != expected_hashes:
        raise ValueError("The source differs from the approved quiescent database baseline.")
    output.mkdir(parents=True)
    clone = output / "quiescent-copy"
    shutil.copytree(source, clone)
    if file_manifest(source) != before or file_manifest(clone) != before:
        raise ValueError("Source changed while copying; this archive cannot be used.")
    review_path = ROOT / "data/import_review/chunk_review.json"
    if digest(review_path) != REVIEW_SHA256:
        raise ValueError("The approved review has changed.")
    review = json.loads(review_path.read_text(encoding="utf-8"))
    reviewed = {row["id"]: {"text_sha256": hashlib.sha256(row["text"].encode()).hexdigest(), "metadata": row["metadata"]}
        for row in review["chunks"]}
    if database_records(clone) != reviewed:
        raise ValueError("The source copy differs from the 84 reviewed chunks.")
    manifest = {"format": "realtyai-chroma-snapshot-v1", "collection_name": COLLECTION, "collection_id": COLLECTION_ID,
        "chroma_version": "1.5.9", "review_sha256": REVIEW_SHA256, "provenance": PROVENANCE,
        "files": before, "records": reviewed}
    manifest_data = canonical_json(manifest) + b"\n"
    validate_manifest(manifest_data)
    temporary = output / "snapshot.tar.gz"
    with (temporary.open("xb") as raw,
            gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as compressed,
            tarfile.open(fileobj=compressed, mode="w", format=tarfile.USTAR_FORMAT) as archive):
        for name, data in [(MANIFEST_NAME, manifest_data), *[(name, (clone / name).read_bytes()) for name in before]]:
            entry = tarfile.TarInfo(name)
            entry.size, entry.mode, entry.mtime = len(data), 0o600, 0
            archive.addfile(entry, io.BytesIO(data))
    archive_hash = digest(temporary)
    archive_path = output / (COLLECTION + "-" + archive_hash + ".tar.gz")
    temporary.rename(archive_path)
    (output / MANIFEST_NAME).write_bytes(manifest_data)
    receipt = {"archive": str(archive_path), "archive_sha256": archive_hash,
        "manifest_sha256": hashlib.sha256(manifest_data).hexdigest(), "archive_bytes": archive_path.stat().st_size,
        "files": len(before), "chunks": 84, "source_counts": {"darglobal": 46, "wasalt": 38}, "documents": 12,
        "collection_id": COLLECTION_ID, "source_unchanged": file_manifest(source) == before,
        "quiescent_copy": str(clone), "no_chroma_open_indexing_or_embeddings": True}
    (output / "archive-receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt))


if __name__ == "__main__":
    main()
