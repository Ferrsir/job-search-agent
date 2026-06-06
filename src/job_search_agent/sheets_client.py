from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime

from google.oauth2.service_account import Credentials as ServiceAccountCredentials
from googleapiclient.errors import HttpError
from googleapiclient.discovery import build

from job_search_agent.analytics import analysis_sheet_values
from job_search_agent.calibration import CalibrationProfile, calibration_from_sheet_rows
from job_search_agent.dedupe import dedupe_key
from job_search_agent.lifecycle import is_expired_job
from job_search_agent.models import Classification, JobRecord, NetworkContact, ScoredJob
from job_search_agent.requirements import summarize_requirements
from job_search_agent.scoring import score_job, should_skip_job


SHEETS_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

ANALYSIS_COLUMNS = [
    "Geography",
    "Role Family",
    "Qualifications",
    "Salary Min",
    "Salary Max",
    "Salary Text",
    "Seniority",
    "Degree Requirement",
    "Clearance Requirement",
    "Work Mode",
    "Contact Strength",
]


@dataclass(frozen=True)
class ParsedSheetJob:
    title: str
    company: str
    location: str
    url: str
    fit_summary: str


class SheetsClient:
    def __init__(self, service, sheet_id: str):
        self.service = service
        self.sheet_id = sheet_id

    @classmethod
    def from_service_account_json(cls, service_account_json: dict, sheet_id: str) -> "SheetsClient":
        creds = ServiceAccountCredentials.from_service_account_info(service_account_json, scopes=SHEETS_SCOPES)
        return cls(build("sheets", "v4", credentials=creds), sheet_id)

    def existing_dedupe_keys(self, tabs: list[str] | None = None) -> set[str]:
        keys: set[str] = set()
        for tab in tabs or ["Active Roles", "Rejected Notable", "Expired"]:
            values = self._get_values(f"'{tab}'!A1:Z")
            header, body = _header_and_body(values)
            if header:
                key_index = _header_index(header, "dedupe key", "dedupe", "key")
                id_index = _header_index(header, "id", "job id")
                for row in body:
                    key = _cell(row, key_index) if key_index is not None else ""
                    key = key or (_cell(row, id_index) if id_index is not None else "")
                    parsed = _scored_from_row(row, destination_tab=tab, header=header)
                    keys.add(key or (dedupe_key(parsed.job) if parsed else ""))
                continue
            for row in values:
                if len(row) >= 3:
                    keys.add(row[7] if len(row) >= 8 and row[7] else "")
        return {key for key in keys if key}

    def append_scored_jobs(self, scored_jobs: list[ScoredJob]) -> None:
        self.ensure_analysis_columns()
        by_tab: dict[str, list[list[str]]] = {}
        for scored in scored_jobs:
            if should_skip_job(scored.job):
                continue
            by_tab.setdefault(scored.destination_tab, []).append(scored)
        for tab, scored_rows in by_tab.items():
            header_rows = self._get_values(f"'{tab}'!A1:Z")
            header, _ = _header_and_body(header_rows)
            rows = [_row_for_header(scored, header) if header else _row(scored) for scored in scored_rows]
            if not rows:
                continue
            self.service.spreadsheets().values().append(
                spreadsheetId=self.sheet_id,
                range=f"'{tab}'!A:Z",
                valueInputOption="USER_ENTERED",
                insertDataOption="INSERT_ROWS",
                body={"values": rows},
            ).execute()

    def ensure_analysis_columns(self, tabs: list[str] | None = None) -> None:
        for tab in tabs or ["Active Roles", "Rejected Notable", "Expired"]:
            values = self._get_values(f"'{tab}'!A1:Z1")
            if not values:
                continue
            header_row = values[0]
            existing = {_normalize_header(cell) for cell in header_row}
            missing = [column for column in ANALYSIS_COLUMNS if _normalize_header(column) not in existing]
            if not missing:
                continue
            updated = [*header_row, *missing]
            end_col = _column_letter(len(updated))
            self.service.spreadsheets().values().update(
                spreadsheetId=self.sheet_id,
                range=f"'{tab}'!A1:{end_col}1",
                valueInputOption="USER_ENTERED",
                body={"values": [updated]},
            ).execute()

    def backfill_analysis_columns(self, tabs: list[str] | None = None) -> dict[str, int]:
        updated_counts: dict[str, int] = {}
        target_tabs = tabs or ["Active Roles", "Rejected Notable", "Expired"]
        self.ensure_analysis_columns(target_tabs)
        for tab in target_tabs:
            values = self._get_values(f"'{tab}'!A1:AZ")
            header, body = _header_and_body(values)
            if not header:
                updated_counts[tab] = 0
                continue
            max_index = max(header.values(), default=0)
            changed = 0
            updated_body: list[list[str]] = []
            for row in body:
                updated = [*row]
                if len(updated) <= max_index:
                    updated.extend([""] * (max_index + 1 - len(updated)))
                scored = _scored_from_row(updated, destination_tab=tab, header=header)
                if scored:
                    analysis = analysis_sheet_values(scored)
                    for name, value in analysis.items():
                        index = _header_index(header, name)
                        if index is not None and updated[index] != value:
                            updated[index] = value
                            changed += 1
                updated_body.append(updated)
            updated_counts[tab] = changed
            if changed:
                header_row = values[0]
                if len(header_row) <= max_index:
                    header_row = [*header_row, *([""] * (max_index + 1 - len(header_row)))]
                end_col = _column_letter(max_index + 1)
                self.service.spreadsheets().values().update(
                    spreadsheetId=self.sheet_id,
                    range=f"'{tab}'!A1:{end_col}{len(updated_body) + 1}",
                    valueInputOption="USER_ENTERED",
                    body={"values": [header_row, *updated_body]},
                ).execute()
        return updated_counts

    def public_source_urls(self) -> list[str]:
        rows = self._get_values("'Source List'!A2:Z")
        urls: list[str] = []
        for row in rows:
            for cell in row:
                if isinstance(cell, str) and cell.startswith(("http://", "https://")):
                    urls.append(cell)
                    break
        return list(dict.fromkeys(urls))

    def calibration_profile(self) -> CalibrationProfile:
        rows = self._get_values("'Calibration Examples'!A1:Z")
        return calibration_from_sheet_rows(rows)

    def backend_scored_jobs(self) -> list[ScoredJob]:
        active_rows = self._get_values("'Active Roles'!A1:Z")
        rejected_rows = self._get_values("'Rejected Notable'!A1:Z")
        expired_rows = self._get_values("'Expired'!A1:Z")
        return [
            scored
            for scored in scored_jobs_from_sheet_rows(active_rows, rejected_rows, expired_rows)
            if not should_skip_job(scored.job)
        ]

    def _get_values(self, range_name: str) -> list[list[str]]:
        try:
            response = (
                self.service.spreadsheets()
                .values()
                .get(spreadsheetId=self.sheet_id, range=range_name)
                .execute()
            )
        except HttpError as exc:
            if "Expired" in range_name and exc.resp.status in {400, 404}:
                return []
            raise
        return response.get("values", [])


