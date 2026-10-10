"""Run an explicitly unverified, read-only retrieval comparison on candidate labels."""

import csv
import json
from collections import Counter
from pathlib import Path

import pymupdf

from evaluation.evaluate import ROOT, _sha256, load_saved_index, prepare_truth, read_questions
from evaluation.metrics import aggregate, score_question
from evaluation.retrieval_modes import MODES, search_mode
from ingest import chunk_text
from retrieval import ManualIndex, _load_encoder


SOURCE = ROOT / "evaluation/questions_candidates.csv"
OUTPUT = ROOT / "evaluation/results/provisional"
FIELDS = (
    "question_id", "question", "expected_model", "relevant_document",
    "relevant_pages", "relevant_chunk_ids", "question_type", "verified",
)
REVIEW_IDS = ("q010", "q018", "q020", "q027", "q029")


def _parts(value: str) -> list[str]:
    return [part.strip() for part in value.split("|") if part.strip()]


def validate(rows: list[dict], metadata: dict) -> tuple[list[tuple[dict, dict, bool]], list[dict]]:
    """Check provenance and structural consistency, never semantic correctness."""
    documents = {item["name"]: item["sha256"] for item in metadata["documents"]}
    chunks = {item["chunk_id"]: item for item in metadata["chunks"]}
    by_page = {}
    for item in metadata["chunks"]:
        by_page.setdefault((item["source_file"], item["page"]), []).append(item)
    opened = {}
    hash_matches = {}
    checks = []
    selected = []
    try:
        for row in rows:
            errors = []
            if row["verified"].casefold() not in {"", "false", "no", "0"}:
                errors.append("candidate must remain unverified")
            try:
                truth = prepare_truth(row, metadata)
            except ValueError as exc:
                errors.append(str(exc))
                truth = None
            names = _parts(row["relevant_document"])
            page_numbers = [int(p) for p in _parts(row["relevant_pages"]) if p.isdecimal()]
            ids = _parts(row["relevant_chunk_ids"])
            for name in names:
                path = ROOT / "data/manuals" / name
                if name not in documents or not path.is_file():
                    errors.append(f"missing indexed PDF: {name}")
                    continue
                if name not in opened:
                    hash_matches[name] = _sha256(path) == documents[name]
                    opened[name] = pymupdf.open(path)
                if not hash_matches[name]:
                    errors.append(f"PDF checksum differs from saved metadata: {name}")
                document = opened[name]
                for page in page_numbers:
                    if not 1 <= page <= len(document):
                        errors.append(f"page outside PDF: {name}:p{page}")
                        continue
                    actual = chunk_text(document[page - 1].get_text("text"))
                    saved = by_page.get((name, page), [])
                    if [item["text"] for item in saved] != actual:
                        errors.append(f"source PDF text differs from saved chunks: {name}:p{page}")
            for chunk_id in ids:
                item = chunks.get(chunk_id)
                if item and (item["source_file"] not in names or item["page"] not in page_numbers):
                    errors.append(f"chunk document/page conflicts with candidate: {chunk_id}")
            # Only a page represented by exactly one indexed chunk can establish
            # page-local chunk-label completeness without interpreting split tables.
            chunk_complete = bool(truth and truth["answerable"] and page_numbers and ids)
            if chunk_complete:
                chunk_complete = all(
                    len(by_page.get((name, page), [])) == 1
                    and by_page[(name, page)][0]["chunk_id"] in ids
                    for name in names for page in page_numbers
                ) and len(ids) == len(names) * len(page_numbers)
            checks.append({
                "question_id": row["question_id"],
                "status": "PROVISIONAL / AUTO-LABELED: structurally_consistent" if not errors else "invalid",
                "errors": errors,
                "chunk_recall_subset": bool(chunk_complete and not errors),
                "semantic_accuracy_verified": False,
            })
            if not errors:
                selected.append((row, truth, bool(chunk_complete)))
    finally:
        for document in opened.values():
            document.close()
    return selected, checks


def _pct(metric: dict) -> str:
    value = metric["value"]
    return "n/a" if value is None else f"{100 * value:.1f}% ({metric['question_denominator']} Q)"


