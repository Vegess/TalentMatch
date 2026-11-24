from typing import List, Optional, Literal
from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator
from app.schemas._common import clean_skills, check_url, check_currency, check_country, check_timezone


class Link(BaseModel):
    label: str = Field(..., min_length=1, max_length=40)
    url: str

    @field_validator("url")
    @classmethod
    def _u(cls, v):
        return check_url(v)


class FreelancerUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=120)
    phone: Optional[str] = Field(None, max_length=40)
    headline: Optional[str] = Field(None, max_length=160)
    bio: Optional[str] = Field(None, max_length=5000)
    location: Optional[str] = Field(None, max_length=120)
    hourly_rate: Optional[int] = Field(None, ge=0, le=100000)
    availability: Optional[Literal["available", "busy"]] = None
    links: Optional[List[Link]] = Field(None, max_length=10)
    skills: Optional[List[str]] = None
    experience_years: Optional[float] = Field(None, ge=0, le=70)
    is_public: Optional[bool] = None
    country: Optional[str] = None
    timezone: Optional[str] = None
    work_start_hour: Optional[int] = Field(None, ge=0, le=23)
    work_end_hour: Optional[int] = Field(None, ge=0, le=23)
    languages: Optional[List[str]] = None
    currency: Optional[str] = None

    _country = field_validator("country")(lambda cls, v: check_country(v))
    _tz = field_validator("timezone")(lambda cls, v: check_timezone(v))
    _cur = field_validator("currency")(lambda cls, v: check_currency(v))

    @field_validator("languages", mode="before")
    @classmethod
    def _langs(cls, v):
        return None if v is None else clean_skills(v)[:10]

    @field_validator("skills", mode="before")
    @classmethod
    def _skills(cls, v):
        return None if v is None else clean_skills(v)


class FreelancerAdminCreate(BaseModel):
    """Admin creates a profile on someone's behalf (no login)."""
    name: str = Field(..., min_length=1, max_length=120)
    email: EmailStr
    phone: Optional[str] = Field(None, max_length=40)
    headline: Optional[str] = Field(None, max_length=160)
    skills: List[str] = []
    experience_years: float = Field(0.0, ge=0, le=70)

    @field_validator("skills", mode="before")
    @classmethod
    def _skills(cls, v):
        return clean_skills(v)


class ClientUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=120)
    company_name: Optional[str] = Field(None, max_length=200)
    website: Optional[str] = None
    industry: Optional[str] = Field(None, max_length=120)
    about: Optional[str] = Field(None, max_length=5000)
    country: Optional[str] = None
    timezone: Optional[str] = None
    currency: Optional[str] = None

    _country = field_validator("country")(lambda cls, v: check_country(v))
    _tz = field_validator("timezone")(lambda cls, v: check_timezone(v))
    _cur = field_validator("currency")(lambda cls, v: check_currency(v))

    @field_validator("website")
    @classmethod
    def _w(cls, v):
        return check_url(v)


class PayoutDetailsIn(BaseModel):
    method: Literal["bank_account", "upi"]
    beneficiary_name: str = Field(..., min_length=4, max_length=200, description="Name exactly as on the bank account / UPI")
    account_number: Optional[str] = Field(None, max_length=20)
    ifsc: Optional[str] = Field(None, max_length=11)
    vpa: Optional[str] = Field(None, max_length=300)
    phone: Optional[str] = Field(None, max_length=16)

    @field_validator("account_number", "ifsc", "vpa", "phone", mode="before")
    @classmethod
    def _strip(cls, v):
        return v.strip().replace(" ", "") if isinstance(v, str) and v.strip() else None

    @field_validator("phone")
    @classmethod
    def _phone(cls, v):
        if v and not __import__("re").fullmatch(r"\+?\d{8,15}", v):
            raise ValueError("Phone must be 8–15 digits, optionally starting with +")
        return v

    @model_validator(mode="after")
    def _by_method(self):
        from app.services.payouts import IFSC_RE, VPA_RE
        import re
        if self.method == "bank_account":
            if not self.account_number or not re.fullmatch(r"[A-Za-z0-9]{5,20}", self.account_number):
                raise ValueError("Enter a valid bank account number (5–20 characters)")
            if not self.ifsc or not IFSC_RE.fullmatch(self.ifsc.upper()):
                raise ValueError("Enter a valid IFSC code, e.g. HDFC0000317")
            self.ifsc = self.ifsc.upper()
            self.vpa = None
        else:
            if not self.vpa or not VPA_RE.fullmatch(self.vpa):
                raise ValueError("Enter a valid UPI ID, e.g. name@okhdfcbank")
            self.account_number = self.ifsc = None
        return self
