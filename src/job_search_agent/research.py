from __future__ import annotations

import json
import logging
import os
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, HttpUrl, ValidationError

from job_search_agent.calibration import load_feedback_export
from job_search_agent.balancing import balance_scored_jobs
from job_search_agent.config import Settings
from job_search_agent.dedupe import dedupe_key, unique_jobs
from job_search_agent.digest import render_preferences_page, render_weekly_digest, save_digest
from job_search_agent.models import Classification, JobRecord, ScoredJob
from job_search_agent.scoring import score_jobs
from job_search_agent.sheets_client import SheetsClient


LOGGER = logging.getLogger(__name__)


class ResearchCandidate(BaseModel):
    title: str
    company: str
    location: str = ""
    url: HttpUrl | str
    source: str = "GPT web research"
    evidence: str = ""


class ResearchPayload(BaseModel):
    jobs: list[ResearchCandidate] = Field(default_factory=list)
    search_summary: str = ""
    stopped_reason: str = ""


class ResearchResult(BaseModel):
    status: str
    generated_at: str
    searched_with: str
    surfaced_jobs: int
    great_fits: int
    search_summary: str
    stopped_reason: str
    jobs: list[dict[str, Any]]


def run() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    settings = Settings.from_env()
    result = run_research(settings)
    result_path = _save_research_result(result, settings.output_dir)
    LOGGER.info("Saved research result to %s", result_path)

    if result.status != "success":
        LOGGER.warning("Research did not meet success criteria: %s", result.stopped_reason)
        return

    scored_jobs = [_scored_from_payload(item) for item in result.jobs]
    html = render_weekly_digest(scored_jobs, user_profile=settings.user_profile)
    digest_path = save_digest(html, settings.output_dir, f"research_dashboard_{date.today().isoformat()}.html")
    preferences_path = save_digest(
        render_preferences_page(user_profile=settings.user_profile),
        settings.output_dir,
        "preferences.html",
    )
    LOGGER.info("Saved research dashboard to %s", digest_path)
    LOGGER.info("Saved preferences questionnaire to %s", preferences_path)

    if not settings.dry_run and settings.credentials_json:
        sheets = SheetsClient.from_service_account_json(settings.credentials_json, settings.sheet_id)
        existing = sheets.existing_dedupe_keys()
        new_jobs = [scored for scored in scored_jobs if dedupe_key(scored.job) not in existing]
        sheets.append_scored_jobs(new_jobs)


def run_research(settings: Settings) -> ResearchResult:
    model = os.getenv("OPENAI_RESEARCH_MODEL", "gpt-5")
    min_jobs = int(os.getenv("RESEARCH_MIN_JOBS", "5"))
    min_great_fits = int(os.getenv("RESEARCH_MIN_GREAT_FITS", "1"))
    timeout_seconds = float(os.getenv("RESEARCH_TIMEOUT_SECONDS", "900"))
    if not os.getenv("OPENAI_API_KEY"):
        return ResearchResult(
            status="failure",
            generated_at=datetime.now(timezone.utc).isoformat(),
            searched_with=model,
            surfaced_jobs=0,
            great_fits=0,
            search_summary="GPT web research was skipped because OPENAI_API_KEY is not configured.",
            stopped_reason="Missing OPENAI_API_KEY.",
            jobs=[],
        )
    payload = _research_with_openai(model=model, timeout_seconds=timeout_seconds)
    jobs = [
        JobRecord(
            title=candidate.title,
            company=candidate.company,
            location=candidate.location,
            url=str(candidate.url),
            source=candidate.source,
            source_email_id=f"gpt-web-research:{date.today().isoformat()}",
            source_alert_name="GPT-powered web research",
            date_found=date.today(),
            notes=candidate.evidence,
            fit_summary=candidate.evidence,
            raw_text=candidate.evidence,
        )
        for candidate in payload.jobs
    ]
    jobs = unique_jobs(jobs)
    calibration = load_feedback_export(settings.feedback_export_path)
    scored = balance_scored_jobs(score_jobs(jobs, calibration=calibration))
    great_fits = sum(1 for scored_job in scored if Classification.APPLY_NOW in scored_job.labels)
    status = "success" if len(scored) >= min_jobs and great_fits >= min_great_fits else "failure"
    stopped_reason = payload.stopped_reason
    if status == "failure" and not stopped_reason:
        stopped_reason = (
            f"Success criteria not met: surfaced {len(scored)} jobs and {great_fits} great fits; "
            f"required {min_jobs} jobs and {min_great_fits} great fit."
        )
    return ResearchResult(
        status=status,
        generated_at=datetime.now(timezone.utc).isoformat(),
        searched_with=model,
        surfaced_jobs=len(scored),
        great_fits=great_fits,
        search_summary=payload.search_summary,
        stopped_reason=stopped_reason,
        jobs=[_payload_from_scored(scored_job) for scored_job in scored],
    )


