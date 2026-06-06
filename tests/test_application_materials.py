from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from job_search_agent.application_materials import (
    ExampleDocument,
    build_application_packet,
    extract_docx_text,
    save_application_packet,
    _select_job,
)
from job_search_agent.models import Classification, JobRecord, ScoredJob


def test_extract_docx_text_reads_paragraphs(tmp_path: Path) -> None:
    docx_path = tmp_path / "example.docx"
    document_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p><w:r><w:t>First paragraph</w:t></w:r></w:p>
    <w:p><w:r><w:t>Second </w:t></w:r><w:r><w:t>paragraph</w:t></w:r></w:p>
  </w:body>
</w:document>"""
    with zipfile.ZipFile(docx_path, "w") as archive:
        archive.writestr("word/document.xml", document_xml)

    assert extract_docx_text(docx_path) == "First paragraph\nSecond paragraph"


def test_build_application_packet_includes_job_requirements_and_voice_rules() -> None:
    scored = _scored_job()
    examples = [
        ExampleDocument(
            path=Path("Cover Letter_Test.docx"),
            kind="cover letter",
            text="Dear Hiring Manager,\nI am excited to apply because the mission fits my work.",
        )
    ]

    packet = build_application_packet(scored, examples)

    assert "Strategic Partnerships Manager" in packet
    assert "partnerships, stakeholder management, and defense innovation" in packet
    assert "Do not invent degrees" in packet
    assert "not as perfect current facts" in packet


def test_select_job_by_company_title_prefers_highest_score() -> None:
    lower = _scored_job(score=64)
    higher = _scored_job(score=91)

    selected = _select_job([lower, higher], job_id=None, title="partnerships", company="orbit")

    assert selected.total_score == 91


def test_select_job_accepts_website_feedback_id() -> None:
    scored = _scored_job()
    scored.job.source_email_id = "google-sheet:JR-0002"

    selected = _select_job([scored], job_id="google-sheet-jr-0002", title=None, company=None)

    assert selected == scored


def test_save_application_packet_writes_prompt_and_context(tmp_path: Path) -> None:
    scored = _scored_job()

    packet_dir = save_application_packet("prompt body", scored, tmp_path)

    assert (packet_dir / "prompt.md").read_text(encoding="utf-8") == "prompt body"
    assert "Strategic Partnerships Manager" in (packet_dir / "job_context.json").read_text(encoding="utf-8")


def test_select_job_raises_for_missing_match() -> None:
    with pytest.raises(ValueError, match="No job matched"):
        _select_job([_scored_job()], job_id=None, title="lawyer", company=None)


def _scored_job(score: int = 82) -> ScoredJob:
    job = JobRecord(
        title="Strategic Partnerships Manager",
        company="Orbit Works",
        location="Austin, TX",
        url="https://example.com/job",
        source="Google Sheet",
        source_email_id="sheet-1",
        fit_summary="Strong fit because it combines defense innovation, partnerships, and Austin.",
        requirements_summary="Main requirements include partnerships, stakeholder management, and defense innovation.",
    )
    return ScoredJob(
        job=job,
        total_score=score,
        labels=[Classification.APPLY_NOW, Classification.AUSTIN_MATCH],
        score_breakdown={"Sheet score": score},
        rationale=["Strong Austin fit"],
        destination_tab="Active Roles",
    )