def _write_review_sheet(rows: list[dict], output: Path) -> None:
    # These short excerpts are re-read from the source PDFs, not from retrieved chunks.
    cues = {
        "q010": ("gks_65_gce_professional.pdf", 8, "Circular Saw", 540),
        "q018": ("990_4705_InRow_Chilled_Water_Air_Conditioners_300_Installation_Manual.pdf", 15, "Package Contents", 520),
        "q020": ("STULZ_Glycol_Systems_Engineering_Manual.pdf", 5, "Pressure Drop/Flow Rate Curves", 750),
        "q027": ("STULZ CyberOne DX Engineering Manual.pdf", 24, "Cooling Only", 360),
        "q029": ("STULZ CyberRow DX Engineering Manual QEWR002L.pdf", 13, "Model: CRS-", 430),
    }
    lookup = {row["question_id"]: row for row in rows}
    lines = [
        "# Quick human review — PROVISIONAL / AUTO-LABELED",
        "",
        "All five questions remain `verified=false`. These source-PDF excerpts are review prompts, not certified answers. Check the rendered page and the proposed chunk IDs in `chunks.json` before accepting a label.",
        "",
    ]
    for question_id in REVIEW_IDS:
        row = lookup[question_id]
        name, page, anchor, width = cues[question_id]
        with pymupdf.open(ROOT / "data/manuals" / name) as document:
            source = document[page - 1].get_text("text")
        position = source.find(anchor)
        excerpt = source[max(position, 0):max(position, 0) + width].strip()
        lines.extend([
            f"## {question_id} — {row['question_type']}", "",
            f"**Question:** {row['question']}", "",
            f"**Source:** `data/manuals/{name}`, PDF p{page}. Proposed chunk IDs: `{row['relevant_chunk_ids'] or 'none'}`.", "",
            "**Source-PDF text excerpt:**", "", "```text", excerpt, "```", "",
        ])
        if question_id == "q018":
            name2, page2 = name, 16
            with pymupdf.open(ROOT / "data/manuals" / name2) as document:
                source2 = document[page2 - 1].get_text("text")
            lines.extend(["**Also inspect PDF p16:**", "", "```text", source2[:500].strip(), "```", ""])
        if question_id == "q029":
            lines.append("**Absence check:** automatic scan of all 50 indexed PDFs found no `price` or `msrp` text. Confirm visually and consider other wording before accepting an unanswerable label.\n")
        elif question_id == "q027":
            lines.append("**Review focus:** the model/MCA header is separated from the cooling-only rows in saved chunks; confirm the 042 column and pump No/Yes association.\n")
        else:
            lines.append("**Review focus:** confirm the stated model, condition, value/wording, page, and chunk relevance.\n")
    (output / "quick_review.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def run() -> dict:
    index, metadata = load_saved_index(ROOT / "data/index")
    rows = read_questions(SOURCE)
    selected, checks = validate(rows, metadata)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    with (OUTPUT / "questions_provisional.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    (OUTPUT / "label_validation.json").write_text(json.dumps(checks, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if len(selected) != len(rows):
        raise ValueError("Some candidate labels failed structural validation; see label_validation.json")
    encoder = _load_encoder(metadata["model_name"], metadata.get("model_revision"))
    searcher = ManualIndex(index, metadata["chunks"], encoder, metadata["documents"])
    comparison = {}
    for mode in MODES:
        answerable_results = []
        no_answer_results = []
        for row, truth, chunk_complete in selected:
            retrieval = search_mode(searcher, row["question"], mode, top_k=5)
            result = {
                "question_id": row["question_id"], "question": row["question"],
                "question_type": row["question_type"], "verified": False,
                "label_status": "PROVISIONAL / AUTO-LABELED",
                "chunk_recall_subset": chunk_complete,
                "latency_ms": retrieval["latency_ms"], "predictions": retrieval["results"],
            }
            if truth["answerable"]:
                result["metrics"] = score_question(retrieval["results"], truth)
                if not chunk_complete:
                    result["metrics"]["recall_at_5"] = None
                    result["metrics"]["mrr_at_5"] = None
                answerable_results.append(result)
            else:
                result["metrics"] = None
                no_answer_results.append(result)
        (OUTPUT / f"predictions_{mode.name}.json").write_text(json.dumps({
            "label_status": "PROVISIONAL / AUTO-LABELED", "configuration": mode.name,
            "verified_questions": 0, "answerable": answerable_results,
            "unanswerable_candidates_unscored": no_answer_results,
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        comparison[mode.name] = {
            "model_filter": mode.model_filter,
            "deduplicate_pdfs": mode.deduplicate_pdfs,
            "answerable_metrics": aggregate(answerable_results),
            "unanswerable_candidates": len(no_answer_results),
            "unanswerable_latency_ms": [item["latency_ms"] for item in no_answer_results],
        }
    report = {
        "label_status": "PROVISIONAL / AUTO-LABELED — NOT VERIFIED ACCURACY",
        "verified_questions": 0,
        "candidate_questions": len(rows),
        "structurally_valid_candidates": len(selected),
        "answerable_candidates": sum(truth["answerable"] for _, truth, _ in selected),
        "unanswerable_candidates_unverified": sum(not truth["answerable"] for _, truth, _ in selected),
        "chunk_recall_subset_questions": [row["question_id"] for row, truth, eligible in selected if truth["answerable"] and eligible],
        "index_sha256": metadata["index_sha256"],
        "index_chunks": index.ntotal,
        "configurations": comparison,
    }
    (OUTPUT / "aggregate.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# PROVISIONAL / AUTO-LABELED retrieval comparison",
        "", "**Verified questions: 0.** Candidate labels passed structural checks only; none are verified accuracy. All modes used the same saved FAISS index.", "",
        "| Mode | Document Hit@5 | Page Hit@5 | Chunk Recall@5* | Chunk MRR@5* | Model confusion | Mean latency (ms) | p95 latency (ms) |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name, entry in comparison.items():
        metrics = entry["answerable_metrics"]
        confusion = metrics["model_confusion_rate"]
        rate = "n/a" if confusion["value"] is None else f"{100 * confusion['value']:.1f}% ({confusion['classified_result_denominator']} results)"
        latency = metrics["retrieval_latency_ms"]
        lines.append(f"| {name} | {_pct(metrics['document_hit_at_5'])} | {_pct(metrics['page_hit_at_5'])} | {_pct(metrics['recall_at_5'])} | {_pct(metrics['mrr_at_5'])} | {rate} | {latency['mean']:.1f} | {latency['p95_nearest_rank']:.1f} |")
    lines.extend([
        "", "*Chunk metrics use only candidate questions whose labeled PDF page has exactly one saved chunk per page and whose label lists that chunk. This is structural completeness, not human judgment of semantic relevance.*",
        "", "Document and page metrics use 28 answerable candidates. MRR is displayed as a percentage of its 0–1 scale. Mean and p95 latency also use the 28 answerable candidates. The two provisional unanswerable candidates are excluded from all answerable-only metrics and timed separately in `aggregate.json`; no absence or abstention score is claimed.",
        "", "Model confusion covers only recognizable CyberRow/CyberOne family results; other equipment families are outside the existing classifier. Latency is one local pass per mode, including encoding and FAISS search but excluding index/model loading. Mode order and caching can affect timing.",
        "", "Automatic validation checks exact PDF filenames and hashes, page bounds, chunk IDs and document/page alignment, and regeneration of saved chunk text from each source page. It cannot establish correct table cell associations, semantic relevance, exhaustive labels, or absence from image-only PDF content.",
        "", "Files: `questions_provisional.csv`, `label_validation.json`, `predictions_A.json`, `predictions_B.json`, `predictions_C.json`, `aggregate.json`, `quick_review.md`.",
    ])
    (OUTPUT / "comparison.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    _write_review_sheet(rows, OUTPUT)
    return report


if __name__ == "__main__":
    result = run()
    print(json.dumps({key: value for key, value in result.items() if key not in {"configurations"}}, indent=2))
