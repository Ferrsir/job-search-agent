from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from pathlib import Path

from job_search_agent.models import NetworkContact, ScoredJob


@dataclass(frozen=True)
class LinkedInConnection:
    name: str
    company: str = ""
    position: str = ""
    profile_url: str = ""


@dataclass(frozen=True)
class LinkedInNetwork:
    connections: list[LinkedInConnection] = field(default_factory=list)
    followed_companies: set[str] = field(default_factory=set)
    searched_terms: list[str] = field(default_factory=list)
    saved_jobs: list[str] = field(default_factory=list)
    applied_jobs: list[str] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)
    profile_summary: str = ""

    @classmethod
    def from_dirs(cls, dirs: list[Path]) -> "LinkedInNetwork":
        networks = [cls.from_dir(path) for path in dirs if path.exists()]
        return cls.merge(networks)

    @classmethod
    def from_dir(cls, root: Path) -> "LinkedInNetwork":
        return cls(
            connections=_load_connections(root / "Connections.csv"),
            followed_companies=_load_first_column_set(root / "Company Follows.csv"),
            searched_terms=_load_search_queries(root / "SearchQueries.csv"),
            saved_jobs=_load_job_pairs(root / "Jobs" / "Saved Jobs.csv"),
            applied_jobs=_load_job_pairs(root / "Jobs" / "Job Applications.csv"),
            skills=_load_first_column_list(root / "Skills.csv"),
            profile_summary=_load_profile_summary(root / "Profile.csv"),
        )

    @classmethod
    def merge(cls, networks: list["LinkedInNetwork"]) -> "LinkedInNetwork":
        connections_by_key: dict[str, LinkedInConnection] = {}
        followed: set[str] = set()
        searches: list[str] = []
        saved: list[str] = []
        applied: list[str] = []
        skills: list[str] = []
        summary = ""
        for network in networks:
            for connection in network.connections:
                key = "|".join(
                    [
                        _normalize(connection.name),
                        _normalize(connection.company),
                        _normalize(connection.position),
                    ]
                )
                connections_by_key.setdefault(key, connection)
            followed.update(network.followed_companies)
            searches.extend(network.searched_terms)
            saved.extend(network.saved_jobs)
            applied.extend(network.applied_jobs)
            skills.extend(network.skills)
            summary = summary or network.profile_summary
        return cls(
            connections=list(connections_by_key.values()),
            followed_companies=followed,
            searched_terms=_dedupe(searches),
            saved_jobs=_dedupe(saved),
            applied_jobs=_dedupe(applied),
            skills=_dedupe(skills),
            profile_summary=summary,
        )


def enrich_jobs_with_network(scored_jobs: list[ScoredJob], network: LinkedInNetwork | None) -> list[ScoredJob]:
    if not network:
        return scored_jobs
    return [_enrich_job(scored, network) for scored in scored_jobs]


def _enrich_job(scored: ScoredJob, network: LinkedInNetwork) -> ScoredJob:
    contacts = recommend_contacts(scored, network)
    summary = summarize_network_fit(scored, network, contacts)
    if not contacts and not summary:
        return scored
    return scored.model_copy(
        update={
            "job": scored.job.model_copy(
                update={
                    "network_contacts": contacts,
                    "network_summary": summary,
                }
            )
        }
    )


def recommend_contacts(scored: ScoredJob, network: LinkedInNetwork, limit: int = 3) -> list[NetworkContact]:
    company = scored.job.company
    title = scored.job.title
    scored_contacts: list[tuple[int, LinkedInConnection, str]] = []
    for connection in network.connections:
        points, reason = _contact_match_score(connection, company, title)
        if points > 0:
            scored_contacts.append((points, connection, reason))
    scored_contacts.sort(key=lambda item: (-item[0], item[1].name))
    return [
        NetworkContact(
            name=connection.name,
            company=connection.company,
            position=connection.position,
            profile_url=connection.profile_url,
            reason=reason,
        )
        for _, connection, reason in scored_contacts[:limit]
    ]


def summarize_network_fit(
    scored: ScoredJob,
    network: LinkedInNetwork,
    contacts: list[NetworkContact] | None = None,
) -> str:
    company = scored.job.company
    title = scored.job.title
    signals: list[str] = []
    contacts = contacts or []
    if contacts:
        top = contacts[0]
        if top.company:
            signals.append(f"{top.name} appears connected to {top.company}")
        else:
            signals.append(f"{top.name} is a possible first reach")
    if _contains_company(network.followed_companies, company):
        signals.append(f"you already follow {company}")
    if _contains_term(network.searched_terms, company):
        signals.append(f"you have searched for {company}")
    if _contains_term(network.searched_terms, title):
        signals.append("your LinkedIn search history overlaps with this role family")
    if _contains_term(network.saved_jobs, company) or _contains_term(network.saved_jobs, title):
        signals.append("similar roles were saved on LinkedIn")
    if _contains_term(network.applied_jobs, company) or _contains_term(network.applied_jobs, title):
        signals.append("your application history has adjacent roles")
    if not signals:
        return ""
    return "; ".join(signals[:3]) + "."


