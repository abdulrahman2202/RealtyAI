"""Copy the approved model cache and a stopped-backend database snapshot without indexing."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
REVISION = "1110a243fdf4706b3f48f1d95db1a4f5529b4d41"
MODEL_FOLDER = "models--sentence-transformers--all-MiniLM-L6-v2"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot-dir", type=Path)
    parser.add_argument("--backend-stopped", action="store_true")
    args = parser.parse_args()
    hub = Path(os.getenv("HF_HUB_CACHE") or os.getenv("HUGGINGFACE_HUB_CACHE") or
        (Path(os.getenv("HF_HOME", str(Path.home() / ".cache/huggingface"))) / "hub"))
    source = hub / MODEL_FOLDER
    if (source / "refs/main").read_text(encoding="utf-8").strip() != REVISION:
        raise ValueError("The local cache is not the approved embedding revision.")
    model_target = ROOT / "deployment/model-cache/hub" / MODEL_FOLDER
    model_files = [source / "refs/main", *(source / "snapshots" / REVISION).rglob("*")]
    copied = {}
    for file in model_files:
        if not file.is_file():
            continue
        relative = file.relative_to(source)
        target = model_target / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and digest(target) != digest(file):
            raise ValueError("Existing staged model assets differ; they will not be overwritten.")
        if not target.exists():
            shutil.copy2(file, target, follow_symlinks=True)
        copied[relative.as_posix()] = digest(target)
    manifest = {"revision": REVISION, "model_files": copied}
    if args.snapshot_dir:
        if not args.backend_stopped:
            raise ValueError("Stop the local backend and pass --backend-stopped before taking a snapshot.")
        snapshot = args.snapshot_dir.resolve()
        original = ROOT / "data/vector_db_multisource"
        if not snapshot.is_relative_to(ROOT) or snapshot.is_relative_to(ROOT / "data"):
            raise ValueError("Test snapshots must be outside the application data directories and inside this workspace.")
        if snapshot.exists():
            raise FileExistsError("The snapshot target already exists; no existing data will be overwritten.")
        before = {str(file.relative_to(original)): digest(file) for file in original.rglob("*") if file.is_file()}
        connection = sqlite3.connect((original / "chroma.sqlite3").as_uri() + "?mode=ro", uri=True)
        if connection.execute("PRAGMA quick_check").fetchone()[0] != "ok":
            raise ValueError("The existing database did not pass its read-only integrity check.")
        connection.close()
        shutil.copytree(original, snapshot)
        after = {str(file.relative_to(original)): digest(file) for file in original.rglob("*") if file.is_file()}
        clone = {str(file.relative_to(snapshot)): digest(file) for file in snapshot.rglob("*") if file.is_file()}
        if before != after or before != clone:
            raise ValueError("Database files changed during the snapshot; stop all writers and inspect the copy.")
        manifest.update({"snapshot": str(snapshot), "database_source_hashes": before})
        config = dotenv_values(ROOT / ".env", interpolate=False)
        values = {key: config[key] for key in ("GROQ_API_KEY", "GROQ_BASE_URL", "GROQ_MODEL")}
        values.update({"REALTYAI_DB_HOST_PATH": snapshot.as_posix(), "NEXT_PUBLIC_API_URL": "http://127.0.0.1:18000",
            "CORS_ORIGINS": "http://localhost:13000,http://127.0.0.1:13000", "BACKEND_PORT": "18000", "FRONTEND_PORT": "13000"})
        if any(value is None or "\n" in value or "\r" in value for value in values.values()):
            raise ValueError("Required private deployment environment values are missing or invalid.")
        private_env = ROOT / "deployment/local.env"
        if private_env.exists():
            raise FileExistsError("The private Docker environment file exists; it will not be overwritten.")
        private_env.write_text("\n".join(key + "=" + value for key, value in values.items()) + "\n", encoding="utf-8")
        private_env.chmod(0o600)
    (ROOT / "deployment/model-cache/manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"model_revision": REVISION, "staged_model_files": len(copied),
        "snapshot_created": bool(args.snapshot_dir), "no_indexing_performed": True}))


if __name__ == "__main__":
    main()
