from job_search_agent.balancing import balance_scored_jobs, search_sector
from job_search_agent.models import Classification, JobRecord, ScoredJob


def test_search_sector_identifies_finance_roles():
    scored = _scored(
        title="Strategic Finance Associate",
        company="Frontier Capital",
        evidence="FP&A, corporate development, private capital, and investor relations.",
        score=72,
    )

    assert search_sector(scored) == "Finance / Capital"


def test_balance_caps_single_space_company_and_keeps_finance():
    jobs = [
        _scored(
            title=f"Business Development Manager {index}",
            company="CesiumAstro",
            evidence="space aerospace defense business development",
            score=80 - index,
        )
        for index in range(12)
    ]
    jobs.extend(
        [
            _scored("Investment Research Associate", "Frontier Capital", "venture investment research private capital", 69),
            _scored("Strategic Finance Manager", "Anduril", "strategic finance FP&A capital markets", 68),
            _scored("Corporate Development Associate", "Google", "corporate development investment partnerships", 67),
        ]
    )

    balanced = balance_scored_jobs(jobs, max_results=10, max_per_company=4)

    assert sum(1 for scored in balanced if scored.job.company == "CesiumAstro") <= 4
    assert sum(1 for scored in balanced if search_sector(scored) == "Finance / Capital") == 3


def _scored(title: str, company: str, evidence: str, score: int) -> ScoredJob:
    return ScoredJob(
        job=JobRecord(
            title=title,
            company=company,
            location="Remote",
            url=f"https://example.com/{company}/{title}".replace(" ", "-"),
            source="Test",
            source_email_id=title,
            notes=evidence,
            fit_summary=evidence,
            raw_text=evidence,
        ),
        total_score=score,
        labels=[Classification.APPLY_NOW if score >= 75 else Classification.WARM_INTRO_FIRST],
        score_breakdown={},
        rationale=[evidence],
        destination_tab="Active Roles",
    )
