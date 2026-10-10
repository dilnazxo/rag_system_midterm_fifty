"""Run read-only Stage 5.1 retrieval evaluation on the saved FAISS index."""

import argparse
import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

import faiss

from evaluation.metrics import aggregate, score_question
from evaluation.retrieval_modes import MODES, search_mode
from retrieval import INDEX_VERSION, MODEL_NAME, ManualIndex, _canonical_sources, _equipment_families, _load_encoder


ROOT = Path(__file__).resolve().parents[1]
QUESTION_FIELDS = (
    "question_id", "question", "expected_model", "relevant_document",
    "relevant_pages", "relevant_chunk_ids", "question_type", "verified",
)
TRUE_VALUES = {"true", "yes", "1"}
FALSE_VALUES = {"", "false", "no", "0"}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_saved_index(index_dir: Path) -> tuple[faiss.Index, dict]:
    """Validate the saved pair without hashing PDFs or building an index."""
    faiss_path = index_dir / "chunks.faiss"
    metadata_path = index_dir / "chunks.json"
    if not faiss_path.is_file() or not metadata_path.is_file():
        raise FileNotFoundError(f"Saved index pair is missing in {index_dir}")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    if metadata.get("version") != INDEX_VERSION or metadata.get("model_name") != MODEL_NAME:
        raise ValueError("Saved index version or embedding model differs from retrieval.py")
    if metadata.get("index_sha256") != _sha256(faiss_path):
        raise ValueError("Saved FAISS file differs from the metadata checksum")
    index = faiss.read_index(str(faiss_path))
    if not isinstance(index, faiss.IndexFlatIP) or index.ntotal != len(metadata["chunks"]):
        raise ValueError("Expected a saved IndexFlatIP aligned to chunk metadata")
    return index, metadata


