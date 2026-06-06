from datetime import date

from job_search_agent.parsers.linkedin import parse_linkedin_email


def test_parse_linkedin_html_job_link():
    html = """
    <div>
      <a href="https://www.linkedin.com/jobs/view/123?trk=email">Strategic Partnerships Manager</a>
      <p>Orbit Works · Austin, TX · Space</p>
    </div>
    """

    jobs = parse_linkedin_email(
        html=html,
        message_id="msg-1",
        received_date=date(2026, 6, 1),
        alert_name="LinkedIn Job Alert",
    )

    assert len(jobs) == 1
    assert jobs[0].title == "Strategic Partnerships Manager"
    assert jobs[0].company == "Orbit Works"
    assert jobs[0].location == "Austin, TX"
    assert jobs[0].source == "LinkedIn"


def test_parse_linkedin_partial_record_when_only_url_is_available():
    text = "A role you might like https://www.linkedin.com/jobs/view/999"

    jobs = parse_linkedin_email(text=text, message_id="msg-2")

    assert len(jobs) == 1
    assert jobs[0].title == "Needs manual review"
    assert "Needs manual review" in jobs[0].notes
