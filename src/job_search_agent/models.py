from __future__ import annotations

from datetime import date
from enum import StrEnum

from pydantic import BaseModel, Field, HttpUrl


class Classification(StrEnum):
    APPLY_NOW = "Apply Now"
    WARM_INTRO_FIRST = "Warm Intro First"
    MONITOR = "Monitor"
    REMOTE_MATCH = "Remote Match"
    AUSTIN_MATCH = "Austin Match"
    DALLAS_MATCH = "Dallas Match"
    REJECTED_NOTABLE = "Rejected / Notable"
    AUTO_REJECT = "Auto Reject"
    EXPIRED = "Expired"


class JobRecord(BaseModel):
    title: str
    company: str
    location: str = ""
    url: HttpUrl | str = ""
    source: str
    source_email_id: str
    source_alert_name: str = ""
    date_found: date = Field(default_factory=date.today)
    notes: str = ""
    fit_summary: str = ""
    requirements_summary: str = ""
    network_summary: str = ""
    network_contacts: list["NetworkContact"] = Field(default_factory=list)
    raw_text: str = ""


class ScoredJob(BaseModel):
    job: JobRecord
    total_score: int
    labels: list[Classification]
    score_breakdown: dict[str, int]
    rationale: list[str]
    destination_tab: str


class NetworkContact(BaseModel):
    name: str
    company: str = ""
    position: str = ""
    profile_url: str = ""
    reason: str = ""
