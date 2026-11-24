"""Subscription plans and their limits. `None` means unlimited. Prices are per month, per currency."""
from typing import Optional, Dict, Any

PLANS: Dict[str, Dict[str, Any]] = {
    "FREE": {
        "name": "Free", "price_monthly": 0, "prices": {"INR": 0, "USD": 0, "EUR": 0, "GBP": 0},
        "max_open_jobs": 2, "max_visible_matches": 3, "show_contact_details": False, "can_message_any": False,
        "description": "Try the platform: 2 open jobs, top 3 matches per job, contact details hidden.",
    },
    "PREMIUM": {
        "name": "Premium", "price_monthly": 999, "prices": {"INR": 999, "USD": 15, "EUR": 14, "GBP": 12},
        "max_open_jobs": 20, "max_visible_matches": 25, "show_contact_details": True, "can_message_any": True,
        "description": "Growing teams: 20 open jobs, top 25 matches, contact details, message any freelancer.",
    },
    "ENTERPRISE": {
        "name": "Enterprise", "price_monthly": 4999, "prices": {"INR": 4999, "USD": 59, "EUR": 55, "GBP": 47},
        "max_open_jobs": None, "max_visible_matches": None, "show_contact_details": True, "can_message_any": True,
        "description": "Unlimited jobs and matches, full contact details.",
    },
}

DEFAULT_PLAN = "FREE"


def normalize_plan(plan_type: str) -> str:
    key = (plan_type or "").strip().upper()
    if key not in PLANS:
        raise ValueError(f"Unknown plan '{plan_type}'. Choose one of: {', '.join(PLANS)}")
    return key


def plan_limits(plan_type: Optional[str]) -> Dict[str, Any]:
    return PLANS.get((plan_type or "").upper(), PLANS[DEFAULT_PLAN])


def price(plan_type: str, currency: str) -> int:
    return PLANS[plan_type]["prices"].get(currency, PLANS[plan_type]["prices"]["USD"])
