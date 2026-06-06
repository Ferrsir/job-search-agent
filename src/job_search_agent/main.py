from __future__ import annotations

import logging
from datetime import date

from job_search_agent.calibration import CalibrationProfile, load_feedback_export
from job_search_agent.balancing import balance_scored_jobs
from job_search_agent.config import Settings
from job_search_agent.dedupe import unique_jobs
from job_search_agent.digest import render_preferences_page, render_weekly_digest, save_digest
from job_search_agent.enrichment import enrich_alert_jobs
from job_search_agent.linkedin_network import LinkedInNetwork, enrich_jobs_with_network
from job_search_agent.gmail_client import EmailMessage, GmailClient
from job_search_agent.models import JobRecord
from job_search_agent.parsers.handshake import parse_handshake_email
from job_search_agent.parsers.linkedin import parse_linkedin_email
from job_search_agent.public_sources import discover_public_jobs
from job_search_agent.scoring import score_jobs
from job_search_agent.sheets_client import SheetsClient


LOGGER = logging.getLogger(__name__)


def run() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    settings = Settings.from_env()
    LOGGER.info("Starting job-search agent. dry_run=%s", settings.dry_run)

    gmail = GmailClient.from_json(
        oauth_token_json=settings.oauth_token_json,
        service_account_json=settings.credentials_json,
    )
    sheets = None
    existing_keys: set[str] = set()
    if settings.credentials_json:
        sheets = SheetsClient.from_service_account_json(settings.credentials_json, settings.sheet_id)
        existing_keys = sheets.existing_dedupe_keys()
    elif not settings.dry_run:
        raise ValueError("Live mode requires GOOGLE_APPLICATION_CREDENTIALS_JSON for Sheets writes.")
    calibration = _load_calibration(settings, sheets)

    messages = _load_messages(gmail, settings.gmail_search_queries)
    jobs = _parse_messages(messages)
    jobs = enrich_alert_jobs(jobs)
    if settings.enable_public_source_search:
        source_urls = list(settings.public_source_urls)
        if sheets:
            source_urls.extend(sheets.public_source_urls())
        source_urls = list(dict.fromkeys(source_urls))
        LOGGER.info("Discovering public jobs from %d source URLs", len(source_urls))
        jobs.extend(discover_public_jobs(source_urls))
    unique = unique_jobs(jobs, existing_keys=existing_keys)
    scored = score_jobs(unique, calibration=calibration)
    scored = balance_scored_jobs(scored)
    if settings.linkedin_data_dirs:
        network = LinkedInNetwork.from_dirs(settings.linkedin_data_dirs)
        scored = enrich_jobs_with_network(scored, network)
        LOGGER.info(
            "Added LinkedIn network context from %d directories and %d connections",
            len(settings.linkedin_data_dirs),
            len(network.connections),
        )

    html = render_weekly_digest(scored, user_profile=settings.user_profile)
    digest_path = save_digest(html, settings.output_dir, f"weekly_digest_{date.today().isoformat()}.html")
    preferences_path = save_digest(
        render_preferences_page(user_profile=settings.user_profile),
        settings.output_dir,
        "preferences.html",
    )
    LOGGER.info("Saved digest to %s", digest_path)
    LOGGER.info("Saved preferences questionnaire to %s", preferences_path)

    if settings.dry_run:
        LOGGER.info("Dry run: would append %d jobs and create Gmail draft to %s", len(scored), settings.gmail_to)
        return

    if sheets:
        sheets.append_scored_jobs(scored)
    draft_id = gmail.create_draft(settings.gmail_to, "Weekly Job Search Brief", html)
    LOGGER.info("Created Gmail draft %s", draft_id)


def _load_messages(gmail: GmailClient, queries: list[str]) -> list[EmailMessage]:
    ids: list[str] = []
    seen: set[str] = set()
    for query in queries:
        LOGGER.info("Searching Gmail: %s", query)
        for message_id in gmail.search_messages(query):
            if message_id not in seen:
                seen.add(message_id)
                ids.append(message_id)
    return [gmail.get_message(message_id) for message_id in ids]


def _parse_messages(messages: list[EmailMessage]) -> list[JobRecord]:
    jobs: list[JobRecord] = []
    for message in messages:
        sender_subject = f"{message.sender} {message.subject}".lower()
        if "linkedin" in sender_subject:
            jobs.extend(
                parse_linkedin_email(
                    html=message.html,
                    text=message.text,
                    message_id=message.message_id,
                    received_date=message.received_date,
                    alert_name=message.subject,
                )
            )
        elif "handshake" in sender_subject:
            jobs.extend(
                parse_handshake_email(
                    html=message.html,
                    text=message.text,
                    message_id=message.message_id,
                    received_date=message.received_date,
                    alert_name=message.subject,
                )
            )
        else:
            LOGGER.debug("Skipping unsupported sender: %s", message.sender)
    LOGGER.info("Parsed %d job records from %d messages", len(jobs), len(messages))
    return jobs


def _load_calibration(settings: Settings, sheets: SheetsClient | None) -> CalibrationProfile:
    calibration = load_feedback_export(settings.feedback_export_path)
    if sheets:
        calibration = calibration.merge(sheets.calibration_profile())
    LOGGER.info(
        "Loaded calibration: %d feedback examples, %d preferred terms, %d avoid terms",
        len(calibration.feedback_by_job_id),
        len(calibration.preferred_terms),
        len(calibration.avoid_terms),
    )
    return calibration


if __name__ == "__main__":
    run()
