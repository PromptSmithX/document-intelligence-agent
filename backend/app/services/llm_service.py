import os


DEFAULT_LLM_PROVIDER = "gemini"
DEFAULT_GEMINI_MODEL = "gemini-1.5-flash"


def _get_llm_provider() -> str:
    return os.getenv("LLM_PROVIDER", DEFAULT_LLM_PROVIDER).strip().lower() or DEFAULT_LLM_PROVIDER


def _get_gemini_api_key() -> str:
    return os.getenv("GEMINI_API_KEY", "").strip()


def _get_gemini_model() -> str:
    return os.getenv("GEMINI_MODEL", DEFAULT_GEMINI_MODEL).strip() or DEFAULT_GEMINI_MODEL


def generate_answer(prompt: str) -> str:
    provider = _get_llm_provider()
    if provider != "gemini":
        raise ValueError(f"Unsupported LLM provider: {provider}")

    api_key = _get_gemini_api_key()
    if not api_key:
        raise ValueError("GEMINI_API_KEY is required")

    from google import genai

    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=_get_gemini_model(),
        contents=prompt,
    )

    return (response.text or "").strip()