def _row(scored: ScoredJob) -> list[str]:
    job = scored.job
    analysis = analysis_sheet_values(scored)
    return [
        job.date_found.isoformat(),
        job.title,
        job.company,
        job.location,
        str(job.url),
        job.source,
        str(scored.total_score),
        dedupe_key(job),
        _short_fit_summary(scored),
        _requirements_summary(scored),
        analysis["geography"],
        analysis["role family"],
        analysis["qualifications"],
        analysis["salary min"],
        analysis["salary max"],
        analysis["salary text"],
        analysis["seniority"],
        analysis["degree requirement"],
        analysis["clearance requirement"],
        analysis["work mode"],
        analysis["contact strength"],
    ]


def _row_for_header(scored: ScoredJob, header: dict[str, int]) -> list[str]:
    size = max(header.values(), default=9) + 1
    row = [""] * size

    def set_cell(value: str, *names: str) -> None:
        for name in names:
            index = header.get(_normalize_header(name))
            if index is not None:
                row[index] = value
                return

    job = scored.job
    key = dedupe_key(job)
    set_cell(key, "id", "job id")
    set_cell(job.date_found.isoformat(), "date found", "date")
    set_cell(job.company, "company", "organization", "employer")
    set_cell(job.title, "role", "title", "job title", "position")
    set_cell(job.location, "city", "location")
    set_cell("Remote" if "remote" in job.location.lower() else "", "work mode")
    set_cell(str(job.url), "url", "link", "posting url")
    set_cell(job.source, "source")
    set_cell(str(scored.total_score), "score", "match score")
    set_cell(key, "dedupe key", "dedupe", "key")
    set_cell(_short_fit_summary(scored), "fit summary", "why", "why fit", "rationale", "recommendation", "notes")
    set_cell(_requirements_summary(scored), "main requirements", "requirements", "job requirements", "qualifications")
    set_cell(scored.job.network_summary, "network summary", "network signals", "first reach summary")
    set_cell(_network_contacts_text(scored.job.network_contacts), "first reach contacts", "network contacts", "warm intro contacts")
    analysis = analysis_sheet_values(scored)
    for name, value in analysis.items():
        set_cell(value, name)
    return row