def _research_with_openai(*, model: str, timeout_seconds: float) -> ResearchPayload:
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError("Install dependencies with pip install -e '.[dev]' before running GPT research.") from exc

    prompt = """
Find current public job postings for a personalized job search.

Hard constraints:
- Do not scrape LinkedIn directly.
- Prefer public company career pages and public ATS pages such as Greenhouse, Lever, Ashby, Workday, and company websites.
- Stop once you have at least 5 plausible jobs and at least 1 great fit, or when the search appears exhausted.
- Build a balanced slate. Do not let space/defense companies dominate the list.
- Target mix: about 35% finance/capital markets/venture/private capital, 25% strategy or strategic partnerships, 25% defense/space/dual-use, and 15% policy/research/other.
- Include finance-adjacent searches such as strategic finance, corporate development, FP&A, investment research, venture capital platform, private capital, growth equity, capital formation, and investor relations.
- Prioritize Austin, Dallas-Fort Worth, Remote, Hybrid Austin, Hybrid Dallas, Texas-wide with travel.
- Role families: strategic partnerships, venture capital/investment research/platform, government affairs/public policy, research analyst, strategy/market intelligence, strategic business development.
- Sectors: space, venture/private capital, quantum, intelligence/OSINT, advanced manufacturing, autonomy/drones, defense AI/cyber/dual-use.
- Avoid pure sales, pure engineering, internships, fellowships, active security clearance required, U.S. citizens-only roles, and mandatory non-Texas relocation unless exceptional.

Return only JSON with this exact shape:
{
  "search_summary": "short summary",
  "stopped_reason": "why you stopped",
  "jobs": [
    {
      "title": "role title",
      "company": "company",
      "location": "location",
      "url": "canonical public posting URL",
      "source": "GPT web research",
      "evidence": "one sentence explaining why this is relevant"
    }
  ]
}
"""
    client = OpenAI(timeout=timeout_seconds)
    response = client.responses.create(
        model=model,
        reasoning={"effort": "low"},
        tools=[{"type": "web_search"}],
        tool_choice="auto",
        input=prompt,
    )
    text = response.output_text.strip()
    try:
        return ResearchPayload.model_validate_json(_extract_json(text))
    except ValidationError as exc:
        raise RuntimeError(f"GPT research returned invalid job JSON: {exc}") from exc


def _extract_json(text: str) -> str:
    if text.startswith("{"):
        return text
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise RuntimeError("GPT research response did not contain a JSON object.")
    return text[start : end + 1]


def _payload_from_scored(scored: ScoredJob) -> dict[str, Any]:
    return {
        "title": scored.job.title,
        "company": scored.job.company,
        "location": scored.job.location,
        "url": str(scored.job.url),
        "score": scored.total_score,
        "labels": [str(label) for label in scored.labels],
        "rationale": scored.rationale,
        "evidence": scored.job.notes,
    }


def _scored_from_payload(payload: dict[str, Any]) -> ScoredJob:
    job = JobRecord(
        title=payload["title"],
        company=payload["company"],
        location=payload.get("location", ""),
        url=payload.get("url", ""),
        source="GPT web research",
        source_email_id=f"gpt-web-research:{date.today().isoformat()}",
        source_alert_name="GPT-powered web research",
        notes=payload.get("evidence", ""),
        fit_summary=payload.get("evidence", ""),
        raw_text=payload.get("evidence", ""),
    )
    return score_jobs([job])[0]


def _save_research_result(result: ResearchResult, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"research_result_{date.today().isoformat()}.json"
    path.write_text(json.dumps(result.model_dump(), indent=2), encoding="utf-8")
    return path


if __name__ == "__main__":
    run()
