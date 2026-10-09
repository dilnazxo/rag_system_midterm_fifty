"""Extract page-scoped text chunks from PDF manuals."""

from pathlib import Path
from typing import TypedDict

import pymupdf


class ChunkRecord(TypedDict):
    chunk_id: str
    text: str
    source_file: str
    page: int


def chunk_text(text: str, chunk_size: int = 800, overlap: int = 120) -> list[str]:
    """Split one page's text into overlapping character chunks."""
    if chunk_size <= 0 or not 0 <= overlap < chunk_size:
        raise ValueError("chunk_size must be positive and overlap smaller than it")

    text = text.strip()
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunk = text[start:end]
        if chunk.strip():
            chunks.append(chunk)
        if end == len(text):
            break
        start = end - overlap
    return chunks


def ingest_pdfs(manuals_dir: str | Path = "data/manuals") -> list[ChunkRecord]:
    """Read PDFs in a folder and return chunks with filename and page metadata."""
    directory = Path(manuals_dir)
    records: list[ChunkRecord] = []
    pdf_paths = sorted(
        (path for path in directory.iterdir() if path.is_file() and path.suffix.lower() == ".pdf"),
        key=lambda path: path.name.lower(),
    )

    for pdf_path in pdf_paths:
        with pymupdf.open(pdf_path) as document:
            for page_number, page in enumerate(document, start=1):
                for chunk_number, text in enumerate(chunk_text(page.get_text("text")), start=1):
                    records.append(
                        {
                            "chunk_id": f"{pdf_path.name}:p{page_number}:c{chunk_number}",
                            "text": text,
                            "source_file": pdf_path.name,
                            "page": page_number,
                        }
                    )

    return records
