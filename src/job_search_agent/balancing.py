from __future__ import annotations

import re
from collections import Counter

from job_search_agent.models import Classification, ScoredJob


SECTOR_CAPS = {
    "Space / Defense": 0.35,
    "Finance / Capital": 0.35,
    "Strategy / Partnerships": 0.45,
    "Policy / Research": 0.25,
    "Other": 0.20,
}

DEFAULT_MAX_PER_COMPANY = 6
DEFAULT_MAX_RESULTS = 30


def balance_scored_jobs(
    scored_jobs: list[ScoredJob],
    *,
    max_results: int = DEFAULT_MAX_RESULTS,
    max_per_company: int = DEFAULT_MAX_PER_COMPANY,
) -> list[ScoredJob]:
    if not scored_jobs:
        return []
    target = min(max_results, len(scored_jobs))
    sector_limits = {sector: max(1, round(target * share)) for sector, share in SECTOR_CAPS.items()}
    ordered = sorted(scored_jobs, key=_priority_key)
    selected: list[ScoredJob] = []
    company_counts: Counter[str] = Counter()
    sector_counts: Counter[str] = Counter()

    for scored in ordered:
        if len(selected) >= target:
            break
        company = _company_key(scored.job.company)
        sector = search_sector(scored)
        if company and company_counts[company] >= max_per_company:
            continue
        if sector_counts[sector] >= sector_limits.get(sector, 1):
            continue
        selected.append(scored)
        company_counts[company] += 1
        sector_counts[sector] += 1

    for scored in ordered:
        if len(selected) >= target:
            break
        if scored in selected:
            continue
        company = _company_key(scored.job.company)
        if company and company_counts[company] >= max_per_company:
            continue
        selected.append(scored)
        company_counts[company] += 1

    return selected


def search_sector(scored: ScoredJob) -> str:
    text = _text(scored)
    if any(term in text for term in ("venture", "investment", "private capital", "private equity", "growth equity")):
        return "Finance / Capital"
    if any(term in text for term in ("strategic finance", "fp&a", "corporate development", "corp dev", "capital markets")):
        return "Finance / Capital"
    if any(term in text for term in ("partnership", "business development", "go-to-market", "commercial strategy")):
        return "Strategy / Partnerships"
    if any(term in text for term in ("policy", "government affairs", "market intelligence", "research analyst")):
        return "Policy / Research"
    if any(term in text for term in ("space", "aerospace", "satellite", "defense", "autonomy", "drone", "dual-use")):
        return "Space / Defense"
    return "Other"


def _priority_key(scored: ScoredJob) -> tuple[int, int, int, str]:
    sector = search_sector(scored)
    finance_bonus = 12 if sector == "Finance / Capital" else 0
    strategy_bonus = 6 if sector == "Strategy / Partnerships" else 0
    label_bonus = 10 if Classification.APPLY_NOW in scored.labels else 5 if Classification.WARM_INTRO_FIRST in scored.labels else 0
    return (scored.total_score + finance_bonus + strategy_bonus + label_bonus, scored.total_score, label_bonus, scored.job.title)


def _text(scored: ScoredJob) -> str:
    job = scored.job
    return " ".join(
        [
            job.title,
            job.company,
            job.location,
            job.notes,
            job.fit_summary,
            job.requirements_summary,
            job.raw_text,
            " ".join(scored.rationale),
        ]
    ).lower()


def _company_key(company: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "", company.lower())
    known = {
        "shieldai": "shieldai",
        "shield": "shieldai",
        "cesiumastro": "cesiumastro",
        "careers": "",
    }
    return known.get(normalized, normalized)
