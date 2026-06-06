from job_search_agent.config import Settings
from job_search_agent.public_sync import _source_urls


class FakeSheets:
    def public_source_urls(self):
        return [
            "https://jobs.lever.co/frontier",
            "https://jobs.ashbyhq.com/autonomy",
        ]


def test_source_urls_merges_env_and_sheet_without_duplicates(tmp_path):
    settings = Settings(
        dry_run=True,
        sheet_id="sheet",
        gmail_to="simone@example.com",
        gmail_search_queries=[],
        enable_public_source_search=True,
        public_source_urls=[
            "https://boards.greenhouse.io/orbitworks",
            "https://jobs.lever.co/frontier",
        ],
        feedback_export_path=None,
        output_dir=tmp_path,
        credentials_json=None,
        oauth_client_secret_json=None,
        oauth_token_json=None,
    )

    assert _source_urls(settings, FakeSheets()) == [
        "https://boards.greenhouse.io/orbitworks",
        "https://jobs.lever.co/frontier",
        "https://jobs.ashbyhq.com/autonomy",
    ]