def scored_jobs_from_sheet_rows(
    active_rows: list[list[str]],
    rejected_rows: list[list[str]] | None = None,
    expired_rows: list[list[str]] | None = None,
) -> list[ScoredJob]:
    scored: list[ScoredJob] = []
    active_header, active_body = _header_and_body(active_rows)
    rejected_header, rejected_body = _header_and_body(rejected_rows or [])
    expired_header, expired_body = _header_and_body(expired_rows or [])
    for row in active_body:
        parsed = _scored_from_row(row, destination_tab="Active Roles", header=active_header)
        if parsed:
            scored.append(parsed)
    for row in rejected_body:
        parsed = _scored_from_row(row, destination_tab="Rejected Notable", header=rejected_header)
        if parsed:
            scored.append(parsed)
    for row in expired_body:
        parsed = _scored_from_row(row, destination_tab="Expired", header=expired_header)
        if parsed:
            scored.append(parsed)
    return scored


def _scored_from_row(row: list[str], destination_tab: str, header: dict[str, int] | None = None) -> ScoredJob | None:
    if header:
        return _scored_from_header_row(row, destination_tab, header)
    if len(row) < 4:
        return None
    title = _cell(row, 1)
    company = _cell(row, 2)
    if not title or not company:
        return None
    location = _cell(row, 3)
    url = _cell(row, 4)
    source = _cell(row, 5) or "Google Sheet"
    score = _parse_score(_cell(row, 6))
    fit_summary = _cell(row, 8)
    requirements_summary = _cell(row, 9)
    date_found = _parse_date(_cell(row, 0))
    job = JobRecord(
        title=title,
        company=company,
        location=location,
        url=url,
        source=source,
        source_email_id="google-sheet",
        date_found=date_found,
        fit_summary=fit_summary,
        requirements_summary=requirements_summary,
        raw_text=" ".join(cell for cell in row if cell),
    )
    labels = _labels_from_sheet_row(score, location, destination_tab, job)
    fit_summary = fit_summary or _fit_summary_from_signals(
        title=title,
        company=company,
        location=location,
        sector="",
        score=score,
        destination_tab=destination_tab,
    )
    job.fit_summary = fit_summary
    rationale = [fit_summary, f"Sheet score: {score}", f"Source: {source}"]
    return ScoredJob(
        job=job,
        total_score=score,
        labels=labels,
        score_breakdown={"Sheet score": score},
        rationale=rationale,
        destination_tab="Expired" if Classification.EXPIRED in labels else destination_tab,
    )


