"""PDF and HTML parsing utilities for regulatory circular ingestion."""

import re
import tempfile
from html.parser import HTMLParser

import httpx
import pdfplumber


class _HTMLTextExtractor(HTMLParser):
    """Strips HTML tags and extracts visible text content."""

    _INVISIBLE_TAGS = frozenset({"script", "style", "head", "meta", "link"})

    def __init__(self):
        super().__init__()
        self._pieces: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs):
        if tag.lower() in self._INVISIBLE_TAGS:
            self._skip_depth += 1

    def handle_endtag(self, tag: str):
        if tag.lower() in self._INVISIBLE_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1

    def handle_data(self, data: str):
        if self._skip_depth == 0:
            self._pieces.append(data)

    def get_text(self) -> str:
        return " ".join(self._pieces)


def parse_pdf_bytes(data: bytes) -> str:
    """Extract all text from raw PDF bytes using pdfplumber.

    Args:
        data: Raw PDF file content.

    Returns:
        Concatenated text from all pages.
    """
    pages_text: list[str] = []
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(data)
        tmp.flush()
        tmp_path = tmp.name

    with pdfplumber.open(tmp_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                pages_text.append(text)

    return "\n\n".join(pages_text)


def parse_url(url: str) -> str:
    """Download a URL and extract text content.

    If the response content-type is application/pdf, extracts text via
    pdfplumber.  Otherwise treats the response as HTML and strips tags.

    Args:
        url: The URL to download.

    Returns:
        Extracted plain text.
    """
    with httpx.Client(timeout=60.0, follow_redirects=True) as client:
        response = client.get(url)
        response.raise_for_status()

    content_type = response.headers.get("content-type", "").lower()

    if "application/pdf" in content_type:
        return parse_pdf_bytes(response.content)

    # Treat as HTML
    extractor = _HTMLTextExtractor()
    extractor.feed(response.text)
    return extractor.get_text()


def section_text(raw: str) -> str:
    """Light cleanup: normalise whitespace and line breaks.

    Args:
        raw: Raw extracted text.

    Returns:
        Cleaned text with normalised spacing.
    """
    # Collapse multiple blank lines into one
    text = re.sub(r"\n{3,}", "\n\n", raw)
    # Collapse runs of spaces/tabs (but not newlines) into a single space
    text = re.sub(r"[^\S\n]+", " ", text)
    # Strip leading/trailing whitespace from each line
    lines = [line.strip() for line in text.splitlines()]
    return "\n".join(lines).strip()
