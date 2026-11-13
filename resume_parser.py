"""Turn an uploaded .docx or .pdf resume into plain text."""
import io

from docx import Document
from pypdf import PdfReader


def parse_resume(data: bytes, filename: str) -> str:
    name = filename.lower()
    if name.endswith(".docx"):
        doc = Document(io.BytesIO(data))
        parts = [p.text for p in doc.paragraphs if p.text.strip()]
        for table in doc.tables:
            for row in table.rows:
                cells = [c.text.strip() for c in row.cells if c.text.strip()]
                if cells:
                    parts.append(" | ".join(cells))
        return "\n".join(parts)
    if name.endswith(".pdf"):
        reader = PdfReader(io.BytesIO(data))
        return "\n".join((page.extract_text() or "") for page in reader.pages)
    raise ValueError("Upload a .docx or .pdf file.")
