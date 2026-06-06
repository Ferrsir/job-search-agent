from __future__ import annotations

import re
from datetime import date

from bs4 import BeautifulSoup

from job_search_agent.models import JobRecord
from job_search_agent.parsers.common import collapse_space, html_to_text


LINKEDIN_JOB_RE = re.compile(r"https?://[^\s\"'<]+linkedin\.com/jobs/[^\s\"'<]+", re.I)


def parse_linkedin_email(
    *,
    html: str = "",
    text: str = "",
    message_id: str,
    received_date: date | None = None,
    alert_name: str = "",
) -> list[JobRecord]:
    body_text = html_to_text(html) if html else text
    jobs = _parse_from_html(html, body_text, message_id, received_date, alert_name)
    if jobs:
        return jobs
    return _parse_from_text(body_text, message_id, received_date, alert_name)


def _parse_from_html(
    html: str,
    body_text: str,
    message_id: str,
    received_date: date | None,
    alert_name: str,
) -> list[JobRecord]:
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    records: list[JobRecord] = []
    seen_urls: set[str] = set()
    for link in soup.find_all("a", href=True):
        href = link["href"]
        if "linkedin.com/jobs" not in href:
            continue
        title = collapse_space(link.get_text(" "))
        if not title or title.lower() in {"view job", "apply", "see job"}:
            title = "Needs manual review"
        container_text = collapse_space(_nearest_container_text(link))
        company, location = _extract_company_location(container_text, title)
        records.append(
            JobRecord(
                title=title,
                company=company or "Needs manual review",
                location=location,
                url=href,
                source="LinkedIn",
                source_email_id=message_id,
                source_alert_name=alert_name,
                date_found=received_date or date.today(),
                notes="Needs manual review" if "Needs manual review" in {title, company} else "",
                raw_text=container_text[:2000] or body_text[:2000],
            )
        )
        seen_urls.add(href)
    for url in LINKEDIN_JOB_RE.findall(body_text):
        if url in seen_urls:
            continue
        records.append(
            JobRecord(
                title="Needs manual review",
                company="Needs manual review",
                url=url,
                source="LinkedIn",
                source_email_id=message_id,
                source_alert_name=alert_name,
                date_found=received_date or date.today(),
                notes="LinkedIn alert did not expose full details. Needs manual review.",
                raw_text=body_text[:2000],
            )
        )
    return records


def _parse_from_text(
    body_text: str,
    message_id: str,
    received_date: date | None,
    alert_name: str,
) -> list[JobRecord]:
    records: list[JobRecord] = []
    chunks = re.split(r"\n\s*\n", body_text)
    for chunk in chunks:
        url_match = LINKEDIN_JOB_RE.search(chunk)
        if not url_match:
            continue
        lines = [
            collapse_space(LINKEDIN_JOB_RE.sub("", line))
            for line in chunk.splitlines()
            if collapse_space(LINKEDIN_JOB_RE.sub("", line))
        ]
        title = lines[0] if len(lines) > 1 else "Needs manual review"
        company = lines[1] if len(lines) > 1 else "Needs manual review"
        location = lines[2] if len(lines) > 2 else ""
        records.append(
            JobRecord(
                title=title,
                company=company,
                location=location,
                url=url_match.group(0),
                source="LinkedIn",
                source_email_id=message_id,
                source_alert_name=alert_name,
                date_found=received_date or date.today(),
                notes="Needs manual review" if "Needs manual review" in {title, company} else "",
                raw_text=chunk[:2000],
            )
        )
    return records


def _nearest_container_text(link) -> str:
    node = link
    for _ in range(4):
        if node.parent is None:
            break
        node = node.parent
        text = collapse_space(node.get_text(" "))
        if len(text) > 30:
            return text
    return collapse_space(link.get_text(" "))


def _extract_company_location(container_text: str, title: str) -> tuple[str, str]:
    cleaned = container_text.replace(title, "", 1).strip(" -|")
    parts = [p.strip(" -|") for p in re.split(r"\s{2,}| · | \| |\n", cleaned) if p.strip(" -|")]
    company = parts[0] if parts else ""
    location = ""
    for part in parts[1:]:
        if re.search(r"\b(remote|austin|dallas|fort worth|texas|washington|dc|hybrid)\b", part, re.I):
            location = part
            break
    return company, location
