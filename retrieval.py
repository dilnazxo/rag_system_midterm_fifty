"""Local sentence embeddings and FAISS search for PDF manual chunks."""

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Protocol, TypedDict

import faiss
import numpy as np

from ingest import ChunkRecord, ingest_pdfs


MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
BATCH_SIZE = 32
INDEX_VERSION = 1
_EQUIPMENT_PATTERN = re.compile(r"\bcyber\s*(row|one|air)\s+(dx|cw)\b")


class Encoder(Protocol):
    def encode(self, sentences: list[str], **kwargs: object) -> np.ndarray: ...


class SearchResult(TypedDict):
    text: str
    source_file: str
    page: int
    chunk_id: str
    score: float


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _document_fingerprints(directory: Path) -> list[dict[str, str]]:
    pdf_paths = sorted(
        (path for path in directory.iterdir() if path.is_file() and path.suffix.lower() == ".pdf"),
        key=lambda path: path.name.lower(),
    )
    return [{"name": path.name, "sha256": _file_hash(path)} for path in pdf_paths]


def _equipment_families(value: str) -> set[str]:
    normalized = re.sub(r"[^a-z0-9]+", " ", value.casefold())
    return {f"cyber{family} {variant}" for family, variant in _EQUIPMENT_PATTERN.findall(normalized)}


def _canonical_sources(documents: list[dict[str, str]]) -> dict[str, str]:
    names_by_hash: dict[str, list[str]] = {}
    for document in documents:
        names_by_hash.setdefault(document["sha256"], []).append(document["name"])
    canonical_by_hash = {
        digest: min(
            names,
            key=lambda name: (bool(re.search(r" \(\d+\)\.pdf$", name, re.IGNORECASE)), name.casefold()),
        )
        for digest, names in names_by_hash.items()
    }
    return {document["name"]: canonical_by_hash[document["sha256"]] for document in documents}


def _load_encoder(model_name: str, model_revision: str | None) -> Encoder:
    import torch
    from sentence_transformers import SentenceTransformer

    device = "cuda" if torch.cuda.is_available() else "cpu"
    return SentenceTransformer(
        model_name,
        device=device,
        revision=model_revision,
        local_files_only=True,
    )


def _encode(encoder: Encoder, texts: list[str]) -> np.ndarray:
    vectors = np.asarray(
        encoder.encode(
            texts,
            batch_size=BATCH_SIZE,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        ),
        dtype=np.float32,
    )
    if vectors.ndim != 2 or vectors.shape[0] != len(texts):
        raise ValueError("Encoder returned an unexpected embedding shape")
    faiss.normalize_L2(vectors)
    return vectors


class ManualIndex:
    """A persisted FAISS index and its page-aligned chunk records."""

    def __init__(
        self,
        index: faiss.Index,
        chunks: list[ChunkRecord],
        encoder: Encoder,
        documents: list[dict[str, str]] | None = None,
    ):
        self.index = index
        self.chunks = chunks
        self.encoder = encoder
        self._canonical_source = _canonical_sources(documents or [])
        self._source_families = {
            chunk["source_file"]: _equipment_families(chunk["source_file"]) for chunk in chunks
        }

    @classmethod
    def load_or_build(
        cls,
        manuals_dir: str | Path = "data/manuals",
        index_dir: str | Path = "data/index",
        *,
        model_name: str = MODEL_NAME,
        model_revision: str | None = None,
        encoder: Encoder | None = None,
        allow_build: bool = True,
    ) -> "ManualIndex":
        """Reuse the index only when PDF content and model identity still match."""
        manuals_path = Path(manuals_dir)
        index_path = Path(index_dir)
        documents = _document_fingerprints(manuals_path)
        if encoder is None:
            encoder = _load_encoder(model_name, model_revision)

        faiss_path = index_path / "chunks.faiss"
        metadata_path = index_path / "chunks.json"
        if faiss_path.is_file() and metadata_path.is_file():
            try:
                metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
                if (
                    metadata["version"] == INDEX_VERSION
                    and metadata["model_name"] == model_name
                    and metadata["model_revision"] == model_revision
                    and metadata["documents"] == documents
                    and metadata["index_sha256"] == _file_hash(faiss_path)
                ):
                    index = faiss.read_index(str(faiss_path))
                    chunks = metadata["chunks"]
                    if index.ntotal == len(chunks):
                        return cls(index, chunks, encoder, documents)
            except (OSError, ValueError, KeyError, TypeError, RuntimeError):
                pass  # A stale or damaged cache is rebuilt below.

        if not allow_build:
            raise FileNotFoundError(f"Saved FAISS index is missing or stale in {index_path}")

        chunks = ingest_pdfs(manuals_path)
        if not chunks:
            raise ValueError(f"No extractable PDF text in {manuals_path}")

        index: faiss.Index | None = None
        for start in range(0, len(chunks), BATCH_SIZE):
            texts = [chunk["text"] for chunk in chunks[start : start + BATCH_SIZE]]
            vectors = _encode(encoder, texts)
            if index is None:
                index = faiss.IndexFlatIP(vectors.shape[1])
            elif vectors.shape[1] != index.d:
                raise ValueError("Encoder dimension changed during indexing")
            index.add(vectors)

        assert index is not None
        index_path.mkdir(parents=True, exist_ok=True)
        temporary_faiss = index_path / "chunks.faiss.tmp"
        temporary_metadata = index_path / "chunks.json.tmp"
        faiss.write_index(index, str(temporary_faiss))
        metadata = {
            "version": INDEX_VERSION,
            "model_name": model_name,
            "model_revision": model_revision,
            "documents": documents,
            "index_sha256": _file_hash(temporary_faiss),
            "chunks": chunks,
        }
        temporary_metadata.write_text(json.dumps(metadata, ensure_ascii=False), encoding="utf-8")
        os.replace(temporary_faiss, faiss_path)
        os.replace(temporary_metadata, metadata_path)
        return cls(index, chunks, encoder, documents)

    def search(self, query: str, top_k: int = 5) -> list[SearchResult]:
        """Rank eligible manual chunks, excluding other models and duplicate PDFs."""
        if not query.strip() or top_k <= 0:
            return []
        requested_families = _equipment_families(query)
        eligible_positions = {
            position
            for position, chunk in enumerate(self.chunks)
            if self._canonical_source.get(chunk["source_file"], chunk["source_file"])
            == chunk["source_file"]
            and (
                not requested_families
                or self._source_families[chunk["source_file"]] & requested_families
            )
        }
        if not eligible_positions:
            return []
        query_vector = _encode(self.encoder, [query])
        if query_vector.shape[1] != self.index.d:
            raise ValueError("Query encoder dimension differs from the saved index")
        search_k = min(top_k, self.index.ntotal) if len(eligible_positions) == self.index.ntotal else self.index.ntotal
        scores, positions = self.index.search(query_vector, search_k)
        results: list[SearchResult] = []
        for score, position in zip(scores[0], positions[0]):
            if int(position) not in eligible_positions:
                continue
            chunk = self.chunks[int(position)]
            results.append(
                {
                    "text": chunk["text"],
                    "source_file": chunk["source_file"],
                    "page": chunk["page"],
                    "chunk_id": chunk["chunk_id"],
                    "score": float(score),
                }
            )
            if len(results) == top_k:
                break
        return results
