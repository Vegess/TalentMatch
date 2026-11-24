"""Pull name, email, phone, skills and years of experience out of raw CV text."""
import re
from typing import List

from app.schemas._common import clean_skills

KNOWN_SKILLS = [
    "python", "java", "javascript", "typescript", "react", "angular", "node", "django", "fastapi",
    "flask", "sql", "postgresql", "mysql", "mongodb", "aws", "azure", "google cloud", "docker",
    "kubernetes", "terraform", "linux", "git", "c#", ".net", "c++", "go", "rust", "php", "html", "css",
    "machine learning", "data science", "deep learning", "nlp", "pandas", "tableau", "powerbi", "excel",
    "project management", "consulting", "erp", "sap", "oracle", "salesforce", "analytics",
    "strategy", "operations", "manufacturing", "quality", "iso", "lean", "six sigma", "agile",
    "scrum", "devops", "ci/cd", "testing", "selenium", "figma", "ui/ux", "accounting", "finance",
    "marketing", "seo", "sales", "hr", "supply chain", "procurement",
]
SECTION_STOP = r"(?:experience|work experience|employment|education|projects|certifications?|languages|summary|profile|contact|references)"
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
PHONE_RE = re.compile(r"(?:\+?\d[\d\s\-()]{8,}\d)")


def _parse_profile_text(text: str) -> dict:
    """Pull skills, years of experience, email and phone out of raw CV text."""
    out = {"skills": [], "experience_years": 0.0, "email": None, "phone": None}
    if not text:
        return out

    m = EMAIL_RE.search(text)
    out["email"] = m.group(0).lower() if m else None
    m = PHONE_RE.search(text)
    out["phone"] = re.sub(r"\s+", " ", m.group(0)).strip() if m else None

    # Experience: prefer explicit "N years of experience"; fall back to the largest "N years".
    exp = re.search(r"(\d+(?:\.\d+)?)\s*\+?\s*(?:years?|yrs?)\s*(?:of\s+)?(?:professional\s+|industry\s+|work\s+)?experience",
                    text, re.IGNORECASE)
    if exp:
        out["experience_years"] = float(exp.group(1))
    else:
        nums = [float(n) for n in re.findall(r"(\d+(?:\.\d+)?)\s*\+?\s*(?:years?|yrs?)\b", text, re.IGNORECASE)]
        nums = [n for n in nums if n <= 50]
        out["experience_years"] = max(nums) if nums else 0.0

    # Skills section: "Skills:", "Technical Skills", "Key Skills", "Expertise", "Competencies".
    skills: List[str] = []
    sec = re.search(
        rf"(?:technical\s+skills|key\s+skills|core\s+skills|skills|expertise|competencies|tech\s+stack)\s*[:\-–]?\s*\n?"
        rf"(.+?)(?=\n\s*{SECTION_STOP}\b|\Z)",
        text, re.IGNORECASE | re.DOTALL,
    )
    if sec:
        block = sec.group(1)[:1500]
        for part in re.split(r"[,;•●▪·|/\n]|\s[-–—]\s", block):
            part = part.strip(" \t-–—*:.")
            if 1 < len(part) <= 40 and len(part.split()) <= 4:
                skills.append(part)
    if not skills:
        lower = text.lower()
        for kw in KNOWN_SKILLS:
            if re.search(rf"(?<![\w]){re.escape(kw)}(?![\w])", lower):
                skills.append(kw.title() if kw.isalpha() and len(kw) > 3 else kw.upper() if kw.isalpha() else kw)
    out["skills"] = clean_skills(skills)[:40]
    return out


parse_profile_text = _parse_profile_text
