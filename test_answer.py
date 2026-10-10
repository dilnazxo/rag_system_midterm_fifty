"""Mocked API tests for grounded answer generation."""

import json
import io
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from answer import ABSTENTION, answer_question, main
from openai import AuthenticationError


SOURCES = [
    {
        "text": "Inspect the pump seal every month.",
        "source_file": "pump.pdf",
        "page": 4,
        "chunk_id": "pump.pdf:p4:c1",
        "score": 0.81,
    },
    {
        "text": "The unit has a pressure gauge.",
        "source_file": "pump.pdf",
        "page": 5,
        "chunk_id": "pump.pdf:p5:c1",
        "score": 0.67,
    },
]

BOSCH_SOURCE = {
    "text": "GKS 65 GCE Professional\nRated power input\nW\n1600\n1600\n1800",
    "source_file": "gks_65_gce_professional.pdf",
    "page": 8,
    "chunk_id": "gks_65_gce_professional.pdf:p8:c4",
    "score": 0.9,
}


def mock_completion(answer: str, evidence_ids: list[int]) -> SimpleNamespace:
    content = json.dumps({"answer": answer, "evidence_ids": evidence_ids})
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


class AnswerTest(unittest.TestCase):
    def test_bosch_valid_json_answer_citing_evidence_one(self) -> None:
        index = MagicMock()
        index.search.return_value = [BOSCH_SOURCE]
        with (
            patch("answer.OpenAI") as client_class,
            patch.dict(os.environ, {"OPENAI_API_KEY": "test", "OPENAI_MODEL": "test"}),
        ):
            client_class.return_value.chat.completions.create.return_value = mock_completion(
                "The rated power input is 1800 W [1].", [1]
            )
            result = answer_question(
                "What is the rated power input of the Bosch GKS 65 GCE Professional?",
                manual_index=index,
            )
        self.assertEqual(result["answer"], "The rated power input is 1800 W [1].")
        self.assertEqual(result["cited_evidence_ids"], [1])

    def test_bosch_cited_plain_text_response(self) -> None:
        index = MagicMock()
        index.search.return_value = [BOSCH_SOURCE]
        content = "The rated power input is 1800 W [1]."
        with (
            patch("answer.OpenAI") as client_class,
            patch.dict(os.environ, {"OPENAI_API_KEY": "test", "OPENAI_MODEL": "test"}),
        ):
            client_class.return_value.chat.completions.create.return_value = SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
            )
            result = answer_question(
                "What is the rated power input of the Bosch GKS 65 GCE Professional?",
                manual_index=index,
            )
        self.assertEqual(result["answer"], content)
        self.assertEqual(result["cited_evidence_ids"], [1])

    def test_plain_text_requires_a_valid_supplied_citation(self) -> None:
        index = MagicMock()
        index.search.return_value = [BOSCH_SOURCE]
        for content in ("The rated power input is 1800 W.", "The rated power input is 1800 W [2].", "The rated power input is 1800 W [1."):
            with self.subTest(content=content):
                with (
                    patch("answer.OpenAI") as client_class,
                    patch.dict(os.environ, {"OPENAI_API_KEY": "test", "OPENAI_MODEL": "test"}),
                ):
                    client_class.return_value.chat.completions.create.return_value = SimpleNamespace(
                        choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
                    )
                    with self.assertRaises(ValueError):
                        answer_question("What is the rated power input of the Bosch GKS 65 GCE Professional?", manual_index=index)

    def test_supplied_index_avoids_reloading_the_saved_index(self) -> None:
        index = MagicMock()
        index.search.return_value = SOURCES
        with (
            patch("answer.ManualIndex.load_or_build") as load,
            patch("answer.OpenAI") as client_class,
            patch.dict(os.environ, {"OPENAI_API_KEY": "test", "OPENAI_MODEL": "test"}),
        ):
            client_class.return_value.chat.completions.create.return_value = mock_completion(
                "Inspect the pump seal every month [1].", [1]
            )
            result = answer_question("Pump seal?", manual_index=index)
        load.assert_not_called()
        index.search.assert_called_once_with("Pump seal?", top_k=5)
        self.assertEqual(result["cited_evidence_ids"], [1])

    def test_cli_401_does_not_print_exception_or_key(self) -> None:
        response = MagicMock()
        response.status_code = 401
        response.headers = {}
        error = AuthenticationError(
            "Incorrect API key: test-secret-must-not-print",
            response=response,
            body={"code": "invalid_api_key"},
        )
        output = io.StringIO()
        with (
            patch("answer.answer_question", side_effect=error),
            patch("sys.stderr", output),
            patch.dict(os.environ, {}, clear=True),
            self.assertRaises(SystemExit) as exit_result,
        ):
            main(["--question", "Pressure rating?"])

        self.assertEqual(exit_result.exception.code, 1)
        self.assertIn("project-root .env", output.getvalue())
        self.assertNotIn("test-secret-must-not-print", output.getvalue())

    def test_cli_prints_only_cited_source_filename_and_page(self) -> None:
        result = {
            "answer": "The unit has a pressure gauge [2].",
            "sources": SOURCES,
            "cited_evidence_ids": [2],
        }
        output = io.StringIO()
        with patch("answer.answer_question", return_value=result) as ask, patch("sys.stdout", output):
            main(["--question", "Does the unit have a pressure gauge?"])

        ask.assert_called_once_with("Does the unit have a pressure gauge?")
        self.assertEqual(
            output.getvalue(),
            "The unit has a pressure gauge [2].\n[2] pump.pdf, page 5\n",
        )

    def test_answer_uses_retrieved_evidence_and_api_config(self) -> None:
        index = MagicMock()
        index.search.return_value = SOURCES
        with (
            patch("answer.ManualIndex.load_or_build", return_value=index),
            patch("answer.OpenAI") as client_class,
            patch.dict(
                os.environ,
                {
                    "OPENAI_API_KEY": "test-only-key",
                    "OPENAI_MODEL": "test-model",
                    "OPENAI_BASE_URL": "https://example.test/v1",
                },
            ),
        ):
            client_class.return_value.chat.completions.create.return_value = mock_completion(
                "Inspect the pump seal every month [1].", [1]
            )
            result = answer_question("How often should the pump seal be inspected?")

        index.search.assert_called_once_with("How often should the pump seal be inspected?", top_k=5)
        client_class.assert_called_once_with(
            api_key="test-only-key", base_url="https://example.test/v1"
        )
        request = client_class.return_value.chat.completions.create.call_args.kwargs
        self.assertEqual(request["model"], "test-model")
        self.assertIn("Evidence [1]", request["messages"][1]["content"])
        self.assertIn("source_file: \"pump.pdf\"", request["messages"][1]["content"])
        self.assertIn("page: 4", request["messages"][1]["content"])
        self.assertIn("chunk_id: \"pump.pdf:p4:c1\"", request["messages"][1]["content"])
        self.assertEqual(result["sources"], SOURCES)
        self.assertEqual(result["cited_evidence_ids"], [1])

    def test_unknown_evidence_id_is_rejected(self) -> None:
        index = MagicMock()
        index.search.return_value = SOURCES
        with (
            patch("answer.ManualIndex.load_or_build", return_value=index),
            patch("answer.OpenAI") as client_class,
            patch.dict(os.environ, {"OPENAI_API_KEY": "test", "OPENAI_MODEL": "test"}),
        ):
            client_class.return_value.chat.completions.create.return_value = mock_completion(
                "Unsupported claim [3].", [3]
            )
            with self.assertRaisesRegex(ValueError, "unknown evidence ID"):
                answer_question("Question")

    def test_answer_and_evidence_ids_must_match(self) -> None:
        index = MagicMock()
        index.search.return_value = SOURCES
        with (
            patch("answer.ManualIndex.load_or_build", return_value=index),
            patch("answer.OpenAI") as client_class,
            patch.dict(os.environ, {"OPENAI_API_KEY": "test", "OPENAI_MODEL": "test"}),
        ):
            client_class.return_value.chat.completions.create.return_value = mock_completion(
                "Inspect the seal [1].", [2]
            )
            with self.assertRaisesRegex(ValueError, "citations differ"):
                answer_question("Question")

    def test_uncited_answer_becomes_abstention(self) -> None:
        index = MagicMock()
        index.search.return_value = SOURCES
        with (
            patch("answer.ManualIndex.load_or_build", return_value=index),
            patch("answer.OpenAI") as client_class,
            patch.dict(os.environ, {"OPENAI_API_KEY": "test", "OPENAI_MODEL": "test"}),
        ):
            client_class.return_value.chat.completions.create.return_value = mock_completion(
                "The pump requires 50 bar.", []
            )
            result = answer_question("Pressure?")
        self.assertEqual(result["answer"], ABSTENTION)
        self.assertEqual(result["cited_evidence_ids"], [])
        self.assertEqual(result["sources"], SOURCES)

    def test_empty_search_skips_api(self) -> None:
        index = MagicMock()
        index.search.return_value = []
        with (
            patch("answer.ManualIndex.load_or_build", return_value=index),
            patch("answer.OpenAI") as client_class,
        ):
            result = answer_question("Unknown question")
        client_class.assert_not_called()
        self.assertEqual(result, {"answer": ABSTENTION, "sources": [], "cited_evidence_ids": []})

    def test_missing_configuration_does_not_call_api(self) -> None:
        index = MagicMock()
        index.search.return_value = SOURCES
        with (
            patch("answer.ManualIndex.load_or_build", return_value=index),
            patch("answer.OpenAI") as client_class,
            patch("answer.load_dotenv"),
            patch.dict(os.environ, {}, clear=True),
        ):
            with self.assertRaisesRegex(RuntimeError, "OPENAI_API_KEY and OPENAI_MODEL"):
                answer_question("Question")
        client_class.assert_not_called()

    def test_project_root_dotenv_loads_without_overriding_environment(self) -> None:
        index = MagicMock()
        index.search.return_value = SOURCES
        with tempfile.TemporaryDirectory() as temporary_dir:
            project_root = Path(temporary_dir)
            (project_root / ".env").write_text(
                "OPENAI_API_KEY=file-only-key\n"
                "OPENAI_MODEL=file-only-model\n",
                encoding="utf-8",
            )
            with (
                patch("answer.__file__", str(project_root / "answer.py")),
                patch("answer.ManualIndex.load_or_build", return_value=index),
                patch("answer.OpenAI") as client_class,
                patch.dict(os.environ, {"OPENAI_API_KEY": "environment-key"}, clear=True),
            ):
                client_class.return_value.chat.completions.create.return_value = mock_completion(
                    "Inspect the pump seal every month [1].", [1]
                )
                answer_question("How often should the pump seal be inspected?")

        client_class.assert_called_once_with(api_key="environment-key")
        self.assertEqual(
            client_class.return_value.chat.completions.create.call_args.kwargs["model"],
            "file-only-model",
        )


if __name__ == "__main__":
    unittest.main()
