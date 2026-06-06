from __future__ import annotations

import json

from job_search_agent.config import Settings, UserProfile


def test_settings_loads_google_credentials_from_file_path(monkeypatch, tmp_path) -> None:
    credentials_path = tmp_path / "service-account.json"
    credentials_path.write_text(json.dumps({"type": "service_account", "client_email": "bot@example.com"}), encoding="utf-8")
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS_JSON", raising=False)
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", str(credentials_path))

    settings = Settings.from_env()

    assert settings.credentials_json == {"type": "service_account", "client_email": "bot@example.com"}


def test_user_profile_possessive_handles_names_ending_in_s() -> None:
    ferris = UserProfile(
        first_name="Ferris",
        full_name="Ferris LaVigne",
        site_title="Ferris' Career Center",
        site_subtitle="Career Center",
        initials="FL",
        profile_summary="Finance internships.",
        dashboard_url="https://example.com",
        application_context="Use Ferris' materials.",
    )
    simone = UserProfile(
        first_name="Simone",
        full_name="Simone Montandon",
        site_title="Simone's Career Center",
        site_subtitle="Career Center",
        initials="SM",
        profile_summary="Strategy roles.",
        dashboard_url="https://example.com",
        application_context="Use Simone's materials.",
    )

    assert ferris.possessive_first_name == "Ferris'"
    assert simone.possessive_first_name == "Simone's"
