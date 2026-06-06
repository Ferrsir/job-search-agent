from __future__ import annotations

import argparse
import json
import os
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree as ET

from job_search_agent.config import Settings
from job_search_agent.config import UserProfile
from job_search_agent.calibration import job_feedback_id
from job_search_agent.dedupe import dedupe_key
from job_search_agent.models import JobRecord, ScoredJob
from job_search_agent.sheets_client import SheetsClient


DOCX_NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}

DEFAULT_EXAMPLE_PATHS: list[str] = []


@dataclass(frozen=True)
class ExampleDocument:
    path: Path
    kind: str
    text: str


def run() -> None:
    parser = argparse.ArgumentParser(
        description="Build a ChatGPT-ready application packet for a Sheet-backed job."
    )
    parser.add_argument("--list-jobs", action="store_true", help="Print the highest-scored jobs and exit.")
    parser.add_argument("--job-id", help="Sheet ID or dedupe key for the target job.")
    parser.add_argument("--title", help="Case-insensitive title text to match when no job ID is provided.")
    parser.add_argument("--company", help="Case-insensitive company text to match when no job ID is provided.")
    parser.add_argument("--manual-title", help="Build a packet without Sheets using this target job title.")
    parser.add_argument("--manual-company", help="Build a packet without Sheets using this target company.")
    parser.add_argument("--manual-location", default="", help="Location for a manually entered target job.")
    parser.add_argument("--manual-url", default="", help="URL for a manually entered target job.")
    parser.add_argument("--manual-requirements", default="", help="Main requirements for a manually entered target job.")
    parser.add_argument("--manual-fit-summary", default="", help="Why the manually entered job seems relevant.")
    parser.add_argument(
        "--example",
        action="append",
        default=[],
        help="Path to a resume or cover-letter .docx example. Can be passed more than once.",
    )
    parser.add_argument(
        "--output-dir",
        default="artifacts/application_packets",
        help="Directory where the packet should be written.",
    )
    parser.add_argument(
        "--generate",
        action="store_true",
        help="Use OPENAI_API_KEY to generate markdown drafts. Without this flag, only the prompt packet is created.",
    )
    args = parser.parse_args()

    manual_job = _manual_job(args)
    settings = Settings.from_env()
    jobs: list[ScoredJob] = []
    if not manual_job:
        if not settings.credentials_json:
            raise ValueError(
                "GOOGLE_APPLICATION_CREDENTIALS_JSON is required to read jobs from the Sheet backend. "
                "Use --manual-title and --manual-company to build a packet without Sheets."
            )
        sheets = SheetsClient.from_service_account_json(settings.credentials_json, settings.sheet_id)
        jobs = sheets.backend_scored_jobs()

    if args.list_jobs:
        _print_jobs(jobs)
        return

    job = manual_job or _select_job(jobs, job_id=args.job_id, title=args.title, company=args.company)
    examples = load_examples(args.example or _example_paths_from_env() or DEFAULT_EXAMPLE_PATHS)
    packet = build_application_packet(job, examples, user_profile=settings.user_profile)
    packet_dir = save_application_packet(packet, job, Path(args.output_dir))
    print(f"Saved application packet to {packet_dir}")

    if args.generate:
        draft = generate_with_openai(packet)
        (packet_dir / "ai_draft.md").write_text(draft, encoding="utf-8")
        print(f"Saved AI draft to {packet_dir / 'ai_draft.md'}")
    else:
        print("No API call made. Paste prompt.md into ChatGPT to generate the resume and cover letter.")


def load_examples(paths: list[str]) -> list[ExampleDocument]:
    examples: list[ExampleDocument] = []
    for raw_path in paths:
        path = Path(raw_path).expanduser()
        if not path.exists() or path.suffix.lower() != ".docx":
            continue
        text = extract_docx_text(path)
        if text:
            kind = "resume" if "resume" in path.name.lower() else "cover letter"
            examples.append(ExampleDocument(path=path, kind=kind, text=text))
    return examples


