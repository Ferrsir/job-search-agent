from __future__ import annotations

import logging

from job_search_agent.config import Settings
from job_search_agent.sheets_client import SheetsClient


LOGGER = logging.getLogger(__name__)


def run() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    settings = Settings.from_env()
    if not settings.credentials_json:
        raise ValueError("GOOGLE_APPLICATION_CREDENTIALS_JSON is required to backfill Sheet analysis columns.")
    sheets = SheetsClient.from_service_account_json(settings.credentials_json, settings.sheet_id)
    counts = sheets.backfill_analysis_columns()
    for tab, changed_cells in counts.items():
        LOGGER.info("Backfilled %d analysis cells in %s", changed_cells, tab)


if __name__ == "__main__":
    run()
