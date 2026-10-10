"""Evaluation-only retrieval modes over one saved ManualIndex."""

import time
from dataclasses import dataclass

from retrieval import ManualIndex, _encode, _equipment_families


@dataclass(frozen=True)
class Mode:
    name: str
    model_filter: bool
    deduplicate_pdfs: bool


MODES = (
    Mode("A", model_filter=False, deduplicate_pdfs=False),
    Mode("B", model_filter=True, deduplicate_pdfs=False),
    Mode("C", model_filter=True, deduplicate_pdfs=True),
)


def search_mode(searcher: ManualIndex, query: str, mode: Mode, top_k: int = 5) -> dict:
    """Mirror production ranking with explicit evaluation switches.

    Filtering uses model words in the question, never the expected_model label.
    The reported latency includes query encoding, FAISS search and filtering;
    index/model loading is outside the timer.
    """
    started = time.perf_counter()
    if not query.strip() or top_k <= 0:
        return {"results": [], "latency_ms": (time.perf_counter() - started) * 1000}
    if searcher.index.ntotal != len(searcher.chunks):
        raise ValueError("FAISS row count differs from saved chunk metadata")

    requested = _equipment_families(query) if mode.model_filter else set()
    eligible = {
        position
        for position, chunk in enumerate(searcher.chunks)
        if (
            not mode.deduplicate_pdfs
            or searcher._canonical_source.get(chunk["source_file"], chunk["source_file"])
            == chunk["source_file"]
        )
        and (
            not requested
            or searcher._source_families.get(chunk["source_file"], set()) & requested
        )
    }
    if not eligible:
        return {"results": [], "latency_ms": (time.perf_counter() - started) * 1000}

    vector = _encode(searcher.encoder, [query])
    if vector.shape[1] != searcher.index.d:
        raise ValueError("Query encoder dimension differs from the saved index")
    search_k = min(top_k, searcher.index.ntotal) if len(eligible) == searcher.index.ntotal else searcher.index.ntotal
    scores, positions = searcher.index.search(vector, search_k)
    results = []
    for score, position in zip(scores[0], positions[0]):
        position = int(position)
        if position < 0 or position not in eligible:
            continue
        chunk = searcher.chunks[position]
        source = chunk["source_file"]
        canonical_source = searcher._canonical_source.get(source, source)
        canonical_chunk_id = (
            canonical_source + chunk["chunk_id"][len(source):]
            if chunk["chunk_id"].startswith(source + ":")
            else chunk["chunk_id"]
        )
        results.append(
            {
                "rank": len(results) + 1,
                "index_position": position,
                "chunk_id": chunk["chunk_id"],
                "source_file": source,
                "canonical_source_file": canonical_source,
                "canonical_chunk_id": canonical_chunk_id,
                "page": chunk["page"],
                "score": float(score),
                "model_families": sorted(searcher._source_families.get(source, set())),
                "text": chunk["text"],
            }
        )
        if len(results) == top_k:
            break
    return {"results": results, "latency_ms": (time.perf_counter() - started) * 1000}
