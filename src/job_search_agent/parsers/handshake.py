from __future__ import annotations

import re
from datetime import date

from job_search_agent.models import JobRecord
from job_search_agent.parsers.common import collapse_space, html_to_text


HANDSHAKE_JOB_RE = re.compile(r"https?://[^\s\"'<]+joinhandshake\.com/[^\s\"'<]+", re.I)


def parse_handshake_email(
    *,
    html: str = "",
    text: str = "",
    message_id: str,
    received_date: date | None = None,
    alert_name: str = "",
) -> list[JobRecord]:
    body_text = html_to_text(html) if html else text
    records: list[JobRecord] = []
    for chunk in re.split(r"\n\s*\n", body_text):
        url_match = HANDSHAKE_JOB_RE.search(chunk)
        if not url_match:
            continue
        lines = [collapse_space(line) for line in chunk.splitlines() if collapse_space(line)]
        records.append(
            JobRecord(
                title=lines[0] if lines else "Needs manual review",
                company=lines[1] if len(lines) > 1 else "Needs manual review",
                location=lines[2] if len(lines) > 2 else "",
                url=url_match.group(0),
                source="Handshake",
                source_email_id=message_id,
                source_alert_name=alert_name,
                date_found=received_date or date.today(),
                notes="Needs manual review",
                raw_text=chunk[:2000],
            )
        )
    return records
