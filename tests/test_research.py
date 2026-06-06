from job_search_agent.config import Settings
from job_search_agent.research import ResearchCandidate, ResearchPayload, run_research


def test_research_records_failure_without_openai_key(monkeypatch, tmp_path):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    result = run_research(_settings(tmp_path))

    assert result.status == "failure"
    assert result.surfaced_jobs == 0
    assert "OPENAI_API_KEY" in result.stopped_reason


def test_research_success_criteria(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENAI_API_KEY", "test")

    def fake_research(model, timeout_seconds):
        return ResearchPayload(
            search_summary="Found enough roles.",
            stopped_reason="Met success criteria.",
            jobs=[
                ResearchCandidate(title="Strategic Partnerships Manager", company="Affirm", location="Remote US", url="https://example.com/affirm", evidence="strategic partnerships remote"),
                ResearchCandidate(title="Public Policy Lead", company="Quantum Forge", location="Dallas, TX", url="https://example.com/quantum", evidence="quantum public policy"),
                ResearchCandidate(title="Investment Research Associate", company="Frontier Capital", location="Remote", url="https://example.com/frontier", evidence="venture investment research"),
                ResearchCandidate(title="Strategy Associate", company="Orbit Works", location="Austin, TX", url="https://example.com/orbit", evidence="space strategy"),
                ResearchCandidate(title="Market Intelligence Analyst", company="Autonomy Labs", location="Remote", url="https://example.com/autonomy", evidence="autonomy market intelligence"),
            ],
        )

    monkeypatch.setattr("job_search_agent.research._research_with_openai", fake_research)

    result = run_research(_settings(tmp_path))

    assert result.status == "success"
    assert result.surfaced_jobs == 5
    assert result.great_fits >= 1


def _settings(tmp_path):
    return Settings(
        dry_run=True,
        sheet_id="sheet",
        gmail_to="simone@example.com",
        gmail_search_queries=[],
        enable_public_source_search=False,
        public_source_urls=[],
        feedback_export_path=None,
        output_dir=tmp_path,
        credentials_json=None,
        oauth_client_secret_json=None,
        oauth_token_json=None,
    )
