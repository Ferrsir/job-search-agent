from __future__ import annotations

import logging
from datetime import date

from job_search_agent.config import Settings
from job_search_agent.digest import render_weekly_email, save_digest
from job_search_agent.gmail_client import GmailClient
from job_search_agent.linkedin_network import LinkedInNetwork, enrich_jobs_with_network
from job_search_agent.sheets_client import SheetsClient


LOGGER = logging.getLogger(__name__)


def run() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    settings = Settings.from_env()
    LOGGER.info("Starting Sheet-backed weekly brief. dry_run=%s", settings.dry_run)
    if not settings.credentials_json:
        raise ValueError("GOOGLE_APPLICATION_CREDENTIALS_JSON is required to read the Sheet backend.")

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
    html = render_weekly_email(scored_jobs, user_profile=settings.user_profile)
    digest_path = save_digest(html, settings.output_dir, f"weekly_brief_{date.today().isoformat()}.html")
    LOGGER.info("Saved Sheet-backed weekly brief to %s", digest_path)

    if settings.dry_run:
        LOGGER.info("Dry run: would send Sheet-backed weekly brief to %s", settings.gmail_to)
        return

    gmail = GmailClient.from_json(
        oauth_token_json=settings.oauth_token_json,
        service_account_json=settings.credentials_json,
    )
    message_id = gmail.send_html(settings.gmail_to, "Weekly Job Search Brief", html)
    LOGGER.info("Sent Gmail message %s to %s", message_id, settings.gmail_to)
