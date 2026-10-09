"""Local tests for the Streamlit app without starting a server or calling OpenAI."""

import importlib
import sys
import types
import unittest
from unittest.mock import MagicMock, call, patch

from answer import ABSTENTION


fake_streamlit = types.ModuleType("streamlit")
fake_streamlit.cache_resource = lambda **kwargs: lambda function: function
with patch.dict(sys.modules, {"streamlit": fake_streamlit}):
    app = importlib.import_module("app")


SOURCE = {
    "text": "Control circuit wiring shall be at least 18 AWG.",
    "source_file": "STULZ CyberRow DX Engineering Manual QEWR002L.pdf",
    "page": 18,
    "chunk_id": "STULZ CyberRow DX Engineering Manual QEWR002L.pdf:p18:c3",
    "score": 0.61,
}


class AppTest(unittest.TestCase):
    def test_cached_loader_uses_only_the_saved_index(self) -> None:
        sentinel = object()
        with patch.object(app.ManualIndex, "load_or_build", return_value=sentinel) as load:
            self.assertIs(app.get_index(), sentinel)
        self.assertEqual(load.call_args.kwargs["allow_build"], False)
        self.assertEqual(load.call_args.kwargs["index_dir"], app.PROJECT_ROOT / "data" / "index")

    def test_retrieval_only_never_calls_answer_question(self) -> None:
        index = MagicMock()
        index.search.return_value = [SOURCE]
        with patch.object(app, "answer_question") as answer:
            reply = app.respond("CyberRow DX wiring?", app.RETRIEVAL_ONLY, index)
        index.search.assert_called_once_with("CyberRow DX wiring?", top_k=5)
        answer.assert_not_called()
        self.assertEqual(reply["sources"], [SOURCE])
        self.assertEqual(reply["cited_evidence_ids"], [])

    def test_rag_uses_cached_index_and_preserves_citations(self) -> None:
        index = MagicMock()
        result = {"answer": "Use 18 AWG [1].", "sources": [SOURCE], "cited_evidence_ids": [1]}
        with patch.object(app, "answer_question", return_value=result) as answer:
            reply = app.respond("CyberRow DX wiring?", app.RAG_ANSWER, index)
        answer.assert_called_once_with("CyberRow DX wiring?", manual_index=index)
        self.assertEqual(reply["content"], result["answer"])
        self.assertEqual(reply["cited_evidence_ids"], [1])

    def test_no_manual_and_insufficient_evidence_are_friendly(self) -> None:
        index = MagicMock()
        index.search.return_value = []
        self.assertIn("No matching manual", app.respond("Unknown model", app.RETRIEVAL_ONLY, index)["content"])
        with patch.object(
            app, "answer_question",
            return_value={"answer": ABSTENTION, "sources": [SOURCE], "cited_evidence_ids": []},
        ):
            reply = app.respond("CyberRow DX wiring?", app.RAG_ANSWER, index)
        self.assertEqual(reply["status"], "warning")
        self.assertIn("not contain enough information", reply["content"])
        self.assertEqual(reply["sources"], [SOURCE])

    def test_reply_shows_citation_and_evidence_details(self) -> None:
        reply = {"content": "Use 18 AWG [1].", "sources": [SOURCE], "cited_evidence_ids": [1], "status": "normal"}
        with patch.object(app, "st") as ui:
            app.render_reply(reply)
        self.assertIn(call("[1] STULZ CyberRow DX Engineering Manual QEWR002L.pdf, page 18"), ui.write.call_args_list)
        self.assertIn(call(SOURCE["text"]), ui.write.call_args_list)
        self.assertIn(call("Chunk: STULZ CyberRow DX Engineering Manual QEWR002L.pdf:p18:c3 · Similarity: 0.6100"), ui.caption.call_args_list)


if __name__ == "__main__":
    unittest.main()
