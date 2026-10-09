"""Lightweight index tests with deterministic mock embeddings."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import faiss
import numpy as np
import pymupdf

from retrieval import ManualIndex


class MockEncoder:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def encode(self, sentences: list[str], **kwargs: object) -> np.ndarray:
        self.calls.append(sentences)
        assert kwargs["normalize_embeddings"] is True
        assert kwargs["batch_size"] == 32
        return np.asarray(
            [[1.0, 0.0] if "pump" in sentence.lower() else [0.0, 1.0] for sentence in sentences],
            dtype=np.float32,
        )


class FixedEncoder:
    def encode(self, sentences: list[str], **kwargs: object) -> np.ndarray:
        return np.tile(np.asarray([[1.0, 0.0]], dtype=np.float32), (len(sentences), 1))


def model_fixture() -> ManualIndex:
    names = {
        "one": "STULZ CyberOne DX Engineering Manual.pdf",
        "one_copy": "STULZ CyberOne DX Engineering Manual (1).pdf",
        "row": "STULZ CyberRow DX Engineering Manual QEWR002L.pdf",
        "row_copy": "STULZ CyberRow DX Engineering Manual QEWR002L (1).pdf",
        "cw": "STULZ CyberRow CW Engineering Manual QEWR001G.pdf",
    }
    documents = [
        {"name": name, "sha256": "one" if key.startswith("one") else "row" if key.startswith("row") else "cw"}
        for key, name in names.items()
    ]
    records = [
        ("one", 39, 1, "CyberOne DX header", [1.0, 0.0]),
        ("one_copy", 39, 1, "CyberOne DX header", [1.0, 0.0]),
        ("cw", 17, 1, "CyberRow CW electrical system", [0.99, 0.14]),
        ("row_copy", 13, 1, "CyberRow DX electrical data", [0.98, 0.2]),
        ("row", 13, 1, "CyberRow DX electrical data", [0.98, 0.2]),
        ("row", 18, 2, "CyberRow DX control wiring", [0.9, 0.44]),
        ("row", 18, 3, "CyberRow DX circuit protection", [0.85, 0.53]),
    ]
    chunks = [
        {
            "source_file": names[key],
            "page": page,
            "chunk_id": f"{names[key]}:p{page}:c{number}",
            "text": text,
        }
        for key, page, number, text, _ in records
    ]
    vectors = np.asarray([vector for _, _, _, _, vector in records], dtype=np.float32)
    faiss.normalize_L2(vectors)
    index = faiss.IndexFlatIP(2)
    index.add(vectors)
    return ManualIndex(index, chunks, FixedEncoder(), documents)


def write_pdf(path: Path, text: str) -> None:
    with pymupdf.open() as document:
        document.new_page().insert_text((72, 72), text)
        document.save(path)


class RetrievalTest(unittest.TestCase):
    def test_read_only_load_never_builds_a_missing_index(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            root = Path(temporary_dir)
            with patch("retrieval.ingest_pdfs") as ingest:
                with self.assertRaisesRegex(FileNotFoundError, "Saved FAISS index"):
                    ManualIndex.load_or_build(root, root / "index", encoder=MockEncoder(), allow_build=False)
            ingest.assert_not_called()

    def test_explicit_cyberrow_dx_filters_cyberone_and_keeps_distinct_chunks(self) -> None:
        results = model_fixture().search("What are the electrical requirements for STULZ CyberRow DX?", top_k=3)
        self.assertEqual([result["page"] for result in results], [13, 18, 18])
        self.assertTrue(all(result["source_file"].endswith("QEWR002L.pdf") for result in results))
        self.assertEqual(len({result["chunk_id"] for result in results}), 3)
        self.assertTrue(all(set(result) == {"text", "source_file", "page", "chunk_id", "score"} for result in results))

    def test_missing_explicit_family_does_not_fall_back_to_other_models(self) -> None:
        fixture = model_fixture()
        one_chunks = fixture.chunks[:2]
        one_vectors = faiss.IndexFlatIP(2)
        vectors = np.asarray([[1.0, 0.0], [1.0, 0.0]], dtype=np.float32)
        one_vectors.add(vectors)
        only_cyberone = ManualIndex(one_vectors, one_chunks, FixedEncoder())
        self.assertEqual(only_cyberone.search("CyberRow DX electrical requirements"), [])

    def test_model_names_use_boundaries_and_keep_cw_distinct(self) -> None:
        fixture = model_fixture()
        self.assertEqual(
            [result["source_file"] for result in fixture.search("CyberOne DX electrical data", top_k=2)],
            ["STULZ CyberOne DX Engineering Manual.pdf"],
        )
        self.assertEqual(
            [result["page"] for result in fixture.search("CyberRow DX and CyberRow CW electrical data", top_k=2)],
            [17, 13],
        )
        self.assertEqual(
            fixture.search("CyberRow DX2 electrical data", top_k=1)[0]["source_file"],
            "STULZ CyberOne DX Engineering Manual.pdf",
        )

    def test_unspecified_model_keeps_global_ranking_but_deduplicates_pdfs(self) -> None:
        results = model_fixture().search("electrical data", top_k=3)
        self.assertEqual(
            [result["source_file"] for result in results],
            [
                "STULZ CyberOne DX Engineering Manual.pdf",
                "STULZ CyberRow CW Engineering Manual QEWR001G.pdf",
                "STULZ CyberRow DX Engineering Manual QEWR002L.pdf",
            ],
        )

    def test_index_encodes_in_batches(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            root = Path(temporary_dir)
            chunks = [
                {
                    "chunk_id": f"manual.pdf:p1:c{number}",
                    "text": f"pump section {number}",
                    "source_file": "manual.pdf",
                    "page": 1,
                }
                for number in range(33)
            ]
            encoder = MockEncoder()
            with patch("retrieval.ingest_pdfs", return_value=chunks):
                index = ManualIndex.load_or_build(root, root / "index", encoder=encoder)
            self.assertEqual([len(batch) for batch in encoder.calls], [32, 1])
            self.assertEqual(index.index.ntotal, 33)

    def test_search_and_cache_invalidation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            root = Path(temporary_dir)
            manuals = root / "manuals"
            manuals.mkdir()
            index_dir = root / "index"
            write_pdf(manuals / "pump.pdf", "pump pressure")
            write_pdf(manuals / "fan.pdf", "fan speed")

            first_encoder = MockEncoder()
            first = ManualIndex.load_or_build(manuals, index_dir, encoder=first_encoder)
            self.assertEqual(len(first_encoder.calls), 1)
            result = first.search("pump", top_k=1)[0]
            self.assertEqual(result["source_file"], "pump.pdf")
            self.assertEqual(result["page"], 1)
            self.assertEqual(result["text"], "pump pressure")
            self.assertEqual(result["chunk_id"], "pump.pdf:p1:c1")
            self.assertAlmostEqual(result["score"], 1.0)

            reused_encoder = MockEncoder()
            reused = ManualIndex.load_or_build(manuals, index_dir, encoder=reused_encoder)
            self.assertEqual(reused_encoder.calls, [])
            self.assertEqual(reused.search("pump", top_k=1)[0]["chunk_id"], "pump.pdf:p1:c1")

            write_pdf(manuals / "new.pdf", "pump maintenance")
            changed_encoder = MockEncoder()
            rebuilt = ManualIndex.load_or_build(manuals, index_dir, encoder=changed_encoder)
            self.assertEqual(len(changed_encoder.calls), 1)
            self.assertEqual(len(rebuilt.chunks), 3)

            new_model_encoder = MockEncoder()
            ManualIndex.load_or_build(
                manuals, index_dir, model_revision="different-revision", encoder=new_model_encoder
            )
            self.assertEqual(len(new_model_encoder.calls), 1)

    @unittest.skipUnless(os.environ.get("RUN_REAL_MODEL_SMOKE") == "1", "real model not requested")
    def test_real_model_smoke(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            root = Path(temporary_dir)
            manuals = root / "manuals"
            manuals.mkdir()
            write_pdf(manuals / "pump.pdf", "Pump pressure and flow rate")
            searcher = ManualIndex.load_or_build(manuals, root / "index")
            self.assertEqual(searcher.search("pump pressure", top_k=1)[0]["source_file"], "pump.pdf")


if __name__ == "__main__":
    unittest.main()
