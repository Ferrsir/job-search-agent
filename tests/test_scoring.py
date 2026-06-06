from datetime import date, timedelta

from job_search_agent.calibration import CalibrationProfile, job_feedback_id
from job_search_agent.models import Classification, JobRecord
from job_search_agent.scoring import score_job


def test_score_keeps_strategic_manager_role_as_warm_but_not_top_student_fit():
    job = JobRecord(
        title="Strategic Partnerships Manager",
        company="Orbit Works",
        location="Austin, TX",
        url="https://example.com/job",
        source="LinkedIn",
        source_email_id="1",
        raw_text="space dual-use venture-backed network access senior role",
    )

    scored = score_job(job)

    assert scored.total_score >= 70
    assert Classification.WARM_INTRO_FIRST in scored.labels
    assert Classification.AUSTIN_MATCH in scored.labels
    assert scored.destination_tab == "Active Roles"


def test_auto_reject_clearance_engineering_role():
    job = JobRecord(
        title="Software Engineer",
        company="Prime Defense",
        location="Washington, DC",
        url="https://example.com/job",
        source="LinkedIn",
        source_email_id="1",
        raw_text="active security clearance required",
    )

    scored = score_job(job)

    assert Classification.AUTO_REJECT in scored.labels
    assert scored.destination_tab == "Rejected Notable"


def test_auto_rejects_roles_requiring_engineering_degree():
    job = JobRecord(
        title="Product Manager",
        company="Orbital Systems",
        location="Austin, TX",
        url="https://example.com/job",
        source="Public source",
        source_email_id="1",
        requirements_summary="Bachelor's degree in engineering or computer science required.",
        raw_text="space strategy market intelligence",
    )

    scored = score_job(job)

    assert Classification.AUTO_REJECT in scored.labels
    assert scored.destination_tab == "Rejected Notable"


def test_penalizes_too_technical_non_engineering_title():
    job = JobRecord(
        title="Product Manager",
        company="Autonomy Labs",
        location="Remote",
        url="https://example.com/job",
        source="Public source",
        source_email_id="1",
        raw_text="autonomy strategy role requiring Python, embedded systems, and machine learning depth",
    )

    scored = score_job(job)

    assert scored.score_breakdown["Technical mismatch"] < 0
    assert any("more technical" in note for note in scored.rationale)


def test_shortlist_feedback_promotes_borderline_job():
    job = JobRecord(
        title="Market Intelligence Associate",
        company="Frontier Capital",
        location="Remote",
        url="https://example.com/research",
        source="LinkedIn",
        source_email_id="1",
        raw_text="venture platform",
    )
    calibration = CalibrationProfile(feedback_by_job_id={job_feedback_id(job): "shortlist"})

    scored = score_job(job, calibration=calibration)

    assert scored.score_breakdown["Feedback calibration"] == 10
    assert Classification.APPLY_NOW in scored.labels
    assert "Feedback signal: shortlist" in scored.rationale


def test_wrong_direction_feedback_moves_job_to_rejected_notable():
    job = JobRecord(
        title="Business Development Manager",
        company="QuotaCo",
        location="Austin, TX",
        url="https://example.com/bd",
        source="LinkedIn",
        source_email_id="1",
        raw_text="strategic partnerships",
    )
    calibration = CalibrationProfile(feedback_by_job_id={job_feedback_id(job): "wrong"})

    scored = score_job(job, calibration=calibration)

    assert Classification.REJECTED_NOTABLE in scored.labels
    assert scored.destination_tab == "Rejected Notable"


def test_wrong_reason_calibration_penalizes_similar_future_jobs():
    job = JobRecord(
        title="Director of Business Development",
        company="FutureCo",
        location="New York, NY",
        url="https://example.com/future",
        source="Public",
        source_email_id="future",
        raw_text="strategic partnerships and market development",
    )
    calibration = CalibrationProfile(
        wrong_reason_counts={"too_senior": 1, "wrong_location": 1},
        avoid_terms=("new york, ny",),
    )

    scored = score_job(job, calibration=calibration)

    assert scored.score_breakdown["Feedback calibration"] < 0
    assert any("too senior" in note and "wrong location" in note for note in scored.rationale)


def test_old_job_is_marked_expired():
    job = JobRecord(
        title="Strategic Finance Associate",
        company="Frontier Capital",
        location="Remote",
        url="https://example.com/old",
        source="Sheet",
        source_email_id="old",
        date_found=date.today() - timedelta(days=46),
        raw_text="Strategic finance and investment research.",
    )

    scored = score_job(job)

    assert Classification.EXPIRED in scored.labels
    assert scored.destination_tab == "Expired"


def test_preference_terms_adjust_score():
    job = JobRecord(
        title="Policy Lead",
        company="Quantum Forge",
        location="Dallas, TX",
        url="https://example.com/policy",
        source="LinkedIn",
        source_email_id="1",
        raw_text="quantum public policy",
    )
    calibration = CalibrationProfile(preferred_terms=("quantum", "public policy"), avoid_terms=("pure sales",))

    scored = score_job(job, calibration=calibration)

    assert scored.score_breakdown["Feedback calibration"] == 4
    assert any("Preference match" in note for note in scored.rationale)


def test_freshman_sophomore_finance_internship_scores_as_strong_fit():
    job = JobRecord(
        title="Finance Intern",
        company="Texas Capital",
        location="Dallas, TX",
        url="https://example.com/finance-intern",
        source="LinkedIn",
        source_email_id="freshman-finance",
        raw_text=(
            "Summer finance internship for freshman and sophomore undergraduate students. "
            "Corporate finance, financial analysis, valuation, and company research. $20-$25/hour."
        ),
    )

    scored = score_job(job)

    assert scored.score_breakdown["Role fit"] >= 20
    assert scored.score_breakdown["Student fit"] == 18
    assert scored.score_breakdown["Seniority fit"] > 0
    assert Classification.APPLY_NOW in scored.labels
    assert scored.destination_tab == "Active Roles"


def test_graduate_or_rising_senior_role_is_penalized_below_student_friendly_internship():
    student_job = JobRecord(
        title="Investment Analyst Intern",
        company="Search Fund Partners",
        location="Plano, TX",
        url="https://example.com/student",
        source="Handshake",
        source_email_id="student",
        raw_text="Freshman or sophomore undergraduate students welcome. Investment research and valuation internship.",
    )
    advanced_job = JobRecord(
        title="Investment Banking Summer Analyst",
        company="Prestige Bank",
        location="Dallas, TX",
        url="https://example.com/advanced",
        source="LinkedIn",
        source_email_id="advanced",
        raw_text="For rising senior or graduate student candidates. MBA or completed bachelor's degree preferred.",
    )

    student_scored = score_job(student_job)
    advanced_scored = score_job(advanced_job)

    assert advanced_scored.score_breakdown["Student fit"] < 0
    assert advanced_scored.score_breakdown["Seniority fit"] < 0
    assert student_scored.total_score > advanced_scored.total_score
    assert any("senior, graduate" in note for note in advanced_scored.rationale)
