from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv


DEFAULT_SHEET_ID = "1hUdPtfQY4Fo6iZ9pDYWyWrJT2lCht2LeR7QPI5KsrsA"


@dataclass(frozen=True)
class UserProfile:
    first_name: str
    full_name: str
    site_title: str
    site_subtitle: str
    initials: str
    profile_summary: str
    dashboard_url: str
    application_context: str

    @property
    def possessive_first_name(self) -> str:
        return _possessive(self.first_name)

    @classmethod
    def from_env(cls) -> "UserProfile":
        first_name = os.getenv("JOB_SEARCH_USER_FIRST_NAME", "Simone").strip() or "Simone"
        full_name = os.getenv("JOB_SEARCH_USER_FULL_NAME", "Simone Montandon").strip() or first_name
        default_site_title = f"{_possessive(first_name)} Career Center"
        return cls(
            first_name=first_name,
            full_name=full_name,
            site_title=os.getenv("JOB_SEARCH_SITE_TITLE", default_site_title).strip() or default_site_title,
            site_subtitle=os.getenv("JOB_SEARCH_SITE_SUBTITLE", "Career Center").strip() or "Career Center",
            initials=os.getenv("JOB_SEARCH_USER_INITIALS", _initials(full_name)).strip() or _initials(full_name),
            profile_summary=os.getenv(
                "JOB_SEARCH_PROFILE_SUMMARY",
                "Strategy, capital, policy, and dual-use technology",
            ).strip()
            or "Strategy, capital, policy, and dual-use technology",
            dashboard_url=os.getenv("JOB_SEARCH_DASHBOARD_URL", "https://gusim1.github.io/job-search-agent/").strip()
            or "https://gusim1.github.io/job-search-agent/",
            application_context=os.getenv(
                "JOB_SEARCH_APPLICATION_CONTEXT",
                "Use the uploaded resume, cover-letter examples, and style guide as the source of truth. "
                "Do not invent personal facts.",
            ).strip(),
        )


@dataclass(frozen=True)
class Settings:
    dry_run: bool
    sheet_id: str
    gmail_to: str
    gmail_search_queries: list[str]
    enable_public_source_search: bool
    public_source_urls: list[str]
    feedback_export_path: Path | None
    output_dir: Path
    credentials_json: dict | None
    oauth_client_secret_json: dict | None
    oauth_token_json: dict | None
    user_profile: UserProfile = field(default_factory=UserProfile.from_env)
    linkedin_data_dirs: list[Path] = field(default_factory=list)

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv()
        query = os.getenv("GMAIL_SEARCH_QUERY", 'label:"Job Search Agent" newer_than:14d')
        extra_queries = [
            '(from:jobs-noreply@linkedin.com OR from:jobalerts-noreply@linkedin.com) '
            '("investment" OR "venture capital" OR "private capital" OR "strategic finance" OR '
            '"corporate development" OR "capital markets" OR "FP&A" OR "market intelligence") newer_than:14d',
            '(from:jobs-noreply@linkedin.com OR from:jobalerts-noreply@linkedin.com) '
            '("strategic partnerships" OR "business development" OR "strategy" OR "strategic partner") newer_than:14d',
            "from:jobalerts-noreply@linkedin.com newer_than:14d",
            "from:(linkedin.com) (job OR jobs OR alert OR hiring) newer_than:14d",
            "from:(handshake) (job OR jobs OR alert OR recommended) newer_than:14d",
        ]
        queries = [query, *extra_queries]
        return cls(
            dry_run=os.getenv("DRY_RUN", "true").strip().lower() != "false",
            sheet_id=os.getenv("GOOGLE_SHEET_ID", DEFAULT_SHEET_ID),
            gmail_to=os.getenv("GMAIL_TO", "simone@montandon.it"),
            gmail_search_queries=list(dict.fromkeys(queries)),
            enable_public_source_search=os.getenv("ENABLE_PUBLIC_SOURCE_SEARCH", "false").strip().lower() == "true",
            public_source_urls=_csv_env("PUBLIC_SOURCE_URLS"),
            feedback_export_path=_path_env("FEEDBACK_EXPORT_PATH"),
            linkedin_data_dirs=[Path(item).expanduser() for item in _csv_env("LINKEDIN_DATA_DIRS")],
            output_dir=Path(os.getenv("OUTPUT_DIR", "artifacts")),
            credentials_json=_json_env("GOOGLE_APPLICATION_CREDENTIALS_JSON")
            or _json_file_env("GOOGLE_APPLICATION_CREDENTIALS_JSON_FILE")
            or _json_file_env("GOOGLE_APPLICATION_CREDENTIALS"),
            oauth_client_secret_json=_json_env("GOOGLE_OAUTH_CLIENT_SECRET_JSON")
            or _json_file_env("GOOGLE_OAUTH_CLIENT_SECRET_JSON_FILE"),
            oauth_token_json=_json_env("GOOGLE_OAUTH_TOKEN_JSON")
            or _json_file_env("GOOGLE_OAUTH_TOKEN_JSON_FILE"),
            user_profile=UserProfile.from_env(),
        )


def _json_env(name: str) -> dict | None:
    value = os.getenv(name)
    if not value:
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{name} must contain raw JSON, not a file path or token string.") from exc


def _json_file_env(name: str) -> dict | None:
    value = os.getenv(name)
    if not value:
        return None
    path = Path(value).expanduser()
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"{name} must point to a readable JSON file.") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"{name} must point to a valid JSON file.") from exc


def _csv_env(name: str) -> list[str]:
    value = os.getenv(name, "")
    return [item.strip() for item in value.split(",") if item.strip()]


def _path_env(name: str) -> Path | None:
    value = os.getenv(name)
    return Path(value) if value else None


def _initials(full_name: str) -> str:
    parts = [part for part in full_name.replace("-", " ").split() if part]
    if not parts:
        return "U"
    return "".join(part[0].upper() for part in parts[:2])


def _possessive(name: str) -> str:
    cleaned = name.strip()
    if not cleaned:
        return ""
    return f"{cleaned}'" if cleaned.lower().endswith("s") else f"{cleaned}'s"
