"""Domain models for SafeDose.

An NSQ record is one row from a CDSCO "Not of Standard Quality" monthly
alert: a specific drug *batch* that a government lab tested and found
substandard, spurious, or misbranded. The whole point of the tool is that
a flag applies to a *batch*, not a brand — so batch number is the key
identity field, and matching is built around it.
"""

from __future__ import annotations

import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class FailureCategory(str, Enum):
    """Coarse grouping of the (very granular) CDSCO failure reasons."""

    spurious = "spurious"          # declared spurious / counterfeit — most serious
    contamination = "contamination"  # particulate matter, microbial, sterility
    dissolution = "dissolution"    # fails to release active ingredient correctly
    assay = "assay"                # wrong amount of active ingredient
    labelling = "labelling"        # misbranding, wrong/missing label claims
    physical = "physical"          # appearance, pH, uniformity, disintegration
    other = "other"


class NSQRecord(BaseModel):
    id: str                         # stable hash of source+batch+drug
    drug_name: str = Field(min_length=2)
    batch_no: str = Field(min_length=1)
    batch_no_normalized: str        # uppercased, stripped of spaces/punct
    manufacturer: Optional[str] = None
    mfg_date: Optional[str] = None  # kept as printed (MM/YYYY); CDSCO is inconsistent
    expiry_date: Optional[str] = None
    failure_reason: str             # verbatim CDSCO text
    failure_category: FailureCategory
    is_spurious: bool               # declared spurious/counterfeit (not just NSQ)
    tested_by: Optional[str] = None  # CDSCO lab
    source_alert: str               # e.g. "NSQ Alert March-2025"
    source_url: str
    alert_period: str               # "2025-03"


class MatchType(str, Enum):
    batch_flagged = "batch_flagged"      # this exact batch is on an NSQ list
    drug_flagged = "drug_flagged"        # same drug, other batch(es) flagged
    clear = "clear"                      # nothing matched in the dataset


class CheckResult(BaseModel):
    query_drug: Optional[str]
    query_batch: Optional[str]
    match_type: MatchType
    severity: str                        # "danger" | "caution" | "clear"
    headline: str
    detail: str
    batch_matches: list[NSQRecord] = Field(default_factory=list)
    drug_matches: list[NSQRecord] = Field(default_factory=list)
    checked_alerts: int                  # how many monthly alerts the dataset covers
    dataset_period: str                  # human label of coverage


class Stats(BaseModel):
    total_records: int
    spurious_count: int
    distinct_drugs: int
    distinct_manufacturers: int
    alerts_ingested: list[str]
    last_alert_period: Optional[str]
    by_category: dict[str, int]
    generated_on: datetime.date
