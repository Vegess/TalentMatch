from typing import Literal, Optional
from pydantic import BaseModel, EmailStr, Field


class RegisterIn(BaseModel):
    role: Literal["client", "freelancer"]
    name: str = Field(..., min_length=1, max_length=120)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    company_name: Optional[str] = Field(None, max_length=200)  # clients
    headline: Optional[str] = Field(None, max_length=160)      # freelancers
    country: Optional[str] = Field(None, max_length=2)
    timezone: Optional[str] = Field(None, max_length=64)
    language: Optional[Literal["en", "hi", "es"]] = None


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(..., max_length=128)


class ChangePasswordIn(BaseModel):
    current_password: str = Field(..., max_length=128)
    new_password: str = Field(..., min_length=8, max_length=128)


class PreferencesIn(BaseModel):
    preferred_language: Optional[Literal["en", "hi", "es"]] = None
    email_notifications: Optional[bool] = None


class ForgotPasswordIn(BaseModel):
    email: EmailStr


class ResetPasswordIn(BaseModel):
    token: str = Field(..., min_length=20, max_length=200)
    new_password: str = Field(..., min_length=8, max_length=128)
