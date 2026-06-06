from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from job_search_agent.analytics import build_analytics_dashboard
from job_search_agent.calibration import job_feedback_id
from job_search_agent.config import UserProfile
from job_search_agent.models import Classification, ScoredJob


def render_weekly_digest(
    scored_jobs: list[ScoredJob],
    template_dir: Path | None = None,
    user_profile: UserProfile | None = None,
) -> str:
    return _render(scored_jobs, "weekly_digest.html.j2", template_dir, user_profile)


def render_weekly_email(
    scored_jobs: list[ScoredJob],
    template_dir: Path | None = None,
    user_profile: UserProfile | None = None,
) -> str:
    return _render(scored_jobs, "weekly_email.html.j2", template_dir, user_profile)


def render_preferences_page(template_dir: Path | None = None, user_profile: UserProfile | None = None) -> str:
    template_root = template_dir or Path(__file__).resolve().parents[2] / "templates"
    env = Environment(
        loader=FileSystemLoader(template_root),
        autoescape=select_autoescape(["html", "xml"]),
    )
    return env.get_template("preferences.html.j2").render(user_profile=user_profile or UserProfile.from_env())


def _render(
    scored_jobs: list[ScoredJob],
    template_name: str,
    template_dir: Path | None = None,
    user_profile: UserProfile | None = None,
) -> str:
    template_root = template_dir or Path(__file__).resolve().parents[2] / "templates"
    env = Environment(
        loader=FileSystemLoader(template_root),
        autoescape=select_autoescape(["html", "xml"]),
    )
    template = env.get_template(template_name)
    all_jobs = sorted(scored_jobs, key=_stable_job_sort_key)
    groups = _group_jobs(scored_jobs)
    return template.render(
        groups=groups,
        all_jobs=all_jobs,
        total=len(scored_jobs),
        weekly_takeaway=_weekly_takeaway(groups["Top Roles"]),
        job_feedback_id=job_feedback_id,
        newsletter_roles=_newsletter_roles(all_jobs, groups),
        analytics=build_analytics_dashboard(scored_jobs),
        user_profile=user_profile or UserProfile.from_env(),
    )


def save_digest(html: str, output_dir: Path, filename: str = "weekly_digest.html") -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / filename
    path.write_text(html, encoding="utf-8")
    return path


def _group_jobs(scored_jobs: list[ScoredJob]) -> dict[str, list[ScoredJob]]:
    buckets: dict[str, list[ScoredJob]] = {
        "Top Roles": [],
        "Dallas": [],
        "Austin": [],
        "Remote": [],
        "Discarded": [],
        "Expired": [],
    }
    mapping = [
        (Classification.APPLY_NOW, "Top Roles"),
        (Classification.DALLAS_MATCH, "Dallas"),
        (Classification.AUSTIN_MATCH, "Austin"),
        (Classification.REMOTE_MATCH, "Remote"),
        (Classification.REJECTED_NOTABLE, "Discarded"),
        (Classification.AUTO_REJECT, "Discarded"),
        (Classification.EXPIRED, "Expired"),
    ]
    sorted_jobs = sorted(scored_jobs, key=_stable_job_sort_key)
    for scored in sorted_jobs:
        if Classification.EXPIRED in scored.labels:
            buckets["Expired"].append(scored)
            continue
        for label, bucket in mapping:
            if label in scored.labels:
                buckets[bucket].append(scored)
    if len(buckets["Top Roles"]) < 5:
        seen_top_roles = {id(scored) for scored in buckets["Top Roles"]}
        supplements = [
            scored
            for scored in sorted_jobs
            if Classification.REJECTED_NOTABLE not in scored.labels
            and Classification.AUTO_REJECT not in scored.labels
            and Classification.EXPIRED not in scored.labels
            and id(scored) not in seen_top_roles
        ]
        buckets["Top Roles"] = [*buckets["Top Roles"], *supplements][:5]
    return buckets


def _newsletter_roles(all_jobs: list[ScoredJob], groups: dict[str, list[ScoredJob]]) -> list[ScoredJob]:
    roles: list[ScoredJob] = []
    seen: set[str] = set()
    discarded = {id(scored) for scored in [*groups["Discarded"], *groups["Expired"]]}
    for scored in [*groups["Top Roles"], *all_jobs]:
        if id(scored) in discarded:
            continue
        key = f"{scored.job.company}|{scored.job.title}|{scored.job.url}"
        if key in seen:
            continue
        seen.add(key)
        roles.append(scored)
        if len(roles) == 5:
            break
    return roles


def _stable_job_sort_key(scored: ScoredJob) -> tuple[int, str, str, str]:
    return (
        -scored.total_score,
        scored.job.company.lower(),
        scored.job.title.lower(),
        str(scored.job.url).lower(),
    )


def _weekly_takeaway(top_roles: list[ScoredJob]) -> str:
    if not top_roles:
        return "No priority roles are ready this week yet. The best move is to keep the search running and use new finds as calibration examples."
    leaders = top_roles[:2]
    role_phrase = _role_phrase(leaders)
    location_phrase = _location_phrase(top_roles)
    if len(top_roles) == 1:
        return f"One role is worth a close look this week: {role_phrase}. {location_phrase}"
    return f"The strongest leads this week are {role_phrase}. {location_phrase}"


def _role_phrase(roles: list[ScoredJob]) -> str:
    parts = [f"{scored.job.title} at {scored.job.company}" for scored in roles]
    if len(parts) == 1:
        return parts[0]
    return f"{parts[0]} and {parts[1]}"


def _location_phrase(top_roles: list[ScoredJob]) -> str:
    locations = [scored.job.location for scored in top_roles if scored.job.location]
    joined = " ".join(locations).lower()
    if "austin" in joined and "dallas" in joined:
        return "The pattern is Texas-forward, with both Austin and Dallas showing up in the highest-signal roles."
    if "austin" in joined:
        return "The best opportunities are leaning Austin, so prioritize role fit and hiring-manager access there."
    if "dallas" in joined or "fort worth" in joined or "dfw" in joined:
        return "The best opportunities are leaning Dallas, with defense and operations signals worth watching closely."
    if "remote" in joined:
        return "Remote flexibility is the main practical advantage, so prioritize roles with clear strategic ownership."
    return "Use these as the week’s priority review set before spending time on lower-fit listings."
