import fitz


def parse_pdf(file_path: str) -> list[dict]:
    try:
        document = fitz.open(file_path)
    except Exception as exc:
        raise ValueError(f"Could not open PDF: {exc}") from exc

    try:
        pages = []
        for page_index in range(document.page_count):
            page = document.load_page(page_index)
            pages.append(
                {
                    "page": page_index + 1,
                    "text": page.get_text().strip(),
                }
            )

        return pages
    except Exception as exc:
        raise ValueError(f"Could not parse PDF: {exc}") from exc
    finally:
        document.close()
