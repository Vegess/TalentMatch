import datetime as dt
from typing import List, Optional, Literal
from pydantic import BaseModel, Field, field_validator, model_validator
from app.schemas._common import clean_skills, check_currency


class JobIn(BaseModel):
    title: str = Field(..., min_length=3, max_length=200)
    category: Optional[str] = Field(None, max_length=80)
    description: str = Field("", max_length=10000)
    responsibilities: Optional[str] = Field(None, max_length=10000)
    requirements: Optional[str] = Field(None, max_length=10000)
    required_skills: List[str] = []
    min_experience_years: float = Field(0.0, ge=0, le=70)
    budget_type: Literal["fixed", "hourly"] = "fixed"
    budget_min: Optional[int] = Field(None, ge=0, le=100_000_000)
    budget_max: Optional[int] = Field(None, ge=0, le=100_000_000)
    currency: Optional[str] = None  # defaults to the company's billing currency
    location_type: Literal["remote", "onsite", "hybrid"] = "remote"
    location: Optional[str] = Field(None, max_length=120)
    deadline: Optional[dt.date] = None

    @field_validator("required_skills", mode="before")
    @classmethod
    def _skills(cls, v):
        return clean_skills(v)

    _cur = field_validator("currency")(lambda cls, v: check_currency(v))

    @model_validator(mode="after")
    def _budget(self):
        if self.budget_min is not None and self.budget_max is not None and self.budget_max < self.budget_min:
            raise ValueError("budget_max must be greater than or equal to budget_min")
        return self


class JobCreateAdmin(JobIn):
    client_id: int


class JobUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=3, max_length=200)
    category: Optional[str] = Field(None, max_length=80)
    description: Optional[str] = Field(None, max_length=10000)
    responsibilities: Optional[str] = Field(None, max_length=10000)
    requirements: Optional[str] = Field(None, max_length=10000)
    required_skills: Optional[List[str]] = None
    min_experience_years: Optional[float] = Field(None, ge=0, le=70)
    budget_type: Optional[Literal["fixed", "hourly"]] = None
    budget_min: Optional[int] = Field(None, ge=0, le=100_000_000)
    budget_max: Optional[int] = Field(None, ge=0, le=100_000_000)
    location_type: Optional[Literal["remote", "onsite", "hybrid"]] = None
    location: Optional[str] = Field(None, max_length=120)
    deadline: Optional[dt.date] = None
    status: Optional[Literal["open", "closed"]] = None

    @field_validator("required_skills", mode="before")
    @classmethod
    def _skills(cls, v):
        return None if v is None else clean_skills(v)


class ServiceIn(BaseModel):
    title: str = Field(..., min_length=5, max_length=160)
    category: Optional[str] = Field(None, max_length=80)
    description: str = Field("", max_length=10000)
    deliverables: Optional[str] = Field(None, max_length=5000)
    price: int = Field(..., ge=5, le=10_000_000)
    currency: Optional[str] = None  # defaults to the freelancer's currency
    delivery_days: int = Field(7, ge=1, le=365)
    skills: List[str] = []
    status: Literal["active", "paused"] = "active"

    _cur = field_validator("currency")(lambda cls, v: check_currency(v))

    @field_validator("skills", mode="before")
    @classmethod
    def _skills(cls, v):
        return clean_skills(v)


class ServiceUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=5, max_length=160)
    category: Optional[str] = Field(None, max_length=80)
    description: Optional[str] = Field(None, max_length=10000)
    deliverables: Optional[str] = Field(None, max_length=5000)
    price: Optional[int] = Field(None, ge=5, le=10_000_000)
    currency: Optional[str] = None
    delivery_days: Optional[int] = Field(None, ge=1, le=365)
    skills: Optional[List[str]] = None
    status: Optional[Literal["active", "paused"]] = None

    @field_validator("skills", mode="before")
    @classmethod
    def _skills(cls, v):
        return None if v is None else clean_skills(v)


class ProposalIn(BaseModel):
    cover_letter: str = Field(..., min_length=20, max_length=5000)
    bid_amount: int = Field(..., ge=5, le=100_000_000)
    estimated_days: Optional[int] = Field(None, ge=1, le=365)


class ServiceOrderIn(BaseModel):
    requirements: Optional[str] = Field(None, max_length=5000)


class DeliverIn(BaseModel):
    delivery_note: str = Field(..., min_length=5, max_length=5000)


class LinkDocumentIn(BaseModel):
    owner_type: Literal["job", "consultant", "service", "order"]
    owner_id: int
    title: str = Field(..., min_length=1, max_length=200)
    url: str

    @field_validator("url")
    @classmethod
    def _u(cls, v):
        from app.schemas._common import check_url
        return check_url(v)


class CheckoutIn(BaseModel):
    purpose: Literal["subscription", "order"]
    plan_type: Optional[str] = None
    months: int = Field(1, ge=1, le=12)
    order_id: Optional[int] = None


class VerifyIn(BaseModel):
    payment_id: int
    razorpay_order_id: str = Field(..., max_length=64)
    razorpay_payment_id: str = Field(..., max_length=64)
    razorpay_signature: str = Field(..., max_length=128)


class DemoCompleteIn(BaseModel):
    outcome: Literal["success", "failure"] = "success"
