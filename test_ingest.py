"""Small PDF ingestion smoke test."""

import tempfile
import unittest
from pathlib import Path

import pymupdf

from ingest import ingest_pdfs


class IngestSmokeTest(unittest.TestCase):
    def test_chunks_keep_page_and_source(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            pdf_path = Path(temporary_dir) / "sample.pdf"
            with pymupdf.open() as document:
                first_page = document.new_page()
                for line_number in range(20):
                    first_page.insert_text(
                        (72, 72 + line_number * 16),
                        f"PAGE_ONE_LINE_{line_number:02d} " + "engineering manual text " * 2,
                    )
                document.new_page()  # Empty pages should yield no records.
                document.new_page().insert_text((72, 72), "SECOND_PAGE_MARKER")
                document.save(pdf_path)

            records = ingest_pdfs(temporary_dir)

        first_page_chunks = [record["text"] for record in records if record["page"] == 1]
        self.assertGreaterEqual(len(first_page_chunks), 2)
        self.assertEqual(first_page_chunks[0][-120:], first_page_chunks[1][:120])
        self.assertEqual({record["page"] for record in records}, {1, 3})
        self.assertEqual({record["source_file"] for record in records}, {"sample.pdf"})
        self.assertEqual(len({record["chunk_id"] for record in records}), len(records))
        self.assertTrue(all(len(record["text"]) <= 800 for record in records))
        self.assertEqual(records[-1]["text"], "SECOND_PAGE_MARKER")


if __name__ == "__main__":
    unittest.main()
