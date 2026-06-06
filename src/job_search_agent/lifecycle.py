from __future__ import annotations

import re
from datetime import date, timedelta

from job_search_agent.models import JobRecord


EXPIRATION_DAYS = 45

CLOSED_PATTERNS = (
    r"\bno longer accepting\b",
    r"\bnot accepting applications\b",
    r"\bapplications? closed\b",
    r"\bposting closed\b",
    r"\bposition closed\b",
    r"\bjob closed\b",
    r"\bjob expired\b",
    r"\bno longer available\b",
    r"\bthis job is no longer available\b",
)


def is_expired_job(job: JobRecord, *, today: date | None = None) -> bool:
    today = today or date.today()
    if job.date_found <= today - timedelta(days=EXPIRATION_DAYS):
        return True
    haystack = " ".join(
        [job.title, job.company, job.location, job.notes, job.fit_summary, job.requirements_summary, job.raw_text]
    ).lower()
    return any(re.search(pattern, haystack) for pattern in CLOSED_PATTERNS)
