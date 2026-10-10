"""Level-specific retrieval metrics; no labels are inferred from other levels."""

import math
import statistics


def score_question(predictions: list[dict], truth: dict) -> dict:
    """Score one verified row at its explicitly labeled relevance levels."""
    result = {
        "recall_at_5": None,
        "mrr_at_5": None,
        "document_hit_at_5": None,
        "page_hit_at_5": None,
        "model_confusion_wrong": 0,
        "model_confusion_classified": 0,
        "model_confusion_unclassifiable": 0,
    }
    if not truth["answerable"]:
        return result

    top5 = predictions[:5]
    chunks = truth["relevant_chunk_ids"]
    if chunks:
        found = {item["canonical_chunk_id"] for item in top5} & chunks
        result["recall_at_5"] = len(found) / len(chunks)
        first_rank = next(
            (rank for rank, item in enumerate(top5, start=1) if item["canonical_chunk_id"] in chunks),
            None,
        )
        result["mrr_at_5"] = 1 / first_rank if first_rank is not None else 0.0

    documents = truth["relevant_documents"]
    if documents:
        result["document_hit_at_5"] = int(any(item["canonical_source_file"] in documents for item in top5))

    pages = truth["relevant_pages"]
    if pages:
        result["page_hit_at_5"] = int(
            any((item["canonical_source_file"], item["page"]) in pages for item in top5)
        )

    expected_family = truth["expected_family"]
    if expected_family:
        for item in top5:
            families = item["model_families"]
            if len(families) != 1:
                result["model_confusion_unclassifiable"] += 1
                continue
            result["model_confusion_classified"] += 1
            result["model_confusion_wrong"] += families[0] != expected_family
    return result


def _mean_metric(rows: list[dict], key: str) -> dict:
    values = [row["metrics"][key] for row in rows if row["metrics"][key] is not None]
    return {"value": statistics.mean(values) if values else None, "question_denominator": len(values)}


def aggregate(rows: list[dict]) -> dict:
    """Macro-average question metrics; micro-average classified model results."""
    latency = sorted(row["latency_ms"] for row in rows)
    classified = sum(row["metrics"]["model_confusion_classified"] for row in rows)
    wrong = sum(row["metrics"]["model_confusion_wrong"] for row in rows)
    unclassifiable = sum(row["metrics"]["model_confusion_unclassifiable"] for row in rows)
    return {
        "recall_at_5": _mean_metric(rows, "recall_at_5"),
        "mrr_at_5": _mean_metric(rows, "mrr_at_5"),
        "document_hit_at_5": _mean_metric(rows, "document_hit_at_5"),
        "page_hit_at_5": _mean_metric(rows, "page_hit_at_5"),
        "model_confusion_rate": {
            "value": wrong / classified if classified else None,
            "wrong_result_count": wrong,
            "classified_result_denominator": classified,
            "unclassifiable_result_count": unclassifiable,
        },
        "retrieval_latency_ms": {
            "mean": statistics.mean(latency) if latency else None,
            "p95_nearest_rank": latency[math.ceil(0.95 * len(latency)) - 1] if latency else None,
            "question_denominator": len(latency),
        },
    }
