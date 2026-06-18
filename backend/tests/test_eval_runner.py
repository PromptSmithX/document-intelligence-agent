from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUN_EVAL_PATH = ROOT / "eval" / "run_eval.py"
SPEC = importlib.util.spec_from_file_location("run_eval", RUN_EVAL_PATH)
run_eval = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(run_eval)


class FakeBackendClient:
    def __init__(self, fail_search: bool = False) -> None:
        self.fail_search = fail_search
        self.uploads: list[Path] = []
        self.search_calls: list[tuple[str, str, int]] = []
        self.chat_calls: list[tuple[str, str, int]] = []

    def upload_document(self, pdf_path: Path) -> dict:
        self.uploads.append(pdf_path)
        return {"document_id": "doc_fake"}

    def search(self, document_id: str, question: str, top_k: int) -> dict:
        if self.fail_search:
            raise RuntimeError("backend search failed")
        self.search_calls.append((document_id, question, top_k))
        return {
            "results": [
                {
                    "chunk_id": "doc_fake_chunk_0000",
                    "document_id": document_id,
                    "page": 1,
                    "chunk_index": 0,
                    "score": 0.91,
                    "content": "Approved invoices are due within 45 calendar days in USD.",
                }
            ]
        }

    def chat(self, document_id: str, question: str, top_k: int) -> dict:
        self.chat_calls.append((document_id, question, top_k))
        return {
            "answer": "Approved invoices are due within 45 calendar days in USD.",
            "citations": [{"page": 1, "chunk_id": "doc_fake_chunk_0000", "score": 0.91}],
            "latency_seconds": 0.42,
        }


class EvalRunnerTests(unittest.TestCase):
    def test_compute_retrieval_metrics_hit_and_mrr(self) -> None:
        metrics = run_eval.compute_retrieval_metrics(
            [
                {"page": 3, "score": 0.89},
                {"page": 1, "score": 0.75},
            ],
            [1],
        )

        self.assertTrue(metrics["hit"])
        self.assertEqual(metrics["first_relevant_rank"], 2)
        self.assertEqual(metrics["mrr"], 0.5)
        self.assertEqual(metrics["top_score"], 0.89)

    def test_answer_metrics_for_answerable_checks_terms_and_citations(self) -> None:
        case = {
            "answerable": True,
            "expected_pages": [1],
            "required_terms": ["45 calendar days", "USD"],
        }
        metrics = run_eval.compute_answer_metrics(
            case,
            {
                "answer": "Invoices are paid within 45 calendar days in USD.",
                "citations": [{"page": 1}],
                "latency_seconds": 1.2,
            },
        )

        self.assertTrue(metrics["answer_pass"])
        self.assertTrue(metrics["answer_term_pass"])
        self.assertTrue(metrics["citation_page_pass"])
        self.assertEqual(metrics["latency_seconds"], 1.2)

    def test_no_answer_policy_accepts_near_match(self) -> None:
        self.assertTrue(
            run_eval.is_no_answer("This information is not provided in the document.")
        )

    def test_dataset_validation_rejects_missing_required_field(self) -> None:
        with self.assertRaisesRegex(ValueError, "question"):
            run_eval.validate_dataset(
                {
                    "dataset_name": "bad",
                    "document_path": "sample.pdf",
                    "cases": [
                        {
                            "id": "case_1",
                            "answerable": True,
                            "expected_answer": "Answer",
                            "expected_pages": [1],
                            "required_terms": ["Answer"],
                        }
                    ],
                },
                ROOT / "eval" / "questions.json",
            )

    def test_dataset_validation_rejects_empty_expected_pages_for_answerable(self) -> None:
        with self.assertRaisesRegex(ValueError, "expected_pages"):
            run_eval.validate_dataset(
                {
                    "dataset_name": "bad",
                    "document_path": "sample.pdf",
                    "cases": [
                        {
                            "id": "case_1",
                            "question": "Question?",
                            "answerable": True,
                            "expected_answer": "Answer",
                            "expected_pages": [],
                            "required_terms": ["Answer"],
                        }
                    ],
                },
                ROOT / "eval" / "questions.json",
            )

    def test_dataset_validation_rejects_required_terms_wrong_type(self) -> None:
        with self.assertRaisesRegex(ValueError, "required_terms"):
            run_eval.validate_dataset(
                {
                    "dataset_name": "bad",
                    "document_path": "sample.pdf",
                    "cases": [
                        {
                            "id": "case_1",
                            "question": "Question?",
                            "answerable": True,
                            "expected_answer": "Answer",
                            "expected_pages": [1],
                            "required_terms": "Answer",
                        }
                    ],
                },
                ROOT / "eval" / "questions.json",
            )

    def test_run_evaluation_uploads_and_scores_case(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            pdf_path = Path(tmp_dir) / "sample.pdf"
            pdf_path.write_bytes(b"%PDF-1.4\n")
            dataset = self._dataset(pdf_path)
            client = FakeBackendClient()

            report = run_eval.run_evaluation(dataset, client, top_k=5)

        self.assertEqual(report["run"]["document_id"], "doc_fake")
        self.assertEqual(len(client.uploads), 1)
        self.assertEqual(report["aggregate"]["hit_at_5"], 1.0)
        self.assertEqual(report["aggregate"]["answer_pass_rate"], 1.0)
        self.assertEqual(report["aggregate"]["citation_pass_rate"], 1.0)

    def test_run_evaluation_with_document_id_skips_upload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            pdf_path = Path(tmp_dir) / "sample.pdf"
            pdf_path.write_bytes(b"%PDF-1.4\n")
            dataset = self._dataset(pdf_path)
            client = FakeBackendClient()

            report = run_eval.run_evaluation(
                dataset,
                client,
                top_k=3,
                document_id="doc_existing",
            )

        self.assertEqual(report["run"]["document_id"], "doc_existing")
        self.assertEqual(client.uploads, [])
        self.assertEqual(client.search_calls[0][0], "doc_existing")
        self.assertIn("hit_at_3", report["aggregate"])

    def test_backend_error_is_reported_per_case(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            pdf_path = Path(tmp_dir) / "sample.pdf"
            pdf_path.write_bytes(b"%PDF-1.4\n")
            dataset = self._dataset(pdf_path)
            client = FakeBackendClient(fail_search=True)

            report = run_eval.run_evaluation(dataset, client, top_k=5)
            markdown = run_eval.render_markdown(report)

        self.assertEqual(report["aggregate"]["error_cases"], 1)
        self.assertEqual(report["cases"][0]["status"], "error")
        self.assertIn("backend search failed", markdown)

    def test_ci_failures_detect_threshold_miss(self) -> None:
        report = {
            "run": {"top_k": 5},
            "aggregate": {
                "error_cases": 0,
                "hit_at_5": 0.5,
                "answer_pass_rate": 0.7,
                "citation_pass_rate": 0.6,
            },
        }

        failures = run_eval.ci_failures(report)

        self.assertEqual(len(failures), 3)

    def _dataset(self, pdf_path: Path) -> dict:
        return {
            "dataset_name": "test_dataset",
            "document_path": str(pdf_path),
            "document_path_resolved": str(pdf_path),
            "cases": [
                {
                    "id": "payment_terms",
                    "question": "When are invoices due?",
                    "answerable": True,
                    "expected_answer": "Invoices are due within 45 calendar days in USD.",
                    "expected_pages": [1],
                    "required_terms": ["45 calendar days", "USD"],
                }
            ],
        }


if __name__ == "__main__":
    unittest.main()
