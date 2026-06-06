from __future__ import annotations

import logging

from job_search_agent.calibration import load_feedback_export
from job_search_agent.balancing import balance_scored_jobs
from job_search_agent.config import Settings
from job_search_agent.dedupe import unique_jobs
from job_search_agent.public_sources import discover_public_jobs
from job_search_agent.scoring import score_jobs, should_skip_job
from job_search_agent.sheets_client import SheetsClient


LOGGER = logging.getLogger(__name__)


def run() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    settings = Settings.from_env()
    if not settings.credentials_json:
        raise ValueError("Public source sync requires GOOGLE_APPLICATION_CREDENTIALS_JSON for Sheets reads and writes.")

    sheets = SheetsClient.from_service_account_json(settings.credentials_json, settings.sheet_id)
    source_urls = _source_urls(settings, sheets)
    if not source_urls:
        LOGGER.info("No public source URLs configured. Add ATS or careers URLs to PUBLIC_SOURCE_URLS or the Source List tab.")
        return

    LOGGER.info("Discovering free public jobs from %d source URLs", len(source_urls))
    existing_keys = sheets.existing_dedupe_keys()
    calibration = load_feedback_export(settings.feedback_export_path).merge(sheets.calibration_profile())
    jobs = discover_public_jobs(source_urls)
    jobs = [job for job in jobs if not should_skip_job(job)]
    unique = unique_jobs(jobs, existing_keys=existing_keys)
    scored = score_jobs(unique, calibration=calibration)
    scored = balance_scored_jobs(scored)

    if settings.dry_run:
        LOGGER.info("Dry run: would append %d public-source jobs to the tracker", len(scored))
        return

    sheets.append_scored_jobs(scored)
    LOGGER.info("Appended %d public-source jobs to the tracker", len(scored))


def _source_urls(settings: Settings, sheets: SheetsClient) -> list[str]:
    urls = [*settings.public_source_urls, *sheets.public_source_urls()]
    return list(dict.fromkeys(urls))


if __name__ == "__main__":
    run()
