"""Pydantic payloads for purchases, travel, and instruments."""

from __future__ import annotations

from pydantic import BaseModel, Field


class PurchaseIn(BaseModel):
    """Open purchase commitment on one award."""

    award_id: int
    category_code: str
    amount_cents: int = Field(ge=0)
    description: str | None = None
    vendor: str | None = None
    effective_date: str


class TravelIn(BaseModel):
    """Open travel commitment on one award."""

    award_id: int
    amount_cents: int = Field(ge=0)
    description: str | None = None
    person_id: int | None = None
    effective_date: str
    trip_end: str | None = None
    category_code: str = "travel"


class InstrumentShareIn(BaseModel):
    """One award's percent of an instrument (D16 units)."""

    award_id: int
    share_pct: int = Field(gt=0)


class InstrumentIn(BaseModel):
    """Shared cost with fixed percent shares summing to 10000."""

    short_code: str
    title: str
    amount_cents: int = Field(ge=0)
    category_code: str = "equipment"
    effective_from: str
    shares: list[InstrumentShareIn] = Field(min_length=1)


class CommitmentOut(BaseModel):
    """Stored commitment. Dollars are admin-only via this DTO."""

    commitment_id: int
    award_id: int
    kind: str
    status_code: str
    category_code: str
    amount_cents: int
    description: str | None
    vendor: str | None
    person_id: int | None
    effective_date: str
    trip_end: str | None
    instrument_id: int | None
    charge_id: int | None


class InstrumentShareOut(BaseModel):
    """Stored share plus computed cents."""

    instrument_share_id: int
    award_id: int
    share_pct: int
    amount_cents: int


class InstrumentOut(BaseModel):
    """Instrument header with shares and child commitments."""

    instrument_id: int
    short_code: str
    title: str
    amount_cents: int
    category_code: str
    status_code: str
    effective_from: str
    effective_to: str | None
    shares: list[InstrumentShareOut] = Field(default_factory=list)
    commitments: list[CommitmentOut] = Field(default_factory=list)
