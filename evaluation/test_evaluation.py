"""Deterministic Stage 5.1 tests; no model download or API calls."""

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from evaluation.evaluate import QUESTION_FIELDS, ROOT, prepare_truth, run, select_verified
from evaluation.metrics import aggregate, score_question
from evaluation.retrieval_modes import MODES, search_mode
from test_retrieval import model_fixture


class RetrievalModesTest(unittest.TestCase):
    def test_filtering_modes_and_duplicate_handling(self):
        searcher = model_fixture()
        query = "CyberRow DX electrical requirements"
        a, b, c = [search_mode(searcher, query, mode)["results"] for mode in MODES]
        self.assertEqual(len(a), 5)
        self.assertTrue(any("CyberOne DX" in item["source_file"] for item in a))
        self.assertTrue(all("CyberRow DX" in item["source_file"] for item in b))
        self.assertTrue(any("(1).pdf" in item["source_file"] for item in b))
        self.assertTrue(all("(1).pdf" not in item["source_file"] for item in c))
        self.assertEqual([item["chunk_id"] for item in c],
                         [item["chunk_id"] for item in searcher.search(query, top_k=5)])
        self.assertEqual(len({item["canonical_chunk_id"] for item in b}), len(c))

    def test_empty_results_and_unrecognized_query_model(self):
        searcher = model_fixture()
        self.assertEqual(search_mode(searcher, " ", MODES[0])["results"], [])
        self.assertEqual(search_mode(searcher, "electrical data", MODES[0], top_k=0)["results"], [])
        self.assertEqual(
            [item["chunk_id"] for item in search_mode(searcher, "general electrical data", MODES[0])["results"]],
            [item["chunk_id"] for item in search_mode(searcher, "general electrical data", MODES[1])["results"]],
        )


