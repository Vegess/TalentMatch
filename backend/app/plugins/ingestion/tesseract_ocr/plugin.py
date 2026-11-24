from typing import Dict, Any
from app.core.plugin_interface import IngestionPlugin

class TesseractPlugin(IngestionPlugin):
    """
    Implementation of OCR using Pytesseract.
    """
    def extract_text(self, file_path: str) -> Dict[str, Any]:
        try:
            import pytesseract
            from PIL import Image
        except ImportError:
            return {"error": "pytesseract or PIL not installed"}

        try:
            print(f"Tesseract extracting from {file_path}")
            image = Image.open(file_path)
            text = pytesseract.image_to_string(image)
            
            # Basic metadata extraction (just simple stats for now)
            word_count = len(text.split())
            
            return {
                "text": text,
                "metadata": {
                    "engine": "tesseract",
                    "word_count": word_count,
                    "confidence": "unknown" # Pytesseract legacy mode often doesn't give global confidence easily without more complex calls
                }
            }
        except Exception as e:
             return {"error": f"OCR failed: {str(e)}"}