def extract_docx_text(path: Path) -> str:
    with zipfile.ZipFile(path) as archive:
        xml = archive.read("word/document.xml")
    root = ET.fromstring(xml)
    paragraphs: list[str] = []
    for paragraph in root.findall(".//w:p", DOCX_NS):
        parts = [node.text for node in paragraph.findall(".//w:t", DOCX_NS) if node.text]
        text = "".join(parts).strip()
        if text:
            paragraphs.append(text)
    return "\n".join(paragraphs)


def build_application_packet(
    job: ScoredJob,
    examples: list[ExampleDocument],
    user_profile: UserProfile | None = None,
) -> str:
    profile = user_profile or UserProfile.from_env()
    style_profile = _style_profile(examples)
    examples_text = "\n\n".join(_example_excerpt(example) for example in examples)
    job_context = _job_context(job)
    return f"""# Application Packet Prompt

You are helping {profile.full_name} draft job application materials. Produce:

1. A one-page resume tailored to the target role.
2. A cover letter in {profile.possessive_first_name} natural style.
3. A short tailoring note listing which experiences you emphasized and why.

## Non-Negotiables

- Do not invent degrees, employers, titles, dates, languages, skills, metrics, eligibility, citizenship, clearance status, or personal facts.
- Do not use generic AI-sounding phrasing such as "I am uniquely positioned," "dynamic professional," "leveraging synergies," or "passionate about driving impact."
- Keep the voice direct, specific, and human. It should read like a real application written by {profile.first_name}.
- If the job appears to require an engineering degree, software engineering background, or deep technical implementation, flag that concern before drafting.
- If a requirement is unknown, say so in the tailoring note instead of filling the gap.
- Prefer concrete experience from {profile.possessive_first_name} background over inflated claims.

## Target Job

{job_context}

## Voice And Structure Profile

{style_profile}

## User Context

{profile.application_context}

## Source Examples

These examples are older and should be treated as style references, not as perfect current facts.

{examples_text or "_No local examples were available. Use the voice profile and target job only._"}

## Output Format

Use Markdown with these exact sections:

### Tailored Resume

Write a clean one-page resume. Keep bullets concise and accomplishment-oriented. Use the strongest current experience from the uploaded context as the professional anchor.

### Cover Letter

Write a cover letter with a traditional greeting and signoff. Aim for 4 to 5 paragraphs. The letter should be specific to the company and role without sounding overproduced.

### Tailoring Note

List 5 to 7 bullets explaining the choices you made, any assumptions, and any missing information that {profile.first_name} should verify before applying.
"""