def _scored_from_header_row(row: list[str], destination_tab: str, header: dict[str, int]) -> ScoredJob | None:
    title = _header_cell(row, header, "role", "title", "job title", "position")
    company = _header_cell(row, header, "company", "organization", "employer")
    if not title or not company:
        return None
    city = _header_cell(row, header, "city", "location")
    location_type = _header_cell(row, header, "location type")
    work_mode = _header_cell(row, header, "work mode")
    location = city or " / ".join(item for item in [location_type, work_mode] if item)
    url = _header_cell(row, header, "url", "link", "posting url")
    source = _header_cell(row, header, "source") or "Google Sheet"
    if not _is_http_url(url) and _is_http_url(source):
        url, source = source, url or "Google Sheet"
    sheet_row_id = _header_cell(row, header, "id", "job id")
    date_found = _parse_date(_header_cell(row, header, "date found", "date", "found date"))
    source_email_id = f"google-sheet:{sheet_row_id}" if sheet_row_id else "google-sheet"
    sector = _header_cell(row, header, "sector", "industry")
    organization_type = _header_cell(row, header, "organization type", "org type", "company type")
    fit_summary = _header_cell(
        row,
        header,
        "fit summary",
        "why",
        "why fit",
        "rationale",
        "recommendation",
        "notes",
        "decision",
    )
    repaired = _repair_packed_sheet_job(
        title=title,
        company=company,
        location=location,
        url=url,
        fit_summary=fit_summary,
    )
    title = repaired.title
    company = repaired.company
    location = repaired.location
    url = repaired.url
    fit_summary = repaired.fit_summary
    if _looks_like_company_token(title) and _looks_like_job_title(company):
        title, company = company, _clean_packed_company(title)
    requirements_summary = _header_cell(
        row,
        header,
        "main requirements",
        "requirements",
        "job requirements",
        "qualifications",
        "minimum qualifications",
    )
    network_summary = _header_cell(row, header, "network summary", "network signals", "first reach summary")
    network_contacts = _network_contacts_from_text(
        _header_cell(row, header, "first reach contacts", "network contacts", "warm intro contacts")
    )
    raw_text = " ".join(cell for cell in row if cell)
    job = JobRecord(
        title=title,
        company=company,
        location=location,
        url=url,
        source=source,
        source_email_id=source_email_id,
        date_found=date_found,
        notes=fit_summary,
        fit_summary=fit_summary,
        requirements_summary=requirements_summary,
        network_summary=network_summary,
        network_contacts=network_contacts,
        raw_text=" ".join(item for item in [raw_text, sector, organization_type, location_type, work_mode] if item),
    )
    score_value = _header_cell(row, header, "score", "match score")
    if score_value:
        score = _parse_score(score_value)
        labels = _labels_from_sheet_row(score, location, destination_tab, job)
        fit_summary = fit_summary or _fit_summary_from_signals(
            title=title,
            company=company,
            location=location,
            sector=sector or organization_type,
            score=score,
            destination_tab=destination_tab,
        )
        job.fit_summary = fit_summary
        rationale = [fit_summary]
        rationale.extend([f"Sheet score: {score}", f"Source: {source}"])
        return ScoredJob(
            job=job,
            total_score=score,
            labels=labels,
            score_breakdown={"Sheet score": score},
            rationale=rationale,
            destination_tab="Expired" if Classification.EXPIRED in labels else destination_tab,
        )
    scored = score_job(job)
    fit_summary = fit_summary or _fit_summary_from_scored(
        scored,
        sector=sector or organization_type,
        destination_tab=destination_tab,
    )
    scored = scored.model_copy(
        update={
            "job": scored.job.model_copy(
                update={
                    "fit_summary": fit_summary,
                    "notes": fit_summary,
                    "requirements_summary": requirements_summary or scored.job.requirements_summary,
                    "network_summary": network_summary,
                    "network_contacts": network_contacts,
                }
            )
        }
    )
    if destination_tab == "Rejected Notable":
        return scored.model_copy(update={"labels": [Classification.REJECTED_NOTABLE], "destination_tab": destination_tab})
    if destination_tab == "Expired" or is_expired_job(scored.job):
        labels = list(dict.fromkeys([Classification.EXPIRED, *scored.labels]))
        return scored.model_copy(update={"labels": labels, "destination_tab": "Expired"})
    return scored.model_copy(update={"destination_tab": destination_tab})


def _labels_from_sheet_row(
    score: int,
    location: str,
    destination_tab: str,
    job: JobRecord | None = None,
) -> list[Classification]:
    if destination_tab == "Expired" or (job and is_expired_job(job)):
        return [Classification.EXPIRED]
    if destination_tab == "Rejected Notable":
        return [Classification.REJECTED_NOTABLE]
    labels: list[Classification] = []
    if score >= 75:
        labels.append(Classification.APPLY_NOW)
    elif score >= 62:
        labels.append(Classification.WARM_INTRO_FIRST)
    else:
        labels.append(Classification.MONITOR)
    loc = location.lower()
    if "remote" in loc:
        labels.append(Classification.REMOTE_MATCH)
    if "austin" in loc:
        labels.append(Classification.AUSTIN_MATCH)
    if "dallas" in loc or "fort worth" in loc or "dfw" in loc:
        labels.append(Classification.DALLAS_MATCH)
    return labels


