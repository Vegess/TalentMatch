from typing import Dict, Any
from app.core.plugin_interface import IngestionPlugin


class StandardPdfPlugin(IngestionPlugin):
    """Text extraction from digital PDFs using pypdf."""

    def extract_text(self, file_path: str) -> Dict[str, Any]:
        try:
            import pypdf
        except ImportError:
            return {"error": "pypdf is not installed"}
        try:
            reader = pypdf.PdfReader(file_path)
            pages = [(page.extract_text() or "") for page in reader.pages]
            text = "\n".join(pages).strip()
            info = reader.metadata
            return {
                "text": text,
                "metadata": {
                    "engine": "pypdf",
                    "page_count": len(reader.pages),
                    "author": getattr(info, "author", None) if info else None,
                    "title": getattr(info, "title", None) if info else None,
                    "scanned_pdf_suspected": not text,
                },
            }
        except Exception as e:
            return {"error": f"PDF extraction failed: {e}"}
