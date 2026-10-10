"""Lightweight checks for the generated benchmark artifacts."""

import csv
import json
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parent
REVIEW_FIELDS = (
    "row_column_accuracy",
    "header_accuracy",
    "numeric_cell_accuracy",
    "notes_preserved",
)


class BenchmarkArtifactsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.selection = json.loads((HERE / "selection.json").read_text(encoding="utf-8"))
        cls.summary = json.loads((HERE / "automatic_summary.json").read_text(encoding="utf-8"))

    def test_sample_is_diverse(self):
        specs = self.selection["tables"]
        self.assertGreaterEqual(len(specs), 10)
        self.assertLessEqual(len(specs), 15)
        self.assertEqual(len(specs), len({spec["id"] for spec in specs}))
        self.assertGreaterEqual(len({spec["filename"] for spec in specs}), 5)
        self.assertEqual(
            {"electrical", "dimensions", "performance"},
            {spec["category"] for spec in specs},
        )

    def test_exports_preserve_cell_coordinates(self):
        for spec in self.selection["tables"]:
            with self.subTest(table=spec["id"]):
                table_id = spec["id"]
                data = json.loads((HERE / "json" / f"{table_id}.json").read_text(encoding="utf-8"))
                self.assertEqual(data["filename"], spec["filename"])
                self.assertEqual(data["pdf_page_index"], spec["page_index"])
                self.assertTrue((HERE / "markdown" / f"{table_id}.md").is_file())
                self.assertGreater((HERE / "references" / f"{table_id}.png").stat().st_size, 0)
                if data["detection_success"]:
                    self.assertEqual(len(data["raw_grid"]), data["row_count"])
                    self.assertEqual(len(data["cells"]), data["row_count"])
                    self.assertEqual(len(data["raw_header"]["names"]), data["column_count"])
                    for row_number, (raw_row, cell_row) in enumerate(zip(data["raw_grid"], data["cells"])):
                        self.assertEqual(len(raw_row), data["column_count"])
                        self.assertEqual(len(cell_row), data["column_count"])
                        for column_number, (value, cell) in enumerate(zip(raw_row, cell_row)):
                            self.assertEqual(cell["row"], row_number)
                            self.assertEqual(cell["column"], column_number)
                            self.assertEqual(cell["text"], value)
                            if cell["bbox"] is not None:
                                x0, y0, x1, y1 = cell["bbox"]
                                self.assertLessEqual(x0, x1)
                                self.assertLessEqual(y0, y1)

    def test_automatic_counts_and_review_separation(self):
        specs = self.selection["tables"]
        detected = sum(
            json.loads((HERE / "json" / f"{spec['id']}.json").read_text(encoding="utf-8"))["detection_success"]
            for spec in specs
        )
        self.assertEqual(self.summary["selected_tables"], len(specs))
        self.assertEqual(self.summary["selected_candidates_returned_by_find_tables"], detected)
        self.assertNotIn("numeric_cell_accuracy", self.summary)
        with (HERE / "human_review.csv").open("r", encoding="utf-8-sig", newline="") as stream:
            review_rows = list(csv.DictReader(stream))
        self.assertEqual({row["table_id"] for row in review_rows}, {spec["id"] for spec in specs})
        status = json.loads((HERE / "human_review_status.json").read_text(encoding="utf-8"))
        if status["rows_with_any_manual_review_entry"] == 0:
            self.assertTrue(all(not row[field] for row in review_rows for field in REVIEW_FIELDS))
        self.assertIsNone(status["accuracy_aggregates"])


if __name__ == "__main__":
    unittest.main()