def _contact_match_score(connection: LinkedInConnection, company: str, title: str) -> tuple[int, str]:
    company_norm = _normalize(company)
    contact_company_norm = _normalize(connection.company)
    position_norm = _normalize(connection.position)
    title_tokens = _tokens(title)
    score = 0
    reasons: list[str] = []
    if company_norm and contact_company_norm == company_norm:
        score += 100
        reasons.append("current company match")
    elif company_norm and contact_company_norm and min(len(company_norm), len(contact_company_norm)) >= 4 and (
        company_norm in contact_company_norm or contact_company_norm in company_norm
    ):
        score += 72
        reasons.append("company name overlap")
    if score == 0:
        return 0, ""
    shared_title_tokens = title_tokens & _tokens(connection.position)
    useful_shared = shared_title_tokens - {"manager", "associate", "senior", "lead", "analyst", "director"}
    if useful_shared:
        score += min(20, 6 * len(useful_shared))
        reasons.append("role-family overlap")
    if any(term in position_norm for term in ["founder", "recruit", "talent", "people", "chief", "ceo", "coo"]):
        score += 10
        reasons.append("likely useful intro path")
    return score, ", ".join(reasons)


def _load_connections(path: Path) -> list[LinkedInConnection]:
    rows = _dict_rows(path, required_header="First Name")
    connections: list[LinkedInConnection] = []
    for row in rows:
        first = row.get("First Name", "").strip()
        last = row.get("Last Name", "").strip()
        name = " ".join(part for part in [first, last] if part)
        if not name:
            continue
        connections.append(
            LinkedInConnection(
                name=name,
                company=row.get("Company", "").strip(),
                position=row.get("Position", "").strip(),
                profile_url=row.get("URL", "").strip(),
            )
        )
    return connections


def _load_first_column_set(path: Path) -> set[str]:
    return set(_load_first_column_list(path))


def _load_first_column_list(path: Path) -> list[str]:
    rows = _rows(path)
    if len(rows) < 2:
        return []
    return _dedupe(row[0].strip() for row in rows[1:] if row)


def _load_search_queries(path: Path) -> list[str]:
    rows = _dict_rows(path, required_header="Search Query")
    return _dedupe(row.get("Search Query", "").strip() for row in rows)


def _load_job_pairs(path: Path) -> list[str]:
    rows = _dict_rows(path, required_header="Job Title")
    pairs: list[str] = []
    for row in rows:
        company = row.get("Company Name", "").strip()
        title = row.get("Job Title", "").strip() or row.get("Title", "").strip()
        pair = " ".join(item for item in [company, title] if item)
        if pair:
            pairs.append(pair)
    return _dedupe(pairs)


def _load_profile_summary(path: Path) -> str:
    rows = _dict_rows(path, required_header="First Name")
    if not rows:
        return ""
    return rows[0].get("Summary", "").strip()


def _dict_rows(path: Path, required_header: str) -> list[dict[str, str]]:
    rows = _rows(path)
    header_index = next((index for index, row in enumerate(rows) if required_header in row), None)
    if header_index is None:
        return []
    header = rows[header_index]
    return [dict(zip(header, row, strict=False)) for row in rows[header_index + 1 :] if any(cell.strip() for cell in row)]


def _rows(path: Path) -> list[list[str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8-sig", errors="replace") as handle:
        return [[cell.strip() for cell in row] for row in csv.reader(handle)]


def _contains_company(values: set[str], company: str) -> bool:
    company_norm = _normalize(company)
    return any(_normalize(value) == company_norm for value in values if value)


def _contains_term(values: list[str], needle: str) -> bool:
    needle_norm = _normalize(needle)
    if not needle_norm:
        return False
    return any(needle_norm in _normalize(value) or _normalize(value) in needle_norm for value in values if value)


def _normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def _tokens(value: str) -> set[str]:
    return {token for token in _normalize(value).split() if len(token) > 2}


def _dedupe(values) -> list[str]:
    seen: set[str] = set()
    items: list[str] = []
    for value in values:
        if not value:
            continue
        key = value.lower()
        if key in seen:
            continue
        seen.add(key)
        items.append(value)
    return items
