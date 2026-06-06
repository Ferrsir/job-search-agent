from __future__ import annotations

import logging
from datetime import date

from job_search_agent.config import Settings
from job_search_agent.digest import render_preferences_page, render_weekly_digest, save_digest
from job_search_agent.linkedin_network import LinkedInNetwork, enrich_jobs_with_network
from job_search_agent.sheets_client import SheetsClient


LOGGER = logging.getLogger(__name__)


def run() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    settings = Settings.from_env()
    if not settings.credentials_json:
        raise ValueError("GOOGLE_APPLICATION_CREDENTIALS_JSON is required to render the Sheet-backed site.")
    sheets = SheetsClient.from_service_account_json(settings.credentials_json, settings.sheet_id)
    scored_jobs = sheets.backend_scored_jobs()
    if settings.linkedin_data_dirs:
        network = LinkedInNetwork.from_dirs(settings.linkedin_data_dirs)
        scored_jobs = enrich_jobs_with_network(scored_jobs, network)
        LOGGER.info(
            "Added LinkedIn network context from %d directories and %d connections",
            len(settings.linkedin_data_dirs),
            len(network.connections),
        )
    html = render_weekly_digest(scored_jobs, user_profile=settings.user_profile)
    path = save_digest(html, settings.output_dir, f"sheet_dashboard_{date.today().isoformat()}.html")
    preferences_path = save_digest(
        render_preferences_page(user_profile=settings.user_profile),
        settings.output_dir,
        "preferences.html",
    )
    LOGGER.info("Rendered %d Sheet-backed jobs to %s", len(scored_jobs), path)
    LOGGER.info("Rendered preferences questionnaire to %s", preferences_path)


if __name__ == "__main__":
    run()
