from job_search_agent.analytics import analyze_job, build_analytics_dashboard
from job_search_agent.models import Classification, JobRecord, NetworkContact, ScoredJob


def test_analyze_job_extracts_dashboard_fields():
    scored = ScoredJob(
        job=JobRecord(
            title="Strategic Partnerships Manager",
            company="Orbit Works",
            location="Austin, TX / Hybrid",
            url="https://example.com/job",
            source="Sheet",
            source_email_id="1",
            requirements_summary="5+ years of partnerships, government, and aerospace market strategy experience. Salary $120k-$150k.",
            raw_text="Bachelor's degree preferred. No active security clearance required.",
        ),
        total_score=84,
        labels=[Classification.APPLY_NOW, Classification.AUSTIN_MATCH],
        score_breakdown={},
        rationale=["Strong strategic partnerships fit."],
        destination_tab="Active Roles",
    )

    analysis = analyze_job(scored)

    assert analysis.geography == "Austin"
    assert analysis.role_family == "Partnerships / BD"
    assert "Aerospace / space" in analysis.qualifications
    assert "Government" in analysis.qualifications
    assert analysis.salary_min == 120000
    assert analysis.salary_max == 150000
    assert analysis.work_mode == "Hybrid"
    assert analysis.degree_requirement == "Bachelor's mentioned"
    assert analysis.clearance_requirement == "No clearance required"


def test_build_analytics_dashboard_summarizes_market_and_contacts():
    base = JobRecord(
        title="Contracts Manager",
        company="CesiumAstro",
        location="Austin, TX",
        url="https://example.com/cesium",
        source="Sheet",
        source_email_id="1",
        requirements_summary="Contracts, vendors, aerospace customers, and government procurement experience. $100k-$130k.",
        network_contacts=[
            NetworkContact(name="Ava Chen", company="CesiumAstro", position="Director", reason="company match")
        ],
    )
    scored = ScoredJob(
        job=base,
        total_score=78,
        labels=[Classification.APPLY_NOW, Classification.AUSTIN_MATCH],
        score_breakdown={},
        rationale=["Strong fit."],
        destination_tab="Active Roles",
    )

    dashboard = build_analytics_dashboard([scored])

    assert dashboard.geography_role_demand["Austin"][0].label == "Contracts / Legal"
    assert dashboard.top_companies_by_geography["Austin"][0].label == "CesiumAstro"
    assert dashboard.strongest_contacts[0].label == "Ava Chen / CesiumAstro"
    assert dashboard.salary_by_role_family[0].count == 115000
    assert dashboard.score_bands[0].label == "70-79 strong"
    assert dashboard.seniority_mix[0].label == "Mid-level"
    assert dashboard.work_mode_mix[0].label == "Unspecified"
    assert dashboard.degree_mix[0].label == "No explicit degree found"
    assert dashboard.clearance_mix[0].label == "No clearance signal"
    signal = next(iter(dashboard.job_signals.values()))
    assert signal.company == "CesiumAstro"
    assert signal.role_family == "Contracts / Legal"
    assert "Contracts" in signal.qualifications


def test_dashboard_excludes_polluted_and_technical_rows_from_analytics():
    clean = ScoredJob(
        job=JobRecord(
            title="Director of Business Development",
            company="shieldai",
            location="Dallas, TX",
            url="https://example.com/role",
            source="Sheet",
            source_email_id="1",
            requirements_summary="Business development and defense market strategy.",
        ),
        total_score=68,
        labels=[Classification.WARM_INTRO_FIRST, Classification.DALLAS_MATCH],
        score_breakdown={},
        rationale=["Useful target role."],
        destination_tab="Active Roles",
    )
    polluted = ScoredJob(
        job=JobRecord(
            title="Careers",
            company="Careers",
            location="careers|test technician redondo beach|https://impulsespace.example/posting",
            url="https://example.com/bad",
            source="Sheet",
            source_email_id="2",
            requirements_summary="Test technician and avionics execution.",
        ),
        total_score=45,
        labels=[Classification.MONITOR],
        score_breakdown={},
        rationale=["Bad imported row."],
        destination_tab="Active Roles",
    )

    dashboard = build_analytics_dashboard([clean, polluted])

    assert list(dashboard.geography_role_demand) == ["Dallas-Fort Worth"]
    assert dashboard.top_companies_by_geography["Dallas-Fort Worth"][0].label == "Shield AI"
    assert dashboard.role_family_mix[0].label == "Partnerships / BD"
    assert dashboard.cleanup_count == 1
