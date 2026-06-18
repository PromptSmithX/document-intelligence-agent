from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
import sys
import uuid
from pathlib import Path
from typing import Any
from urllib import error, request


NO_ANSWER = "I could not find this information in the document."
DEFAULT_BACKEND_URL = "http://localhost:8000"
DEFAULT_DATASET = "eval/questions.json"
DEFAULT_TOP_K = 5
DEFAULT_RESULTS_MD = "eval/results.md"
DEFAULT_RESULTS_JSON = "eval/results.json"
DEFAULT_JUDGE_MODEL = "gemini-1.5-flash"
CI_HIT_THRESHOLD = 0.8
CI_ANSWER_THRESHOLD = 0.8
CI_CITATION_THRESHOLD = 0.8


class EvalError(RuntimeError):
    """Raised when evaluation cannot continue."""


class BackendClient:
    def __init__(self, backend_url: str, timeout: int = 300) -> None:
        self.backend_url = backend_url.rstrip("/")
        self.timeout = timeout

    def upload_document(self, pdf_path: Path) -> dict[str, Any]:
        boundary = f"----doc-intel-eval-{uuid.uuid4().hex}"
        pdf_bytes = pdf_path.read_bytes()
        filename = pdf_path.name
        body = b"".join(
            [
                f"--{boundary}\r\n".encode("utf-8"),
                (
                    'Content-Disposition: form-data; name="file"; '
                    f'filename="{filename}"\r\n'
                ).encode("utf-8"),
                b"Content-Type: application/pdf\r\n\r\n",
                pdf_bytes,
                b"\r\n",
                f"--{boundary}--\r\n".encode("utf-8"),
            ]
        )
        return self._request(
            "POST",
            "/documents/upload",
            body=body,
            headers={
                "Content-Type": f"multipart/form-data; boundary={boundary}",
                "Content-Length": str(len(body)),
            },
        )

    def search(self, document_id: str, question: str, top_k: int) -> dict[str, Any]:
        return self._request_json(
            "POST",
            "/documents/search",
            {
                "document_id": document_id,
                "query": question,
                "top_k": top_k,
            },
        )

    def chat(self, document_id: str, question: str, top_k: int) -> dict[str, Any]:
        return self._request_json(
            "POST",
            "/chat/query",
            {
                "document_id": document_id,
                "question": question,
                "top_k": top_k,
            },
        )

    def _request_json(
        self,
        method: str,
        path: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        body = json.dumps(payload).encode("utf-8")
        return self._request(
            method,
            path,
            body=body,
            headers={
                "Content-Type": "application/json",
                "Content-Length": str(len(body)),
            },
        )

    def _request(
        self,
        method: str,
        path: str,
        body: bytes | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        url = f"{self.backend_url}{path}"
        req = request.Request(url, data=body, headers=headers or {}, method=method)

        try:
            with request.urlopen(req, timeout=self.timeout) as response:
                raw_body = response.read().decode("utf-8")
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise EvalError(f"{method} {path} failed with HTTP {exc.code}: {detail}") from exc
        except error.URLError as exc:
            raise EvalError(f"{method} {path} failed: {exc.reason}") from exc

        try:
            parsed = json.loads(raw_body)
        except json.JSONDecodeError as exc:
            raise EvalError(f"{method} {path} returned invalid JSON: {raw_body}") from exc

        if not isinstance(parsed, dict):
            raise EvalError(f"{method} {path} returned non-object JSON")
        return parsed


def load_dataset(dataset_path: str | Path) -> dict[str, Any]:
    path = Path(dataset_path)
    try:
        raw_dataset = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"Dataset file does not exist: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Dataset file is not valid JSON: {path}") from exc

    return validate_dataset(raw_dataset, path)


def validate_dataset(raw_dataset: dict[str, Any], dataset_path: Path) -> dict[str, Any]:
    if not isinstance(raw_dataset, dict):
        raise ValueError("Dataset must be a JSON object")

    dataset_name = _required_string(raw_dataset, "dataset_name", "dataset")
    document_path = _required_string(raw_dataset, "document_path", "dataset")
    raw_cases = raw_dataset.get("cases")
    if not isinstance(raw_cases, list) or not raw_cases:
        raise ValueError("dataset.cases must be a non-empty list")

    seen_ids: set[str] = set()
    cases = []
    for index, raw_case in enumerate(raw_cases):
        where = f"cases[{index}]"
        if not isinstance(raw_case, dict):
            raise ValueError(f"{where} must be an object")

        case_id = _required_string(raw_case, "id", where)
        if case_id in seen_ids:
            raise ValueError(f"{where}.id must be unique: {case_id}")
        seen_ids.add(case_id)

        question = _required_string(raw_case, "question", where)
        expected_answer = _required_string(raw_case, "expected_answer", where)
        answerable = raw_case.get("answerable")
        if not isinstance(answerable, bool):
            raise ValueError(f"{where}.answerable must be a boolean")

        expected_pages = _required_int_list(raw_case, "expected_pages", where)
        required_terms = _required_string_list(raw_case, "required_terms", where)

        if answerable and not expected_pages:
            raise ValueError(f"{where}.expected_pages must be non-empty when answerable")
        if answerable and not required_terms:
            raise ValueError(f"{where}.required_terms must be non-empty when answerable")
        if not answerable and expected_pages:
            raise ValueError(f"{where}.expected_pages must be empty when unanswerable")

        cases.append(
            {
                "id": case_id,
                "question": question,
                "answerable": answerable,
                "expected_answer": expected_answer,
                "expected_pages": expected_pages,
                "required_terms": required_terms,
            }
        )

    return {
        "dataset_name": dataset_name,
        "document_path": document_path,
        "document_path_resolved": str(resolve_document_path(document_path, dataset_path)),
        "cases": cases,
    }


def resolve_document_path(document_path: str, dataset_path: Path) -> Path:
    raw_path = Path(document_path)
    if raw_path.is_absolute():
        return raw_path

    candidates = [
        Path.cwd() / raw_path,
        dataset_path.parent / raw_path,
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()

    return candidates[0].resolve()


def _required_string(payload: dict[str, Any], key: str, where: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{where}.{key} must be a non-empty string")
    return value.strip()


def _required_int_list(payload: dict[str, Any], key: str, where: str) -> list[int]:
    value = payload.get(key)
    if not isinstance(value, list):
        raise ValueError(f"{where}.{key} must be a list")

    result = []
    for item in value:
        if isinstance(item, bool) or not isinstance(item, int) or item <= 0:
            raise ValueError(f"{where}.{key} must contain positive integers")
        result.append(item)
    return result


def _required_string_list(payload: dict[str, Any], key: str, where: str) -> list[str]:
    value = payload.get(key)
    if not isinstance(value, list):
        raise ValueError(f"{where}.{key} must be a list")

    result = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"{where}.{key} must contain non-empty strings")
        result.append(item.strip())
    return result


def normalize_text(value: str) -> str:
    return " ".join(str(value or "").lower().split())


def contains_required_terms(answer: str, required_terms: list[str]) -> bool:
    normalized_answer = normalize_text(answer)
    return all(normalize_text(term) in normalized_answer for term in required_terms)


def is_no_answer(answer: str) -> bool:
    normalized = normalize_text(answer)
    if normalized == normalize_text(NO_ANSWER):
        return True

    no_answer_markers = (
        "could not find",
        "cannot find",
        "not found",
        "not provided",
        "not available",
        "not in the context",
        "not in the document",
    )
    has_marker = any(marker in normalized for marker in no_answer_markers)
    has_scope = "document" in normalized or "context" in normalized
    return has_marker and has_scope


def compute_retrieval_metrics(
    search_results: list[dict[str, Any]],
    expected_pages: list[int],
) -> dict[str, Any]:
    expected_page_set = set(expected_pages)
    retrieved_pages = [_safe_int(result.get("page")) for result in search_results]
    first_relevant_rank = None
    for index, page in enumerate(retrieved_pages, start=1):
        if page in expected_page_set:
            first_relevant_rank = index
            break

    return {
        "hit": first_relevant_rank is not None,
        "mrr": 1 / first_relevant_rank if first_relevant_rank else 0.0,
        "first_relevant_rank": first_relevant_rank,
        "top_score": _safe_float(search_results[0].get("score"), 0.0)
        if search_results
        else 0.0,
        "retrieved_pages": retrieved_pages,
    }


def compute_answer_metrics(
    case: dict[str, Any],
    chat_response: dict[str, Any],
) -> dict[str, Any]:
    answer = str(chat_response.get("answer") or "")
    citations = chat_response.get("citations") or []
    if not isinstance(citations, list):
        citations = []

    citation_pages = [_safe_int(citation.get("page")) for citation in citations]
    citation_pages = [page for page in citation_pages if page is not None]
    latency_seconds = _safe_float(chat_response.get("latency_seconds"), None)

    if case["answerable"]:
        answer_term_pass = contains_required_terms(answer, case["required_terms"])
        citation_page_pass = bool(set(citation_pages) & set(case["expected_pages"]))
        no_answer_pass = None
        answer_pass = answer_term_pass
    else:
        answer_term_pass = None
        citation_page_pass = None
        no_answer_pass = is_no_answer(answer)
        answer_pass = no_answer_pass

    return {
        "answer": answer,
        "answer_pass": answer_pass,
        "answer_term_pass": answer_term_pass,
        "no_answer_pass": no_answer_pass,
        "citation_page_pass": citation_page_pass,
        "latency_seconds": latency_seconds,
        "citation_pages": citation_pages,
        "citation_count": len(citations),
    }


def run_evaluation(
    dataset: dict[str, Any],
    client: BackendClient,
    top_k: int = DEFAULT_TOP_K,
    document_id: str | None = None,
    judge_enabled: bool = False,
    judge_model: str = DEFAULT_JUDGE_MODEL,
) -> dict[str, Any]:
    warnings: list[str] = []
    pdf_path = Path(dataset["document_path_resolved"])

    if document_id:
        resolved_document_id = document_id
        upload_response: dict[str, Any] | None = None
    else:
        if not pdf_path.exists():
            raise EvalError(f"Document path does not exist: {pdf_path}")
        upload_response = client.upload_document(pdf_path)
        resolved_document_id = str(upload_response.get("document_id") or "").strip()
        if not resolved_document_id:
            raise EvalError("Upload response did not include document_id")

    use_judge = judge_enabled and bool(os.getenv("GEMINI_API_KEY", "").strip())
    if judge_enabled and not use_judge:
        warnings.append("--judge was requested but GEMINI_API_KEY is not set; skipping LLM judge.")

    case_results = []
    for case in dataset["cases"]:
        case_result = {
            "id": case["id"],
            "question": case["question"],
            "answerable": case["answerable"],
            "expected_answer": case["expected_answer"],
            "expected_pages": case["expected_pages"],
            "required_terms": case["required_terms"],
            "status": "ok",
        }

        try:
            search_response = client.search(resolved_document_id, case["question"], top_k)
            search_results = _extract_results(search_response)
            chat_response = client.chat(resolved_document_id, case["question"], top_k)
            retrieval_metrics = compute_retrieval_metrics(
                search_results,
                case["expected_pages"],
            )
            answer_metrics = compute_answer_metrics(case, chat_response)

            case_result["retrieval"] = retrieval_metrics
            case_result["answer"] = answer_metrics

            if use_judge:
                case_result["judge"] = judge_answer(
                    case,
                    search_results,
                    chat_response,
                    judge_model,
                )
        except Exception as exc:  # Keep the report useful across partial backend failures.
            case_result["status"] = "error"
            case_result["error"] = str(exc)

        case_results.append(case_result)

    report = {
        "run": {
            "generated_at": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
            "dataset_name": dataset["dataset_name"],
            "document_path": dataset["document_path"],
            "document_id": resolved_document_id,
            "top_k": top_k,
            "judge_enabled": use_judge,
            "upload_response": upload_response,
            "warnings": warnings,
        },
        "aggregate": aggregate_results(case_results, top_k),
        "cases": case_results,
    }
    return report


def _extract_results(search_response: dict[str, Any]) -> list[dict[str, Any]]:
    results = search_response.get("results")
    if not isinstance(results, list):
        raise EvalError("Search response did not include results list")
    return [result for result in results if isinstance(result, dict)]


def judge_answer(
    case: dict[str, Any],
    search_results: list[dict[str, Any]],
    chat_response: dict[str, Any],
    judge_model: str,
) -> dict[str, Any]:
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        return {"error": "GEMINI_API_KEY is not set"}

    try:
        from google import genai
    except ImportError as exc:
        return {"error": f"google-genai is not installed: {exc}"}

    prompt = f"""You are grading a RAG answer.
Return strict JSON with integer scores from 0 to 2:
correctness, groundedness, citation_support, and a short rationale.

Question: {case["question"]}
Expected answer: {case["expected_answer"]}
Expected pages: {case["expected_pages"]}
Actual answer: {chat_response.get("answer", "")}
Citations: {json.dumps(chat_response.get("citations", []), ensure_ascii=True)}
Retrieved chunks: {json.dumps(search_results, ensure_ascii=True)}
"""

    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(model=judge_model, contents=prompt)
        payload = _parse_json_object(response.text or "")
        return {
            "correctness": _clamp_score(payload.get("correctness")),
            "groundedness": _clamp_score(payload.get("groundedness")),
            "citation_support": _clamp_score(payload.get("citation_support")),
            "rationale": str(payload.get("rationale") or "").strip(),
        }
    except Exception as exc:
        return {"error": str(exc)}


def _parse_json_object(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`")
        if stripped.startswith("json"):
            stripped = stripped[4:].strip()

    start = stripped.find("{")
    end = stripped.rfind("}")
    if start != -1 and end != -1 and end > start:
        stripped = stripped[start : end + 1]

    parsed = json.loads(stripped)
    if not isinstance(parsed, dict):
        raise ValueError("Judge response must be a JSON object")
    return parsed


def _clamp_score(value: Any) -> int:
    try:
        score = int(value)
    except (TypeError, ValueError):
        return 0
    return max(0, min(2, score))


def aggregate_results(case_results: list[dict[str, Any]], top_k: int) -> dict[str, Any]:
    total_cases = len(case_results)
    error_cases = [result for result in case_results if result["status"] != "ok"]
    answerable_cases = [result for result in case_results if result["answerable"]]
    unanswerable_cases = [result for result in case_results if not result["answerable"]]
    ok_cases = [result for result in case_results if result["status"] == "ok"]
    ok_answerable = [result for result in ok_cases if result["answerable"]]
    ok_unanswerable = [result for result in ok_cases if not result["answerable"]]

    top_scores = [
        result["retrieval"]["top_score"]
        for result in ok_cases
        if "retrieval" in result
    ]
    latencies = [
        result["answer"]["latency_seconds"]
        for result in ok_cases
        if result.get("answer", {}).get("latency_seconds") is not None
    ]

    answer_pass_count = sum(
        1 for result in ok_cases if result.get("answer", {}).get("answer_pass") is True
    )

    judge_scores = _aggregate_judge_scores(ok_cases)

    return {
        "total_cases": total_cases,
        "successful_cases": len(ok_cases),
        "error_cases": len(error_cases),
        "answerable_cases": len(answerable_cases),
        "unanswerable_cases": len(unanswerable_cases),
        f"hit_at_{top_k}": _safe_rate(
            sum(1 for result in ok_answerable if result["retrieval"]["hit"]),
            len(answerable_cases),
        ),
        f"mrr_at_{top_k}": _safe_rate(
            sum(result["retrieval"]["mrr"] for result in ok_answerable),
            len(answerable_cases),
        ),
        "avg_top_score": _average(top_scores),
        "answer_pass_rate": _safe_rate(answer_pass_count, total_cases),
        "answer_term_pass_rate": _safe_rate(
            sum(
                1
                for result in ok_answerable
                if result["answer"]["answer_term_pass"] is True
            ),
            len(answerable_cases),
        ),
        "no_answer_pass_rate": _safe_rate(
            sum(
                1
                for result in ok_unanswerable
                if result["answer"]["no_answer_pass"] is True
            ),
            len(unanswerable_cases),
        ),
        "citation_pass_rate": _safe_rate(
            sum(
                1
                for result in ok_answerable
                if result["answer"]["citation_page_pass"] is True
            ),
            len(answerable_cases),
        ),
        "latency_avg": _average(latencies),
        "latency_p50": percentile(latencies, 50),
        "latency_p95": percentile(latencies, 95),
        "judge": judge_scores,
    }


def _aggregate_judge_scores(case_results: list[dict[str, Any]]) -> dict[str, float] | None:
    score_names = ("correctness", "groundedness", "citation_support")
    scored_cases = [
        result["judge"]
        for result in case_results
        if isinstance(result.get("judge"), dict)
        and all(isinstance(result["judge"].get(name), int) for name in score_names)
    ]
    if not scored_cases:
        return None

    return {
        name: _average([score[name] for score in scored_cases])
        for name in score_names
    }


def _safe_rate(numerator: float, denominator: int) -> float | None:
    if denominator == 0:
        return None
    return numerator / denominator


def _average(values: list[float | int]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def percentile(values: list[float], percentile_value: int) -> float | None:
    if not values:
        return None
    sorted_values = sorted(values)
    index = math.ceil((percentile_value / 100) * len(sorted_values)) - 1
    index = max(0, min(index, len(sorted_values) - 1))
    return sorted_values[index]


def _safe_int(value: Any) -> int | None:
    try:
        if isinstance(value, bool):
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _safe_float(value: Any, default: float | None) -> float | None:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def render_markdown(report: dict[str, Any]) -> str:
    run = report["run"]
    aggregate = report["aggregate"]
    top_k = run["top_k"]
    hit_key = f"hit_at_{top_k}"
    mrr_key = f"mrr_at_{top_k}"

    lines = [
        "# Evaluation Results",
        "",
        f"- Generated at: `{run['generated_at']}`",
        f"- Dataset: `{run['dataset_name']}`",
        f"- Document ID: `{run['document_id']}`",
        f"- top_k: `{top_k}`",
        f"- LLM judge: `{'enabled' if run['judge_enabled'] else 'disabled'}`",
    ]

    warnings = run.get("warnings") or []
    if warnings:
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {warning}" for warning in warnings)

    lines.extend(
        [
            "",
            "## Aggregate Metrics",
            "",
            "| Metric | Value |",
            "|---|---:|",
            f"| Total cases | {aggregate['total_cases']} |",
            f"| Error cases | {aggregate['error_cases']} |",
            f"| Hit@{top_k} | {_format_percent(aggregate[hit_key])} |",
            f"| MRR@{top_k} | {_format_number(aggregate[mrr_key])} |",
            f"| Avg top score | {_format_number(aggregate['avg_top_score'])} |",
            f"| Answer pass rate | {_format_percent(aggregate['answer_pass_rate'])} |",
            f"| Answer term pass rate | {_format_percent(aggregate['answer_term_pass_rate'])} |",
            f"| No-answer pass rate | {_format_percent(aggregate['no_answer_pass_rate'])} |",
            f"| Citation pass rate | {_format_percent(aggregate['citation_pass_rate'])} |",
            f"| Latency avg | {_format_seconds(aggregate['latency_avg'])} |",
            f"| Latency p50 | {_format_seconds(aggregate['latency_p50'])} |",
            f"| Latency p95 | {_format_seconds(aggregate['latency_p95'])} |",
        ]
    )

    if aggregate.get("judge"):
        lines.extend(
            [
                f"| Judge correctness | {_format_number(aggregate['judge']['correctness'])} / 2 |",
                f"| Judge groundedness | {_format_number(aggregate['judge']['groundedness'])} / 2 |",
                f"| Judge citation support | {_format_number(aggregate['judge']['citation_support'])} / 2 |",
            ]
        )

    lines.extend(
        [
            "",
            "## Case Results",
            "",
            "| Case | Answerable | Status | Hit | MRR | Answer pass | Citation pass | Latency | Error |",
            "|---|---:|---|---:|---:|---:|---:|---:|---|",
        ]
    )

    for case_result in report["cases"]:
        retrieval = case_result.get("retrieval", {})
        answer = case_result.get("answer", {})
        lines.append(
            "| "
            + " | ".join(
                [
                    _escape_md(case_result["id"]),
                    str(case_result["answerable"]).lower(),
                    case_result["status"],
                    _format_bool(retrieval.get("hit")),
                    _format_number(retrieval.get("mrr")),
                    _format_bool(answer.get("answer_pass")),
                    _format_bool(answer.get("citation_page_pass")),
                    _format_seconds(answer.get("latency_seconds")),
                    _escape_md(case_result.get("error", "")),
                ]
            )
            + " |"
        )

    lines.extend(["", "## Answers", ""])
    for case_result in report["cases"]:
        lines.extend(
            [
                f"### {_escape_md(case_result['id'])}",
                "",
                f"- Question: {_escape_md(case_result['question'])}",
            ]
        )
        if case_result["status"] == "ok":
            answer = case_result["answer"]
            lines.extend(
                [
                    f"- Expected pages: `{case_result['expected_pages']}`",
                    f"- Citation pages: `{answer['citation_pages']}`",
                    "",
                    _truncate(answer["answer"], 800),
                    "",
                ]
            )
        else:
            lines.extend([f"- Error: {_escape_md(case_result.get('error', ''))}", ""])

    return "\n".join(lines).rstrip() + "\n"


def _format_percent(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.1%}"


def _format_number(value: float | int | None) -> str:
    if value is None:
        return "n/a"
    return f"{float(value):.3f}"


def _format_seconds(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.2f}s"


def _format_bool(value: Any) -> str:
    if value is True:
        return "yes"
    if value is False:
        return "no"
    return "n/a"


def _escape_md(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _truncate(value: str, max_length: int) -> str:
    cleaned = str(value or "").strip()
    if len(cleaned) <= max_length:
        return cleaned
    return cleaned[: max_length - 3].rstrip() + "..."


def write_outputs(
    report: dict[str, Any],
    results_md_path: str | Path,
    results_json_path: str | Path,
) -> None:
    md_path = Path(results_md_path)
    json_path = Path(results_json_path)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(render_markdown(report), encoding="utf-8")
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")


def print_summary(report: dict[str, Any]) -> None:
    aggregate = report["aggregate"]
    top_k = report["run"]["top_k"]
    hit_key = f"hit_at_{top_k}"
    print(f"Dataset: {report['run']['dataset_name']}")
    print(f"Document ID: {report['run']['document_id']}")
    print(f"Cases: {aggregate['successful_cases']}/{aggregate['total_cases']} successful")
    print(f"Hit@{top_k}: {_format_percent(aggregate[hit_key])}")
    print(f"Answer pass rate: {_format_percent(aggregate['answer_pass_rate'])}")
    print(f"Citation pass rate: {_format_percent(aggregate['citation_pass_rate'])}")
    print(f"Latency p95: {_format_seconds(aggregate['latency_p95'])}")
    for warning in report["run"].get("warnings") or []:
        print(f"Warning: {warning}")


def ci_failures(report: dict[str, Any]) -> list[str]:
    aggregate = report["aggregate"]
    top_k = report["run"]["top_k"]
    failures = []

    if aggregate["error_cases"]:
        failures.append(f"{aggregate['error_cases']} case(s) errored")

    hit_value = aggregate[f"hit_at_{top_k}"]
    if hit_value is not None and hit_value < CI_HIT_THRESHOLD:
        failures.append(f"hit@{top_k} {hit_value:.3f} < {CI_HIT_THRESHOLD:.3f}")

    answer_value = aggregate["answer_pass_rate"]
    if answer_value is not None and answer_value < CI_ANSWER_THRESHOLD:
        failures.append(
            f"answer_pass_rate {answer_value:.3f} < {CI_ANSWER_THRESHOLD:.3f}"
        )

    citation_value = aggregate["citation_pass_rate"]
    if citation_value is not None and citation_value < CI_CITATION_THRESHOLD:
        failures.append(
            f"citation_pass_rate {citation_value:.3f} < {CI_CITATION_THRESHOLD:.3f}"
        )

    return failures


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run retrieval and RAG quality evaluation through the backend API."
    )
    parser.add_argument("--backend-url", default=DEFAULT_BACKEND_URL)
    parser.add_argument("--dataset", default=DEFAULT_DATASET)
    parser.add_argument("--top-k", type=int, default=DEFAULT_TOP_K)
    parser.add_argument("--document-id", default=None)
    parser.add_argument("--judge", action="store_true")
    parser.add_argument(
        "--judge-model",
        default=os.getenv("GEMINI_MODEL", DEFAULT_JUDGE_MODEL),
    )
    parser.add_argument("--ci", action="store_true")
    parser.add_argument("--results-md", default=DEFAULT_RESULTS_MD)
    parser.add_argument("--results-json", default=DEFAULT_RESULTS_JSON)
    parser.add_argument("--timeout", type=int, default=300)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.top_k < 1:
        parser.error("--top-k must be greater than 0")

    try:
        dataset = load_dataset(args.dataset)
        client = BackendClient(args.backend_url, timeout=args.timeout)
        report = run_evaluation(
            dataset=dataset,
            client=client,
            top_k=args.top_k,
            document_id=args.document_id,
            judge_enabled=args.judge,
            judge_model=args.judge_model,
        )
        write_outputs(report, args.results_md, args.results_json)
        print_summary(report)
        print(f"Wrote Markdown report: {args.results_md}")
        print(f"Wrote JSON report: {args.results_json}")

        if args.ci:
            failures = ci_failures(report)
            if failures:
                print("CI thresholds failed:")
                for failure in failures:
                    print(f"- {failure}")
                return 1
    except (EvalError, OSError, ValueError) as exc:
        print(f"Evaluation failed: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
