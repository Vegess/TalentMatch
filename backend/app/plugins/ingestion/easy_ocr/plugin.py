from typing import Dict, Any
from app.core.plugin_interface import IngestionPlugin

class EasyOcrPlugin(IngestionPlugin):
    """
    Implementation of OCR using EasyOCR.
    """
    def extract_text(self, file_path: str) -> Dict[str, Any]:
        try:
            import easyocr
            import numpy as np
        except ImportError:
            return {"error": "easyocr or numpy not installed"}

        try:
            print(f"EasyOCR extracting from {file_path}")
            # Initialize reader (supports English by default, can be extended)
            # using gpu=False for compatibility, set to True if GPU available
            reader = easyocr.Reader(['en'], gpu=False) 
            
            result = reader.readtext(file_path, detail=0)
            text = " ".join(result)
            
            return {
                "text": text,
                "metadata": {
                    "engine": "easyocr",
                    "word_count": len(text.split()),
                    "language": "en"
                }
            }
        except Exception as e:
            return {"error": f"EasyOCR failed: {str(e)}"}
