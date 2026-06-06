from job_search_agent.requirements import summarize_requirements


def test_summarize_requirements_extracts_compact_requirement_section():
    text = """
    About the role: Work with customers in defense markets.
    Requirements: 4+ years of experience in strategy or partnerships. Ability to brief senior stakeholders.
    Familiarity with aerospace or defense markets preferred. Benefits include healthcare and equity.
    """

    summary = summarize_requirements(text)

    assert "4+ years of experience" in summary
    assert "Ability to brief senior stakeholders" in summary
    assert "Benefits" not in summary
