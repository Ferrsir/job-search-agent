from job_search_agent.enrichment import enrich_alert_jobs
from job_search_agent.models import JobRecord


class FakeResponse:
    def __init__(self, text=""):
        self.text = text

    def raise_for_status(self):
        return None


def test_enrich_alert_job_from_public_schema_posting():
    job = JobRecord(
        title="Strategic Growth Manager",
        company="Frontier Labs",
        location="Austin, TX",
        url="https://www.linkedin.com/jobs/view/123",
        source="LinkedIn",
        source_email_id="msg-1",
        raw_text="Strategic Growth Manager Frontier Labs Austin",
    )

    def fake_searcher(job, max_results):
        return ["https://frontier.example/jobs/strategic-growth-manager"]

    def fake_get(url, timeout, headers):
        return FakeResponse(
            text="""
            <html>
              <head>
                <title>Frontier Labs Careers</title>
                <script type="application/ld+json">
                {
                  "@type": "JobPosting",
                  "title": "Strategic Growth Manager",
                  "url": "https://frontier.example/jobs/strategic-growth-manager",
                  "hiringOrganization": {"name": "Frontier Labs"},
                  "jobLocation": {"address": {"addressLocality": "Austin", "addressRegion": "TX"}},
                  "description": "Requirements: 5+ years of partnerships or strategy experience. Ability to brief executives. Benefits include healthcare."
                }
                </script>
              </head>
            </html>
            """
        )

    enriched = enrich_alert_jobs([job], fetcher=fake_get, searcher=fake_searcher)

    assert enriched[0].source == "LinkedIn + public enrichment"
    assert enriched[0].url == "https://frontier.example/jobs/strategic-growth-manager"
    assert "5+ years of partnerships" in enriched[0].requirements_summary


def test_enrichment_ignores_private_alert_domains_and_falls_back():
    job = JobRecord(
        title="Policy Associate",
        company="Quantum Forge",
        location="Dallas, TX",
        url="https://joinhandshake.com/jobs/123",
        source="Handshake",
        source_email_id="msg-2",
        raw_text="Policy Associate Quantum Forge Dallas",
    )

    def fake_searcher(job, max_results):
        return ["https://www.linkedin.com/jobs/view/999", "https://joinhandshake.com/jobs/123"]

    enriched = enrich_alert_jobs([job], searcher=fake_searcher)

    assert enriched[0].source == "Handshake"
    assert "Requirements need manual review" in enriched[0].requirements_summary
