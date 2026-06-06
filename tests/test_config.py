from __future__ import annotations

import json

from job_search_agent.config import Settings


def test_settings_loads_google_credentials_from_file_path(monkeypatch, tmp_path) -> None:
    credentials_path = tmp_path / "service-account.json"
    credentials_path.write_text(json.dumps({"type": "service_account", "client_email": "bot@example.com"}), encoding="utf-8")
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS_JSON", raising=False)
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", str(credentials_path))

    settings = Settings.from_env()

    assert settings.credentials_json == {"type": "service_account", "client_email": "bot@example.com"}
