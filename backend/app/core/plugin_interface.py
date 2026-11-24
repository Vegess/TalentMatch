from abc import ABC, abstractmethod
from typing import Dict, Any


class IngestionPlugin(ABC):
    """Abstract base class for ingestion plugins (PDF / OCR text extraction)."""

    @abstractmethod
    def extract_text(self, file_path: str) -> Dict[str, Any]:
        """Return {"text": str, "metadata": {...}} or {"error": str}."""


class RankingPlugin(ABC):
    """Abstract base class for ranking / matching plugins."""

    @abstractmethod
    def calculate_score(self, consultant_data: Dict[str, Any], job_requirements: Dict[str, Any]) -> float:
        """Return a score between 0.0 and 100.0."""

    def explain(self, consultant_data: Dict[str, Any], job_requirements: Dict[str, Any]) -> Dict[str, Any]:
        """Return {"score": float, ...breakdown}. Plugins may override to add detail."""
        return {"score": self.calculate_score(consultant_data, job_requirements)}