class MetricsTest(unittest.TestCase):
    def test_level_specific_metrics_and_denominators(self):
        predictions = [
            {"canonical_chunk_id": "other:p1:c1", "canonical_source_file": "other",
             "page": 1, "model_families": ["cyberone dx"]},
            {"canonical_chunk_id": "target:p2:c2", "canonical_source_file": "target",
             "page": 2, "model_families": ["cyberrow dx"]},
            {"canonical_chunk_id": "unknown:p1:c1", "canonical_source_file": "unknown",
             "page": 1, "model_families": []},
        ]
        truth = {
            "answerable": True,
            "relevant_documents": {"target"},
            "relevant_pages": {("target", 2)},
            "relevant_chunk_ids": {"target:p2:c2", "target:p2:c3"},
            "expected_family": "cyberrow dx",
        }
        metrics = score_question(predictions, truth)
        self.assertEqual(metrics["recall_at_5"], 0.5)
        self.assertEqual(metrics["mrr_at_5"], 0.5)
        self.assertEqual(metrics["document_hit_at_5"], 1)
        self.assertEqual(metrics["page_hit_at_5"], 1)
        self.assertEqual((metrics["model_confusion_wrong"], metrics["model_confusion_classified"],
                          metrics["model_confusion_unclassifiable"]), (1, 2, 1))
        unanswerable = score_question(predictions, {**truth, "answerable": False})
        self.assertIsNone(unanswerable["recall_at_5"])
        self.assertIsNone(unanswerable["document_hit_at_5"])
        report = aggregate([
            {"metrics": metrics, "latency_ms": 10.0},
            {"metrics": unanswerable, "latency_ms": 20.0},
        ])
        self.assertEqual(report["recall_at_5"], {"value": 0.5, "question_denominator": 1})
        self.assertEqual(report["model_confusion_rate"]["value"], 0.5)
        self.assertEqual(report["retrieval_latency_ms"]["mean"], 15.0)
        self.assertEqual(report["retrieval_latency_ms"]["question_denominator"], 2)

    def test_document_label_never_becomes_chunk_label_and_empty_prediction_is_miss(self):
        metadata = {
            "documents": [{"name": "manual.pdf", "sha256": "same"},
                          {"name": "manual (1).pdf", "sha256": "same"}],
            "chunks": [{"source_file": "manual.pdf", "chunk_id": "manual.pdf:p2:c1", "page": 2}],
        }
        row = {"question": "question", "expected_model": "", "relevant_document": "manual.pdf",
               "relevant_pages": "", "relevant_chunk_ids": "", "question_type": "fact"}
        truth = prepare_truth(row, metadata)
        score = score_question([], truth)
        self.assertIsNone(score["recall_at_5"])
        self.assertIsNone(score["mrr_at_5"])
        self.assertEqual(score["document_hit_at_5"], 0)
        self.assertIsNone(score["page_hit_at_5"])
        with_chunk = copy.deepcopy(row)
        with_chunk["relevant_chunk_ids"] = "manual.pdf:p2:c1"
        truth = prepare_truth(with_chunk, metadata)
        duplicate_prediction = [{"canonical_chunk_id": "manual.pdf:p2:c1", "canonical_source_file": "manual.pdf",
                                 "page": 2, "model_families": []}]
        self.assertEqual(score_question(duplicate_prediction, truth)["recall_at_5"], 1.0)

    def test_page_only_label_stays_at_page_level(self):
        metadata = {
            "documents": [{"name": "manual.pdf", "sha256": "a"}],
            "chunks": [{"source_file": "manual.pdf", "chunk_id": "manual.pdf:p2:c1", "page": 2}],
        }
        row = {"question": "question", "expected_model": "", "relevant_document": "",
               "relevant_pages": "manual.pdf:p2", "relevant_chunk_ids": "", "question_type": "fact"}
        truth = prepare_truth(row, metadata)
        prediction = [{"canonical_chunk_id": "manual.pdf:p2:c1", "canonical_source_file": "manual.pdf",
                       "page": 2, "model_families": []}]
        metrics = score_question(prediction, truth)
        self.assertEqual(metrics["page_hit_at_5"], 1)
        self.assertIsNone(metrics["document_hit_at_5"])
        self.assertIsNone(metrics["recall_at_5"])

    def test_verified_selection_and_invalid_ground_truth(self):
        metadata = {"documents": [{"name": "manual.pdf", "sha256": "a"}], "chunks": []}
        base = {"question": "q", "expected_model": "", "relevant_document": "manual.pdf",
                "relevant_pages": "", "relevant_chunk_ids": "", "question_type": "fact", "verified": "true"}
        rows = [
            {**base, "question_id": "v"},
            {**base, "question_id": "u", "verified": ""},
            {**base, "question_id": "bad", "relevant_document": "missing.pdf"},
            {**base, "question_id": "n", "question_type": "unanswerable", "relevant_document": ""},
        ]
        selected, excluded, coverage = select_verified(rows, metadata)
        self.assertEqual(len(selected), 2)
        self.assertEqual(coverage["verified_rows"], 3)
        self.assertEqual(coverage["verified_unanswerable_rows"], 1)
        self.assertEqual(coverage["excluded_by_reason"], {"unverified": 1, "invalid_ground_truth": 1})
        self.assertEqual(len(excluded), 2)
        empty = aggregate([])
        self.assertIsNone(empty["recall_at_5"]["value"])
        self.assertEqual(empty["recall_at_5"]["question_denominator"], 0)


class HeaderOnlyRunTest(unittest.TestCase):
    def test_header_only_template_writes_no_scores_or_model_call(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            questions = output / "header_only.csv"
            questions.write_text(",".join(QUESTION_FIELDS) + "\n", encoding="utf-8")
            with patch("evaluation.evaluate._load_encoder") as encoder:
                report = run(questions, output, ROOT / "data/index")
            encoder.assert_not_called()
            self.assertEqual(report["coverage"]["evaluated_verified_rows"], 0)
            for mode in "ABC":
                saved = json.loads((output / f"predictions_{mode}.json").read_text(encoding="utf-8"))
                self.assertEqual(saved["questions"], [])
                self.assertIsNone(report["configurations"][mode]["metrics"]["recall_at_5"]["value"])


if __name__ == "__main__":
    unittest.main()
