"""
tools/pdf_reader.py
=====================
Extracts text from PDF files for the Researcher agent.

Three public functions:
  read(file_path)              — read from a local file path
  read_base64(b64, filename)   — read from a base64-encoded string (from frontend upload)
  get_metadata(file_path)      — return title/author/page count without full extraction

All return a list[dict] matching ResearchState.raw_sources format so the
Analyst and Writer nodes can process PDF content identically to Tavily results.
"""

import base64
import os
import re
import tempfile
from pathlib import Path

import fitz  # PyMuPDF


# ── Config ────────────────────────────────────────────────────

CHUNK_SIZE  = 8_000   # chars per chunk — roughly 2000 tokens
MAX_CHUNKS  = 5       # max chunks extracted — prevents huge PDFs filling context


# ── Internal helpers ──────────────────────────────────────────

def _extract_chunks(doc: fitz.Document, filename: str = "Uploaded PDF") -> list[dict]:
    """
    Extract text from an open PyMuPDF Document and return a list
    of source dicts compatible with ResearchState.raw_sources.
    """
    # Concatenate all pages
    full_text = ""
    for page in doc:
        full_text += page.get_text("text") + "\n"

    full_text = re.sub(r"\n{3,}", "\n\n", full_text).strip()

    if not full_text:
        return []

    # Try to extract a meaningful title from first non-empty line
    first_line = next(
        (line.strip() for line in full_text.split("\n") if len(line.strip()) > 5),
        ""
    )
    title = (
        doc.metadata.get("title")
        or (first_line[:80] if first_line else filename)
    )

    # Split into chunks
    chunks = []
    for i in range(0, min(len(full_text), CHUNK_SIZE * MAX_CHUNKS), CHUNK_SIZE):
        chunks.append({
            "question": "Extracted from uploaded PDF",
            "title":    title,
            "url":      "local://uploaded-pdf",
            "content":  full_text[i : i + CHUNK_SIZE],
            "score":    0.9,   # user-uploaded docs treated as high-trust
        })

    return chunks


# ── Public API ────────────────────────────────────────────────

def read(file_path: str) -> list[dict]:
    """
    Read a PDF from a local file path.

    Returns:
        List of source dicts compatible with ResearchState.raw_sources.

    Raises:
        FileNotFoundError — if the path does not exist.
        ValueError        — if the file is not a valid PDF.
    """
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {file_path}")

    if path.suffix.lower() != ".pdf":
        raise ValueError(f"Expected a .pdf file, got: {path.suffix}")

    try:
        doc = fitz.open(str(path))
        chunks = _extract_chunks(doc, filename=path.name)
        doc.close()
        return chunks
    except Exception as e:
        raise ValueError(f"Failed to parse PDF: {e}") from e


def read_base64(b64_string: str, filename: str = "upload.pdf") -> list[dict]:
    """
    Read a PDF from a base64-encoded string.
    Used by main.py when the frontend sends a PDF via multipart form.

    Args:
        b64_string: Base64-encoded PDF bytes.
        filename:   Original filename (used as fallback title).

    Returns:
        List of source dicts compatible with ResearchState.raw_sources.

    Raises:
        ValueError — if the base64 string is invalid or the PDF cannot be parsed.
    """
    # Decode base64 → raw bytes
    try:
        pdf_bytes = base64.b64decode(b64_string)
    except Exception as e:
        raise ValueError(f"Invalid base64 string: {e}") from e

    # Write to a temp file so PyMuPDF can open it
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(pdf_bytes)
            tmp_path = tmp.name

        doc = fitz.open(tmp_path)
        chunks = _extract_chunks(doc, filename=filename)
        doc.close()
        return chunks

    except Exception as e:
        raise ValueError(f"Failed to parse PDF: {e}") from e

    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)   # always clean up temp file


def get_metadata(file_path: str) -> dict:
    """
    Return metadata for a PDF without extracting full content.
    Useful for showing file info in the UI before processing.

    Returns:
        {
            "title":      str,
            "author":     str,
            "page_count": int,
            "filename":   str,
        }
    """
    doc = fitz.open(file_path)
    meta = doc.metadata or {}
    page_count = doc.page_count
    doc.close()

    return {
        "title":      meta.get("title", ""),
        "author":     meta.get("author", ""),
        "page_count": page_count,
        "filename":   Path(file_path).name,
    }


# ── Quick smoke test ──────────────────────────────────────────

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python pdf_reader.py <path_to_pdf>")
        sys.exit(1)

    path = sys.argv[1]
    print(f"Reading: {path}\n")

    chunks = read(path)

    if not chunks:
        print("ERROR: No text extracted — PDF may be scanned/image-based.")
        sys.exit(1)

    print(f"Title  : {chunks[0]['title']}")
    print(f"Chunks : {len(chunks)}")
    print(f"Chars  : {sum(len(c['content']) for c in chunks)}")
    print(f"\n── First 500 chars ──\n{chunks[0]['content'][:500]}")