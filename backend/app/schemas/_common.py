from typing import List, Any, Optional
from urllib.parse import urlparse


def clean_skills(value: Any) -> List[str]:
    """Accept a list or a comma-separated string; trim, drop empties and duplicates (case-insensitive)."""
    if value is None:
        return []
    if isinstance(value, str):
        value = value.split(",")
    out, seen = [], set()
    for s in value:
        s = str(s).strip()[:60]
        if s and s.lower() not in seen:
            seen.add(s.lower())
            out.append(s)
    return out[:40]


def check_url(url: Optional[str]) -> Optional[str]:
    if url is None:
        return None
    url = url.strip()
    if not url:
        return None
    p = urlparse(url)
    if p.scheme not in ("http", "https") or not p.netloc or len(url) > 1000:
        raise ValueError("Must be a full http(s) link, e.g. https://example.com/file.pdf")
    return url


def check_currency(v):
    from app.core import config
    if v is None:
        return None
    v = str(v).upper().strip()
    if v not in config.CURRENCIES:
        raise ValueError(f"Currency must be one of {', '.join(config.CURRENCIES)}")
    return v


def check_country(v):
    from app.core.geo import COUNTRY_CODES
    if v is None or v == "":
        return None
    v = str(v).upper().strip()
    if v not in COUNTRY_CODES:
        raise ValueError("Unknown country code (use ISO 2-letter codes like IN, US, GB)")
    return v


def check_timezone(v):
    from app.core.geo import valid_timezone
    if v is None or v == "":
        return None
    if not valid_timezone(v):
        raise ValueError("Unknown timezone (use names like Asia/Kolkata or Europe/London)")
    return v
