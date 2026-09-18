"""
Auth schemas — request / response models for authentication endpoints.
"""

from __future__ import annotations

import re
from typing import Optional

from pydantic import BaseModel, Field, field_validator


# ── Common country codes for the selector ────────────────────────────────
COUNTRY_CODES = [
    {"code": "+20", "name": "Egypt", "iso": "EG"},
    {"code": "+1", "name": "United States", "iso": "US"},
    {"code": "+44", "name": "United Kingdom", "iso": "GB"},
    {"code": "+966", "name": "Saudi Arabia", "iso": "SA"},
    {"code": "+971", "name": "United Arab Emirates", "iso": "AE"},
    {"code": "+49", "name": "Germany", "iso": "DE"},
    {"code": "+33", "name": "France", "iso": "FR"},
    {"code": "+91", "name": "India", "iso": "IN"},
    {"code": "+86", "name": "China", "iso": "CN"},
    {"code": "+81", "name": "Japan", "iso": "JP"},
    {"code": "+82", "name": "South Korea", "iso": "KR"},
    {"code": "+55", "name": "Brazil", "iso": "BR"},
    {"code": "+7", "name": "Russia", "iso": "RU"},
    {"code": "+39", "name": "Italy", "iso": "IT"},
    {"code": "+34", "name": "Spain", "iso": "ES"},
    {"code": "+90", "name": "Turkey", "iso": "TR"},
    {"code": "+234", "name": "Nigeria", "iso": "NG"},
    {"code": "+27", "name": "South Africa", "iso": "ZA"},
    {"code": "+62", "name": "Indonesia", "iso": "ID"},
    {"code": "+60", "name": "Malaysia", "iso": "MY"},
    {"code": "+92", "name": "Pakistan", "iso": "PK"},
    {"code": "+880", "name": "Bangladesh", "iso": "BD"},
    {"code": "+63", "name": "Philippines", "iso": "PH"},
    {"code": "+84", "name": "Vietnam", "iso": "VN"},
    {"code": "+66", "name": "Thailand", "iso": "TH"},
    {"code": "+48", "name": "Poland", "iso": "PL"},
    {"code": "+31", "name": "Netherlands", "iso": "NL"},
    {"code": "+46", "name": "Sweden", "iso": "SE"},
    {"code": "+41", "name": "Switzerland", "iso": "CH"},
    {"code": "+61", "name": "Australia", "iso": "AU"},
    {"code": "+64", "name": "New Zealand", "iso": "NZ"},
    {"code": "+52", "name": "Mexico", "iso": "MX"},
    {"code": "+54", "name": "Argentina", "iso": "AR"},
    {"code": "+57", "name": "Colombia", "iso": "CO"},
    {"code": "+56", "name": "Chile", "iso": "CL"},
    {"code": "+212", "name": "Morocco", "iso": "MA"},
    {"code": "+216", "name": "Tunisia", "iso": "TN"},
    {"code": "+213", "name": "Algeria", "iso": "DZ"},
    {"code": "+218", "name": "Libya", "iso": "LY"},
    {"code": "+249", "name": "Sudan", "iso": "SD"},
    {"code": "+962", "name": "Jordan", "iso": "JO"},
    {"code": "+961", "name": "Lebanon", "iso": "LB"},
    {"code": "+964", "name": "Iraq", "iso": "IQ"},
    {"code": "+965", "name": "Kuwait", "iso": "KW"},
    {"code": "+968", "name": "Oman", "iso": "OM"},
    {"code": "+974", "name": "Qatar", "iso": "QA"},
    {"code": "+973", "name": "Bahrain", "iso": "BH"},
    {"code": "+967", "name": "Yemen", "iso": "YE"},
]

# ── Phone normalization helper ───────────────────────────────────────────
_DIGITS_ONLY = re.compile(r"\D")

def normalize_phone(country_code: str, local_number: str) -> str:
    """
    Combine country code and local number into E.164 format.

    Examples:
        normalize_phone("+20", "1012345678")   → "+201012345678"
        normalize_phone("+20", "01012345678")  → "+201012345678"
        normalize_phone("+1", "2025551234")    → "+12025551234"
    """
    # Strip all non-digit characters
    digits = _DIGITS_ONLY.sub("", local_number)

    # If the local number starts with the country digits, strip them
    cc_digits = _DIGITS_ONLY.sub("", country_code)
    if digits.startswith(cc_digits):
        digits = digits[len(cc_digits):]

    # Strip leading zero (common in local formats like 01012345678)
    if digits.startswith("0"):
        digits = digits[1:]

    return f"+{cc_digits}{digits}"


def validate_phone_number(country_code: str, local_number: str) -> str | None:
    """
    Validate and return normalized E.164 phone, or None if invalid.
    Basic checks: country code must start with +, combined length 7-15 digits.
    """
    if not country_code.startswith("+"):
        return None

    normalized = normalize_phone(country_code, local_number)
    digits = _DIGITS_ONLY.sub("", normalized)

    # E.164 spec: 7-15 digits total
    if len(digits) < 7 or len(digits) > 15:
        return None

    return normalized


# ── Password validation ──────────────────────────────────────────────────
def check_password_strength(password: str) -> list[str]:
    """Return a list of unmet password requirements."""
    errors = []
    if len(password) < 8:
        errors.append("Password must be at least 8 characters")
    if not re.search(r"[A-Z]", password):
        errors.append("Password must contain an uppercase letter")
    if not re.search(r"[a-z]", password):
        errors.append("Password must contain a lowercase letter")
    if not re.search(r"\d", password):
        errors.append("Password must contain a number")
    if not re.search(r"[!@#$%^&*()_+\-=\[\]{}|;':\",./<>?`~\\]", password):
        errors.append("Password must contain a special character")
    return errors


# ── Request / Response models ────────────────────────────────────────────

class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=80)
    country_code: str = Field(..., min_length=2, max_length=5,
                               description="Country code with + prefix, e.g. '+20'")
    mobile_phone: str = Field(..., min_length=4, max_length=20,
                               description="Local phone number (digits, may include leading 0)")
    password: str = Field(..., min_length=8, max_length=128)

    @field_validator("country_code")
    @classmethod
    def validate_country_code(cls, v: str) -> str:
        if not v.startswith("+"):
            raise ValueError("Country code must start with '+'")
        if not _DIGITS_ONLY.sub("", v):
            raise ValueError("Country code must contain digits")
        return v.strip()

    @field_validator("mobile_phone")
    @classmethod
    def validate_mobile_phone(cls, v: str) -> str:
        digits = _DIGITS_ONLY.sub("", v)
        if len(digits) < 4:
            raise ValueError("Phone number too short")
        if len(digits) > 15:
            raise ValueError("Phone number too long")
        return v.strip()

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        errors = check_password_strength(v)
        if errors:
            raise ValueError("; ".join(errors))
        return v


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: int
    username: str


class UserResponse(BaseModel):
    id: int
    username: str
    mobile_phone: str

    model_config = {"from_attributes": True}