def _parse_date(value: str) -> date:
    if not value:
        return date.today()
    cleaned = value.strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y"):
        try:
            return datetime.strptime(cleaned.split("T", 1)[0], fmt).date()
        except ValueError:
            continue
    try:
        return date.fromisoformat(cleaned.split("T", 1)[0])
    except ValueError:
        return date.today()


def _cell(row: list[str], index: int) -> str:
    return row[index].strip() if index < len(row) and isinstance(row[index], str) else ""


def _header_and_body(rows: list[list[str]]) -> tuple[dict[str, int] | None, list[list[str]]]:
    if not rows:
        return None, []
    normalized = [_normalize_header(cell) for cell in rows[0]]
    if {"company", "role"} & set(normalized) or "url" in normalized:
        return {name: index for index, name in enumerate(normalized) if name}, rows[1:]
    return None, rows


def _header_cell(row: list[str], header: dict[str, int], *names: str) -> str:
    for name in names:
        index = _header_index(header, name)
        if index is not None:
            value = _cell(row, index)
            if value:
                return value
    return ""


def _header_index(header: dict[str, int], *names: str) -> int | None:
    for name in names:
        index = header.get(_normalize_header(name))
        if index is not None:
            return index
    return None


def _normalize_header(value: str) -> str:
    return " ".join(value.strip().lower().replace("_", " ").replace("-", " ").split())


def _column_letter(index: int) -> str:
    letters = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters


def _repair_packed_sheet_job(
    *,
    title: str,
    company: str,
    location: str,
    url: str,
    fit_summary: str,
) -> ParsedSheetJob:
    packed = _packed_job_from_text(location) or _packed_job_from_text(fit_summary) or _packed_job_from_text(url)
    if not packed:
        return ParsedSheetJob(title=title, company=company, location=location, url=url, fit_summary=fit_summary)
    packed_company, packed_title, packed_url = packed
    existing_title_is_location = _looks_like_location(title)
    repaired_company = _prefer_existing_company(company, packed_company)
    repaired_title = _clean_packed_title(packed_title) if existing_title_is_location or _looks_packed(location) else title
    repaired_location = title if existing_title_is_location else location
    repaired_url = url if url.startswith(("http://", "https://")) and not _looks_packed(url) else packed_url
    repaired_fit_summary = fit_summary
    if _looks_packed(fit_summary) or _looks_packed(location):
        repaired_fit_summary = ""
    return ParsedSheetJob(
        title=repaired_title,
        company=repaired_company,
        location=repaired_location,
        url=repaired_url,
        fit_summary=repaired_fit_summary,
    )


def _packed_job_from_text(value: str) -> tuple[str, str, str] | None:
    if not _looks_packed(value):
        return None
    parts = [part.strip() for part in value.split("|") if part.strip()]
    for index in range(len(parts) - 2):
        company, title, url = parts[index], parts[index + 1], parts[index + 2]
        if url.startswith(("http://", "https://")) and company and title:
            return company, title, url
    return None


def _is_http_url(value: str) -> bool:
    return value.startswith(("http://", "https://"))


def _looks_packed(value: str) -> bool:
    return "|" in value and "http" in value


def _looks_like_company_token(value: str) -> bool:
    normalized = value.strip()
    if not normalized or len(normalized) > 32 or " " in normalized:
        return False
    return _company_key(normalized) in {"cesiumastro", "shieldai", "fedtech", "skyways"} or normalized.islower()


def _looks_like_job_title(value: str) -> bool:
    normalized = value.lower()
    return any(
        term in normalized
        for term in [
            "associate",
            "business development",
            "chief of staff",
            "communications",
            "contracts",
            "director",
            "lead",
            "manager",
            "operations",
            "program",
            "specialist",
        ]
    )