def read_questions(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames is None or tuple(reader.fieldnames) != QUESTION_FIELDS:
            raise ValueError(f"Questions CSV must have fields: {', '.join(QUESTION_FIELDS)}")
        rows = [{key: (row[key] or "").strip() for key in QUESTION_FIELDS} for row in reader]
    rows = [row for row in rows if any(row.values())]
    ids = [row["question_id"] for row in rows]
    if not all(ids) or len(ids) != len(set(ids)):
        raise ValueError("Every nonblank question row needs a unique question_id")
    return rows


def _items(value: str) -> list[str]:
    return [item.strip() for item in value.split("|") if item.strip()]


def prepare_truth(row: dict, metadata: dict) -> dict:
    """Keep document, page and chunk judgments independent."""
    documents = {document["name"] for document in metadata["documents"]}
    chunks = {chunk["chunk_id"]: chunk for chunk in metadata["chunks"]}
    canonical = _canonical_sources(metadata["documents"])
    answerable = row["question_type"].casefold() != "unanswerable"
    document_labels = _items(row["relevant_document"])
    page_labels = _items(row["relevant_pages"])
    chunk_labels = _items(row["relevant_chunk_ids"])
    if not row["question"]:
        raise ValueError("verified row has an empty question")
    if not answerable and (document_labels or page_labels or chunk_labels):
        raise ValueError("unanswerable row must have empty relevance fields")
    if answerable and not (document_labels or page_labels or chunk_labels):
        raise ValueError("answerable row has no relevance labels")
    if any(name not in documents for name in document_labels):
        raise ValueError("relevant_document contains a filename absent from saved metadata")
    if any(chunk_id not in chunks for chunk_id in chunk_labels):
        raise ValueError("relevant_chunk_ids contains an ID absent from saved metadata")

    canonical_documents = {canonical.get(name, name) for name in document_labels}
    canonical_pages = set()
    for label in page_labels:
        if label.isdecimal():
            if len(document_labels) != 1:
                raise ValueError("bare relevant_pages values require one relevant_document")
            filename, page = document_labels[0], int(label)
        else:
            match = re.fullmatch(r"(.+):p(\d+)", label)
            if match is None:
                raise ValueError(f"invalid relevant_pages item: {label!r}")
            filename, page = match.group(1), int(match.group(2))
        if filename not in documents or page <= 0:
            raise ValueError(f"relevant_pages refers to an unknown document or page: {label!r}")
        canonical_pages.add((canonical.get(filename, filename), page))

    canonical_chunks = set()
    for chunk_id in chunk_labels:
        chunk = chunks[chunk_id]
        source = chunk["source_file"]
        if not chunk_id.startswith(source + ":"):
            raise ValueError(f"chunk ID does not match its source file: {chunk_id!r}")
        canonical_chunks.add(canonical.get(source, source) + chunk_id[len(source):])

    families = _equipment_families(row["expected_model"])
    expected_family = next(iter(families)) if len(families) == 1 else None
    return {
        "answerable": answerable,
        "relevant_documents": canonical_documents,
        "relevant_pages": canonical_pages,
        "relevant_chunk_ids": canonical_chunks,
        "expected_family": expected_family,
        "expected_model_classifiable": len(families) == 1,
    }


def select_verified(rows: list[dict], metadata: dict) -> tuple[list[tuple[dict, dict]], list[dict], dict]:
    selected = []
    excluded = []
    verified_count = 0
    for row in rows:
        value = row["verified"].casefold()
        if value not in TRUE_VALUES:
            reason = "unverified" if value in FALSE_VALUES else "invalid_verified_flag"
            excluded.append({"question_id": row["question_id"], "reason": reason})
            continue
        verified_count += 1
        try:
            truth = prepare_truth(row, metadata)
        except ValueError as exc:
            excluded.append({"question_id": row["question_id"], "reason": "invalid_ground_truth", "detail": str(exc)})
            continue
        selected.append((row, truth))
    coverage = {
        "total_question_rows": len(rows),
        "verified_rows": verified_count,
        "evaluated_verified_rows": len(selected),
        "verified_answerable_rows": sum(truth["answerable"] for _, truth in selected),
        "verified_unanswerable_rows": sum(not truth["answerable"] for _, truth in selected),
        "excluded_rows": len(excluded),
        "excluded_by_reason": dict(Counter(item["reason"] for item in excluded)),
    }
    return selected, excluded, coverage


def run(questions_path: Path, results_dir: Path, index_dir: Path) -> dict:
    index, metadata = load_saved_index(index_dir)
    rows = read_questions(questions_path)
    selected, excluded, coverage = select_verified(rows, metadata)
    searcher = None
    if selected:
        encoder = _load_encoder(metadata["model_name"], metadata.get("model_revision"))
        searcher = ManualIndex(index, metadata["chunks"], encoder, metadata["documents"])

    results_dir.mkdir(parents=True, exist_ok=True)
    aggregate_results = {}
    for mode in MODES:
        predictions = []
        for row, truth in selected:
            retrieval = search_mode(searcher, row["question"], mode, top_k=5)
            predictions.append(
                {
                    "question_id": row["question_id"],
                    "question": row["question"],
                    "question_type": row["question_type"],
                    "expected_model": row["expected_model"],
                    "ground_truth_levels": [
                        level for level, values in (
                            ("document", truth["relevant_documents"]),
                            ("page", truth["relevant_pages"]),
                            ("chunk", truth["relevant_chunk_ids"]),
                        ) if values
                    ],
                    "answerable": truth["answerable"],
                    "latency_ms": retrieval["latency_ms"],
                    "predictions": retrieval["results"],
                    "metrics": score_question(retrieval["results"], truth),
                }
            )
        (results_dir / f"predictions_{mode.name}.json").write_text(
            json.dumps({"configuration": mode.name, "questions": predictions}, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        aggregate_results[mode.name] = {
            "model_filter": mode.model_filter,
            "deduplicate_pdfs": mode.deduplicate_pdfs,
            "metrics": aggregate(predictions),
        }

    report = {
        "index": {
            "path": str(index_dir),
            "sha256": metadata["index_sha256"],
            "model_name": metadata["model_name"],
            "model_revision": metadata.get("model_revision"),
            "chunks": index.ntotal,
            "dimensions": index.d,
            "documents": len(metadata["documents"]),
            "index_type": type(index).__name__,
        },
        "coverage": coverage,
        "configurations": aggregate_results,
        "metrics_computed_only_for_verified_ground_truth": True,
    }
    (results_dir / "aggregate.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (results_dir / "excluded_rows.json").write_text(json.dumps(excluded, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--questions", type=Path, default=ROOT / "evaluation/questions.csv")
    parser.add_argument("--results-dir", type=Path, default=ROOT / "evaluation/results")
    parser.add_argument("--index-dir", type=Path, default=ROOT / "data/index")
    args = parser.parse_args()
    report = run(args.questions, args.results_dir, args.index_dir)
    print(json.dumps({"coverage": report["coverage"], "index_chunks": report["index"]["chunks"]}, indent=2))


if __name__ == "__main__":
    main()
