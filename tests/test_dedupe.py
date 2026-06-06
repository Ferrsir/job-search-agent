from job_search_agent.dedupe import dedupe_key, unique_jobs
from job_search_agent.models import JobRecord


def test_dedupe_ignores_case_spacing_and_tracking_params():
    first = JobRecord(
        title="Strategic Partnerships Manager",
        company="Orbit Works",
        url="https://example.com/jobs/1?utm_source=email",
        source="LinkedIn",
        source_email_id="1",
    )
    second = JobRecord(
        title="strategic   partnerships manager",
        company="ORBIT WORKS",
        url="https://example.com/jobs/1",
        source="LinkedIn",
        source_email_id="2",
    )

    assert dedupe_key(first) == dedupe_key(second)
    assert len(unique_jobs([first, second])) == 1
