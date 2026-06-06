from __future__ import annotations

import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from job_search_agent.models import JobRecord


TRACKING_PARAMS = {"trk", "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content"}


def dedupe_key(job: JobRecord) -> str:
    return "|".join(
        [
            _normalize(job.company),
            _normalize(job.title),
            _normalize_url(str(job.url)),
        ]
    )


def unique_jobs(jobs: list[JobRecord], existing_keys: set[str] | None = None) -> list[JobRecord]:
    seen = set(existing_keys or set())
    unique: list[JobRecord] = []
    for job in jobs:
        key = dedupe_key(job)
        if key in seen:
            continue
        seen.add(key)
        unique.append(job)
    return unique


def _normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def _normalize_url(url: str) -> str:
    if not url:
        return ""
    parts = urlsplit(url)
    query = urlencode([(k, v) for k, v in parse_qsl(parts.query) if k not in TRACKING_PARAMS])
    return urlunsplit((parts.scheme, parts.netloc.lower(), parts.path.rstrip("/"), query, ""))