def save_application_packet(packet: str, job: ScoredJob, output_root: Path) -> Path:
    job_slug = _slug(f"{job.job.company}-{job.job.title}")
    packet_dir = output_root / job_slug
    packet_dir.mkdir(parents=True, exist_ok=True)
    (packet_dir / "prompt.md").write_text(packet, encoding="utf-8")
    (packet_dir / "job_context.json").write_text(
        json.dumps(_job_json(job), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return packet_dir


def generate_with_openai(prompt: str) -> str:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY is required when --generate is used.")
    from openai import OpenAI

    client = OpenAI(api_key=api_key)
    response = client.responses.create(
        model=os.getenv("APPLICATION_MATERIALS_MODEL", "gpt-5"),
        input=prompt,
    )
    return response.output_text


def _manual_job(args: argparse.Namespace) -> ScoredJob | None:
    if not args.manual_title and not args.manual_company:
        return None
    if not args.manual_title or not args.manual_company:
        raise ValueError("--manual-title and --manual-company must be used together.")
    job = JobRecord(
        title=args.manual_title,
        company=args.manual_company,
        location=args.manual_location,
        url=args.manual_url,
        source="Manual entry",
        source_email_id="manual-entry",
        fit_summary=args.manual_fit_summary,
        requirements_summary=args.manual_requirements,
    )
    return ScoredJob(
        job=job,
        total_score=0,
        labels=[],
        score_breakdown={},
        rationale=[item for item in [args.manual_fit_summary, args.manual_requirements] if item],
        destination_tab="Manual",
    )


def _select_job(
    jobs: list[ScoredJob],
    *,
    job_id: str | None,
    title: str | None,
    company: str | None,
) -> ScoredJob:
    if job_id:
        requested = _normalize_job_id(job_id)
        for job in jobs:
            identifiers = {
                dedupe_key(job.job),
                job.job.source_email_id,
                job_feedback_id(job.job),
                _normalize_job_id(dedupe_key(job.job)),
                _normalize_job_id(job.job.source_email_id),
                _normalize_job_id(job_feedback_id(job.job)),
            }
            if job_id in identifiers or requested in identifiers:
                return job
        raise ValueError(f"No job matched --job-id {job_id!r}. Run with --list-jobs to see options.")

    title_query = (title or "").strip().lower()
    company_query = (company or "").strip().lower()
    matches = [
        job
        for job in jobs
        if (not title_query or title_query in job.job.title.lower())
        and (not company_query or company_query in job.job.company.lower())
    ]
    if not matches:
        raise ValueError("No job matched the title/company filters. Run with --list-jobs to see options.")
    return sorted(matches, key=lambda item: item.total_score, reverse=True)[0]


def _print_jobs(jobs: list[ScoredJob]) -> None:
    for job in sorted(jobs, key=lambda item: item.total_score, reverse=True)[:40]:
        key = dedupe_key(job.job)
        website_key = job_feedback_id(job.job)
        print(f"{job.total_score:>3}  {job.job.company} | {job.job.title} | {job.job.location} | {key} | website id: {website_key}")


def _normalize_job_id(value: str) -> str:
    return value.strip().lower().replace(":", "-").replace("/", "-").replace(" ", "-")


def _example_paths_from_env() -> list[str]:
    value = os.getenv("APPLICATION_EXAMPLE_FILES", "")
    return [item.strip() for item in value.split(",") if item.strip()]


def _style_profile(examples: list[ExampleDocument]) -> str:
    resume_count = len([example for example in examples if example.kind == "resume"])
    letter_count = len(examples) - resume_count
    return f"""- Reference set loaded: {resume_count} resume document(s) and {letter_count} cover-letter document(s).
- Cover letters usually open by naming the role, the employer, and the practical reason the opportunity fits.
- The tone is formal but plainspoken: direct first-person statements, concrete examples, and minimal flourish.
- Paragraphs tend to move from interest in the organization, to relevant academic/professional background, to specific operating strengths, to a short close.
- Resume bullets should emphasize the strongest evidence from the resume and cover-letter examples, especially work that maps directly to the target job requirements.
- Prefer measured confidence over salesy language. The old letters are useful because they sound like a real person; keep that quality."""


def _example_excerpt(example: ExampleDocument) -> str:
    excerpt = _trim_words(example.text, 550 if example.kind == "resume" else 450)
    return f"### {example.path.name} ({example.kind})\n\n{excerpt}"


def _job_context(job: ScoredJob) -> str:
    facts = _job_json(job)
    return "\n".join(f"- {key}: {value}" for key, value in facts.items() if value)


def _job_json(job: ScoredJob) -> dict[str, object]:
    return {
        "company": job.job.company,
        "title": job.job.title,
        "location": job.job.location,
        "url": str(job.job.url),
        "source": job.job.source,
        "score": job.total_score,
        "labels": [label.value for label in job.labels],
        "fit_summary": job.job.fit_summary,
        "main_requirements": job.job.requirements_summary,
        "scoring_rationale": job.rationale,
        "job_id": dedupe_key(job.job),
    }


def _trim_words(text: str, limit: int) -> str:
    words = text.split()
    if len(words) <= limit:
        return text
    return " ".join(words[:limit]) + " ..."


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:90] or "application-packet"


if __name__ == "__main__":
    run()
