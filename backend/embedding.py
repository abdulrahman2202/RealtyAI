"""Local cached tokenizer and embedding provenance shared by every source."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from sentence_transformers import SentenceTransformer
from transformers import AutoTokenizer

from backend.recovery_diagnostics import diagnostic_stage

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


@dataclass(frozen=True)
class EmbeddingProfile:
    tokenizer: Any
    snapshot: Path
    revision: str
    max_sequence_length: int
    dimension: int
    model: str = MODEL_NAME

    def count(self, text: str) -> int:
        return len(self.tokenizer.encode(text, add_special_tokens=True, truncation=False, verbose=False))

    def provenance(self) -> dict:
        return {
            "embedding_model": self.model,
            "embedding_revision": self.revision,
            "embedding_dimension": self.dimension,
            "embedding_max_sequence_length": self.max_sequence_length,
        }


@lru_cache(maxsize=1)
@diagnostic_stage("offline_model_profile")
def cached_profile() -> EmbeddingProfile:
    hub = Path(os.getenv("HF_HUB_CACHE") or os.getenv("HUGGINGFACE_HUB_CACHE") or (
        Path(os.getenv("HF_HOME", str(Path.home() / ".cache" / "huggingface"))) / "hub"
    ))
    model_root = hub / "models--sentence-transformers--all-MiniLM-L6-v2"
    ref = model_root / "refs" / "main"
    if not ref.is_file():
        raise FileNotFoundError("The approved SentenceTransformer model must already be cached locally.")
    revision = ref.read_text(encoding="utf-8").strip()
    snapshot = (model_root / "snapshots" / revision).resolve()
    if not snapshot.is_relative_to((model_root / "snapshots").resolve()):
        raise ValueError("Invalid cached model revision.")
    configuration = json.loads((snapshot / "sentence_bert_config.json").read_text(encoding="utf-8"))
    transformer = json.loads((snapshot / "config.json").read_text(encoding="utf-8"))
    limit = min(int(configuration["max_seq_length"]), 256)
    tokenizer = AutoTokenizer.from_pretrained(str(snapshot), local_files_only=True, use_fast=True)
    return EmbeddingProfile(tokenizer, snapshot, revision, limit, int(transformer["hidden_size"]))


@lru_cache(maxsize=1)
@diagnostic_stage("offline_embedding_model_loading")
def cached_encoder() -> SentenceTransformer:
    profile = cached_profile()
    encoder = SentenceTransformer(str(profile.snapshot), local_files_only=True, device="cpu")
    encoder.max_seq_length = profile.max_sequence_length
    return encoder
