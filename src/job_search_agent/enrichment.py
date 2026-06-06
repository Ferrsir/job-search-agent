from __future__ import annotations

import logging
from urllib.parse import quote_plus, unquote, urlparse

import requests
from bs4 import BeautifulSoup

from job_search_agent.models import JobRecord
from job_search_agent.public_sources import discover_public_jobs
from job_search_agent.requirements import summarize_requirements


LOGGER = logging.getLogger(__name__)

CANONICAL_PUBLIC_DOMAINS = (
    "greenhouse.io",
    "lever.co",
    "ashbyhq.com",
    "workdayjobs.com",
    "myworkdayjobs.com",
    "pinpointhq.com",
    "smartrecruiters.com",
    "icims.com",
)

PRIVATE_ALERT_DOMAINS = (
    "linkedin.com",
    "joinhandshake.com",
    "handshake.com",
)


def enrich_alert_jobs(
    jobs: list[JobRecord],
    *,
    fetcher=requests.get,
    searcher=None,
    max_results_per_job: int = 5,
) -> list[JobRecord]:
    enriched: list[JobRecord] = []
    for job in jobs:
        if not _needs_enrichment(job):
            enriched.append(job)
            continue
        replacement = _public_enrichment(job, fetcher=fetcher, searcher=searcher, max_results=max_results_per_job)
        enriched.append(replacement or _fallback_requirements(job))
    return enriched


def _needs_enrichment(job: JobRecord) -> bool:
    if job.source not in {"LinkedIn", "Handshake"}:
        return False
    if job.requirements_summary and "manual review" not in job.requirements_summary.lower():
        return False
    return job.title != "Needs manual review" and job.company != "Needs manual review"


def _public_enrichment(job: JobRecord, *, fetcher, searcher, max_results: int) -> JobRecord | None:
    candidates = searcher(job, max_results=max_results) if searcher else _search_public_web(job, fetcher, max_results)
    for url in candidates:
        if not _is_public_candidate(url):
            continue
        try:
            discovered = discover_public_jobs([url], fetcher=fetcher, max_links_per_source=3)
        except requests.RequestException as exc:
            LOGGER.debug("Could not enrich %s from %s: %s", job.title, url, exc)
            continue
        match = _best_match(job, discovered)
        if not match:
            continue
        return _merge_enrichment(job, match)
    return None


def _search_public_web(job: JobRecord, fetcher, max_results: int) -> list[str]:
    query = f'"{job.title}" "{job.company}" {job.location} careers job'
    url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
    response = fetcher(url, timeout=20, headers={"User-Agent": "job-search-agent/0.1"})
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    urls: list[str] = []
    seen: set[str] = set()
    for link in soup.find_all("a", href=True):
        href = _unwrap_duckduckgo_url(link["href"])
        if href in seen or not href.startswith(("http://", "https://")):
            continue
        if not _is_public_candidate(href):
            continue
        seen.add(href)
        urls.append(href)
        if len(urls) >= max_results:
            break
    return urls


def _unwrap_duckduckgo_url(href: str) -> str:
    if "uddg=" not in href:
        return href
    return unquote(href.split("uddg=", 1)[1].split("&", 1)[0])


def _is_public_candidate(url: str) -> bool:
    host = urlparse(url).netloc.lower()
    if any(domain in host for domain in PRIVATE_ALERT_DOMAINS):
        return False
    if any(domain in host for domain in CANONICAL_PUBLIC_DOMAINS):
        return True
    path = urlparse(url).path.lower()
    return any(piece in path for piece in ("/careers", "/career", "/jobs", "/job", "/openings", "/positions"))


def _best_match(original: JobRecord, candidates: list[JobRecord]) -> JobRecord | None:
    original_title = _norm(original.title)
    original_company = _norm(original.company)
    for candidate in candidates:
        title = _norm(candidate.title)
        company = _norm(candidate.company)
        if original_title and (original_title in title or title in original_title):
            if not original_company or original_company in company or company in original_company:
                return candidate
    return candidates[0] if candidates else None


def _merge_enrichment(original: JobRecord, public: JobRecord) -> JobRecord:
    requirements = public.requirements_summary or summarize_requirements(public.raw_text)
    notes = public.fit_summary or public.notes or original.notes
    return original.model_copy(
        update={
            "location": public.location or original.location,
            "url": public.url or original.url,
            "source": f"{original.source} + public enrichment",
            "notes": notes,
            "fit_summary": public.fit_summary or original.fit_summary,
            "requirements_summary": requirements or _manual_review_note(original),
            "raw_text": " ".join([original.raw_text, public.raw_text])[:5000],
        }
    )


def _fallback_requirements(job: JobRecord) -> JobRecord:
    requirements = summarize_requirements(job.raw_text) if _has_requirement_signal(job.raw_text) else ""
    requirements = requirements or _manual_review_note(job)
    return job.model_copy(update={"requirements_summary": requirements})


def _manual_review_note(job: JobRecord) -> str:
    return f"Requirements need manual review; no public company or ATS posting found for this {job.source} alert."


def _has_requirement_signal(text: str) -> bool:
    lower = text.lower()
    return any(
        signal in lower
        for signal in (
            "requirements",
            "qualifications",
            "experience",
            "degree",
            "ability",
            "required",
            "preferred",
            "years",
            "clearance",
            "citizen",
        )
    )


def _norm(value: str) -> str:
    return " ".join(value.lower().replace("&", "and").split())
