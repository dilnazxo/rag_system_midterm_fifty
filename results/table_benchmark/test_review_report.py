"""Check the offline review page without adding browser or PDF dependencies."""

import csv
import json
import unittest
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote

from results.table_benchmark import build_review_report


HERE = Path(__file__).resolve().parent


class ReportParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.case_ids = []
        self.image_sources = []
        self.grid_count = 0

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "section" and "case" in attributes.get("class", "").split():
            self.case_ids.append(attributes["data-table-id"])
        if tag == "img":
            self.image_sources.append(attributes["src"])
        if tag == "table" and "extracted-grid" in attributes.get("class", "").split():
            self.grid_count += 1


class ReviewReportTest(unittest.TestCase):
    def test_report_covers_every_export_and_preserves_csv(self):
        csv_path = HERE / "human_review.csv"
        before = csv_path.read_bytes()
        build_review_report.main()
        self.assertEqual(csv_path.read_bytes(), before)

        selection = json.loads((HERE / "selection.json").read_text(encoding="utf-8"))["tables"]
        report = (HERE / "review.html").read_text(encoding="utf-8")
        parser = ReportParser()
        parser.feed(report)
        self.assertEqual(parser.case_ids, [spec["id"] for spec in selection])
        self.assertEqual(parser.grid_count, len(selection))
        self.assertEqual(len(parser.image_sources), len(selection))
        for source in parser.image_sources:
            self.assertTrue((HERE / unquote(source)).is_file(), source)

        with csv_path.open("r", encoding="utf-8-sig", newline="") as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual([row["table_id"] for row in rows], parser.case_ids)
        for phrase in ("Rows and columns", "Headers", "Numerical cells", "Cell associations", "Notes"):
            self.assertIn(phrase, report)


if __name__ == "__main__":
    unittest.main()
