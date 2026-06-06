from pathlib import Path

from job_search_agent.calibration import calibration_from_sheet_rows, job_feedback_id, load_feedback_export
from job_search_agent.models import JobRecord


def test_load_feedback_export_builds_profile(tmp_path: Path):
    job = JobRecord(
        title="Strategic Partnerships Manager",
        company="Orbit Works",
        url="https://example.com/job",
        source="Preview",
        source_email_id="1",
    )
    path = tmp_path / "feedback.json"
    path.write_text(
        f"""{{
          "preferences": {{
            "roles": "Strategic partnerships\\nMarket intelligence",
            "avoid": "Pure sales\\nInternships"
          }},
          "feedback": {{
            "{job_feedback_id(job)}": "shortlist"
          }},
          "wrongReasons": {{
            "{job_feedback_id(job)}": ["wrong_location", "wrong_job_type"]
          }},
          "directionReasons": {{
            "{job_feedback_id(job)}": ["strong_job_type", "strong_qualifications"]
          }},
          "jobs": {{
            "{job_feedback_id(job)}": {{
              "title": "Strategic Partnerships Manager",
              "location": "New York, NY",
              "requirements": "Partnerships and market intelligence experience"
            }}
          }}
        }}""",
        encoding="utf-8",
    )

    profile = load_feedback_export(path)

    assert profile.feedback_by_job_id[job_feedback_id(job)] == "shortlist"
    assert profile.wrong_reasons_by_job_id[job_feedback_id(job)] == ("wrong_location", "wrong_job_type")
    assert profile.direction_reasons_by_job_id[job_feedback_id(job)] == ("strong_job_type", "strong_qualifications")
    assert profile.wrong_reason_counts["wrong_location"] == 1
    assert "new york, ny" in profile.avoid_terms
    assert "strategic partnerships" in profile.preferred_terms
    assert "strategic partnerships manager" in profile.preferred_terms
    assert "partnerships and market intelligence experience" in profile.preferred_terms
    assert "pure sales" in profile.avoid_terms


def test_calibration_from_sheet_rows_accepts_flexible_headers_and_wrong_reasons():
    rows = [
        ["Company", "Role", "URL", "Feedback", "Wrong Reasons", "Direction Reasons", "Location", "Main Requirements"],
        ["Orbit Works", "Strategic Partnerships Manager", "https://example.com/job", "Right Job"],
        [
            "Frontier",
            "Strategic Partnerships Associate",
            "https://example.com/frontier",
            "Right direction",
            "",
            "Strong Job Type; Strong Qualifications; Strong Seniority Match",
            "Austin, TX",
            "Partnerships and market intelligence experience",
        ],
        ["QuotaCo", "Sales Manager", "https://example.com/sales", "Wrong direction", "Wrong Job Type; Wrong Location", "", "Miami, FL"],
    ]

    profile = calibration_from_sheet_rows(rows)

    assert len(profile.feedback_by_job_id) == 3
    assert set(profile.feedback_by_job_id.values()) == {"shortlist", "direction", "wrong"}
    assert profile.wrong_reason_counts["wrong_job_type"] == 1
    frontier_id = job_feedback_id(
        JobRecord(
            title="Strategic Partnerships Associate",
            company="Frontier",
            url="https://example.com/frontier",
            source="Calibration Examples",
            source_email_id="sheet",
        )
    )
    assert profile.direction_reasons_by_job_id[frontier_id] == (
        "strong_job_type",
        "strong_qualifications",
        "strong_seniority_match",
    )
    assert "strategic partnerships associate" in profile.preferred_terms
    assert "partnerships and market intelligence experience" in profile.preferred_terms
    assert "associate" in profile.preferred_terms
    assert "miami, fl" in profile.avoid_terms
