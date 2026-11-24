import re
from typing import Dict, Any, List, Set
from app.core.plugin_interface import RankingPlugin
from app.core import config

# Common spellings that should count as the same skill.
ALIASES = {
    "js": "javascript", "javascript es6": "javascript", "ts": "typescript",
    "reactjs": "react", "react js": "react", "nodejs": "node", "node js": "node",
    "postgres": "postgresql", "psql": "postgresql", "mssql": "sql server",
    "ms sql": "sql server", "k8s": "kubernetes", "ml": "machine learning",
    "ai": "artificial intelligence", "pm": "project management",
    "py": "python", "golang": "go", "c sharp": "c#", "dotnet": ".net",
    "aws cloud": "aws", "amazon web services": "aws", "gcp": "google cloud",
    "sap erp": "sap", "power bi": "powerbi",
}


def normalize_skill(skill: str) -> str:
    s = str(skill).lower().strip()
    s = s.replace(".js", " js").replace("-", " ").replace("_", " ")
    s = re.sub(r"[^\w#+.\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip(" .")
    return ALIASES.get(s, s)


def _tokens(s: str) -> Set[str]:
    return set(s.split())


def skill_matches(required: str, have: List[str]) -> bool:
    """A required skill is met if the consultant has the same skill, or a more specific
    version of it (e.g. required 'python' is met by 'python 3.11' or 'advanced python')."""
    req_tokens = _tokens(required)
    for h in have:
        if h == required or (req_tokens and req_tokens <= _tokens(h)):
            return True
    return False


class StandardWeightedRanking(RankingPlugin):
    """Weighted score: skills (default 70%) + experience (default 30%), 0-100."""

    def explain(self, consultant_data: Dict[str, Any], job_requirements: Dict[str, Any]) -> Dict[str, Any]:
        have = [normalize_skill(s) for s in (consultant_data.get("skills") or []) if str(s).strip()]
        required_raw = [s for s in (job_requirements.get("skills") or []) if str(s).strip()]

        matched, missing = [], []
        for raw in required_raw:
            (matched if skill_matches(normalize_skill(raw), have) else missing).append(raw)

        skill_score = 100.0 if not required_raw else len(matched) / len(required_raw) * 100.0

        cons_exp = float(consultant_data.get("experience_years") or 0)
        req_exp = float(job_requirements.get("min_experience_years") or 0)
        exp_score = 100.0 if req_exp <= 0 else min(cons_exp / req_exp * 100.0, 100.0)

        sw, ew = config.SKILL_WEIGHT, config.EXPERIENCE_WEIGHT
        total = sw + ew or 1.0
        score = round((skill_score * sw + exp_score * ew) / total, 2)
        return {
            "score": score,
            "skill_score": round(skill_score, 2),
            "experience_score": round(exp_score, 2),
            "matched_skills": matched,
            "missing_skills": missing,
            "consultant_experience": cons_exp,
            "required_experience": req_exp,
        }

    def calculate_score(self, consultant_data: Dict[str, Any], job_requirements: Dict[str, Any]) -> float:
        return self.explain(consultant_data, job_requirements)["score"]