def _looks_like_location(value: str) -> bool:
    normalized = value.strip().lower()
    if not normalized:
        return False
    if any(term in normalized for term in ["remote", "hybrid", "metropolitan area"]):
        return True
    if re.search(r"\b[A-Z]{2}\b", value):
        return True
    return normalized in {
        "austin",
        "austin, tx",
        "dallas",
        "dallas, tx",
        "washington d.c.",
        "washington, dc",
        "redondo beach",
        "redondo beach, ca",
        "mojave",
        "new delhi",
        "the hague",
        "tokyo",
        "riyadh",
    }


def _prefer_existing_company(existing: str, packed: str) -> str:
    existing_normalized = _company_key(existing)
    packed_normalized = _company_key(packed)
    if existing_normalized and existing_normalized == packed_normalized:
        return existing
    return _clean_packed_company(packed)


def _company_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def _clean_packed_company(value: str) -> str:
    known = {
        "cesiumastro": "CesiumAstro",
        "shieldai": "Shield AI",
        "fedtech": "FedTech",
    }
    key = _company_key(value)
    return known.get(key, value.strip().title())


def _clean_packed_title(value: str) -> str:
    words = value.replace("-", " ").split()
    small_words = {"and", "of", "the", "for", "to", "in", "at", "with"}
    cleaned: list[str] = []
    for index, word in enumerate(words):
        lower = word.lower()
        if lower in {"fp&a", "r&d", "ai", "us", "u.s.", "dc", "d.c."}:
            cleaned.append(lower.upper().replace("U.S.", "U.S."))
        elif index > 0 and lower in small_words:
            cleaned.append(lower)
        else:
            cleaned.append(lower.capitalize())
    return " ".join(cleaned)


def _fit_summary_from_scored(scored: ScoredJob, *, sector: str, destination_tab: str) -> str:
    return _fit_summary_from_signals(
        title=scored.job.title,
        company=scored.job.company,
        location=scored.job.location,
        sector=sector,
        score=scored.total_score,
        destination_tab=destination_tab,
    )


def _fit_summary_from_signals(
    *,
    title: str,
    company: str,
    location: str,
    sector: str,
    score: int,
    destination_tab: str,
) -> str:
    context = []
    if sector:
        context.append(sector)
    if location:
        context.append(location)
    context_text = " and ".join(context)
    if destination_tab == "Rejected Notable" or score < 50:
        if context_text:
            return f"Useful calibration lead in {context_text}, but likely a weaker fit for the current search."
        return f"Useful calibration lead at {company}, but likely a weaker fit for the current search."
    if score >= 75:
        if context_text:
            return f"Strong fit because it combines relevant {context_text} signals with a role worth prioritizing."
        return f"Strong fit at {company}; worth prioritizing for review."
    if context_text:
        return f"Promising direction because it matches relevant {context_text} signals; review role requirements before prioritizing."
    return f"Promising direction at {company}; review role requirements before prioritizing."


def _parse_score(value: str) -> int:
    try:
        return max(0, min(100, int(float(value))))
    except ValueError:
        return 0


def _short_fit_summary(scored: ScoredJob) -> str:
    if scored.job.fit_summary:
        return scored.job.fit_summary[:180]
    if scored.job.notes:
        return scored.job.notes[:180]
    if scored.rationale:
        return scored.rationale[0][:180]
    return "Needs review against current preferences."


def _requirements_summary(scored: ScoredJob) -> str:
    if scored.job.requirements_summary:
        return scored.job.requirements_summary[:260]
    return summarize_requirements(" ".join([scored.job.raw_text, scored.job.notes]))[:260]


def _network_contacts_text(contacts: list[NetworkContact]) -> str:
    return "; ".join(
        " - ".join(item for item in [contact.name, contact.company, contact.position, contact.profile_url] if item)
        for contact in contacts
    )


def _network_contacts_from_text(value: str) -> list[NetworkContact]:
    contacts: list[NetworkContact] = []
    for item in [part.strip() for part in value.split(";") if part.strip()]:
        pieces = [part.strip() for part in item.split(" - ")]
        contacts.append(
            NetworkContact(
                name=pieces[0] if pieces else "",
                company=pieces[1] if len(pieces) > 1 else "",
                position=pieces[2] if len(pieces) > 2 else "",
                profile_url=pieces[3] if len(pieces) > 3 else "",
                reason="Sheet-backed first reach",
            )
        )
    return [contact for contact in contacts if contact.name]
