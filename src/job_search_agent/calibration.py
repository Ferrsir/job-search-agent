from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from job_search_agent.models import JobRecord


FeedbackSignal = str
WrongReason = str
DirectionReason = str

SHORTLIST = "shortlist"
DIRECTION = "direction"
WRONG = "wrong"

TOO_SENIOR = "too_senior"
TOO_JUNIOR = "too_junior"
WRONG_QUALIFICATIONS = "wrong_qualifications"
WRONG_LOCATION = "wrong_location"
WRONG_JOB_TYPE = "wrong_job_type"
STRONG_SENIORITY_MATCH = "strong_seniority_match"
STRONG_JOB_TYPE = "strong_job_type"
STRONG_QUALIFICATIONS = "strong_qualifications"

FEEDBACK_ADJUSTMENTS: dict[FeedbackSignal, int] = {
    SHORTLIST: 10,
    DIRECTION: 4,
    WRONG: -18,
}


@dataclass(frozen=True)
class CalibrationProfile:
    feedback_by_job_id: dict[str, FeedbackSignal] = field(default_factory=dict)
    wrong_reasons_by_job_id: dict[str, tuple[WrongReason, ...]] = field(default_factory=dict)
    direction_reasons_by_job_id: dict[str, tuple[DirectionReason, ...]] = field(default_factory=dict)
    wrong_reason_counts: dict[WrongReason, int] = field(default_factory=dict)
    preferred_terms: tuple[str, ...] = ()
    avoid_terms: tuple[str, ...] = ()

    def merge(self, other: "CalibrationProfile") -> "CalibrationProfile":
        reason_counts = dict(self.wrong_reason_counts)
        for reason, count in other.wrong_reason_counts.items():
            reason_counts[reason] = reason_counts.get(reason, 0) + count
        return CalibrationProfile(
            feedback_by_job_id={**self.feedback_by_job_id, **other.feedback_by_job_id},
            wrong_reasons_by_job_id={**self.wrong_reasons_by_job_id, **other.wrong_reasons_by_job_id},
            direction_reasons_by_job_id={**self.direction_reasons_by_job_id, **other.direction_reasons_by_job_id},
            wrong_reason_counts=reason_counts,
            preferred_terms=tuple(dict.fromkeys([*self.preferred_terms, *other.preferred_terms])),
            avoid_terms=tuple(dict.fromkeys([*self.avoid_terms, *other.avoid_terms])),
        )


def job_feedback_id(job: JobRecord) -> str:
    if job.source_email_id.startswith("google-sheet:"):
        return _sanitize_feedback_id(job.source_email_id)
    value = f"{job.company}|{job.title}|{job.url}"
    return _sanitize_feedback_id(value)


def _sanitize_feedback_id(value: str) -> str:
    value = value.lower()
    for char in (" ", "/", ":", "?", "&"):
        value = value.replace(char, "-")
    return value


def load_feedback_export(path: Path | None) -> CalibrationProfile:
    if not path or not path.exists():
        return CalibrationProfile()
    payload = json.loads(path.read_text(encoding="utf-8"))
    wrong_reasons = _normalize_wrong_reasons_map(payload.get("wrongReasons", {}))
    direction_reasons = _normalize_direction_reasons_map(payload.get("directionReasons", {}))
    jobs = payload.get("jobs", {})
    avoid_terms = [
        *_preference_terms(payload.get("preferences", {}), keys=("avoid",)),
        *_avoid_terms_from_wrong_reasons(wrong_reasons, jobs),
    ]
    preferred_terms = [
        *_preference_terms(payload.get("preferences", {}), keys=("locations", "roles", "sectors", "priorities")),
        *_preferred_terms_from_direction_reasons(direction_reasons, jobs),
    ]
    return CalibrationProfile(
        feedback_by_job_id=_normalize_feedback_map(payload.get("feedback", {})),
        wrong_reasons_by_job_id=wrong_reasons,
        direction_reasons_by_job_id=direction_reasons,
        wrong_reason_counts=_reason_counts(wrong_reasons),
        preferred_terms=tuple(dict.fromkeys(preferred_terms)),
        avoid_terms=tuple(dict.fromkeys(avoid_terms)),
    )


def calibration_from_sheet_rows(rows: list[list[str]]) -> CalibrationProfile:
    if not rows:
        return CalibrationProfile()
    headers = [_normalize_header(cell) for cell in rows[0]]
    feedback: dict[str, FeedbackSignal] = {}
    wrong_reasons: dict[str, tuple[WrongReason, ...]] = {}
    direction_reasons: dict[str, tuple[DirectionReason, ...]] = {}
    avoid_terms: list[str] = []
    preferred_terms: list[str] = []
    for row in rows[1:]:
        record = {headers[index]: cell for index, cell in enumerate(row) if index < len(headers)}
        signal = _normalize_signal(
            record.get("feedback")
            or record.get("rating")
            or record.get("label")
            or record.get("classification")
            or ""
        )
        if not signal:
            continue
        job_id = record.get("job_id") or record.get("job id") or ""
        if not job_id:
            company = record.get("company", "")
            title = record.get("title") or record.get("role") or ""
            url = record.get("url") or record.get("link") or ""
            if company and title:
                job_id = job_feedback_id(
                    JobRecord(
                        title=title,
                        company=company,
                        url=url,
                        source="Calibration Examples",
                        source_email_id="sheet",
                    )
                )
        if job_id:
            feedback[job_id] = signal
            title = record.get("title") or record.get("role") or ""
            location = record.get("location", "")
            requirements = record.get("main requirements") or record.get("requirements") or record.get("qualifications") or ""
            reasons = _normalize_wrong_reasons(
                record.get("wrong reasons")
                or record.get("wrong reason")
                or record.get("reason")
                or record.get("reasons")
                or ""
            )
            if signal == WRONG and reasons:
                wrong_reasons[job_id] = reasons
                avoid_terms.extend(
                    _avoid_terms_from_wrong_job_record(
                        reasons,
                        company=record.get("company", ""),
                        title=title,
                        location=location,
                        requirements=requirements,
                    )
                )
            strengths = _normalize_direction_reasons(
                record.get("direction reasons")
                or record.get("direction reason")
                or record.get("strong reasons")
                or record.get("strong reason")
                or record.get("strengths")
                or ""
            )
            if signal == DIRECTION and strengths:
                direction_reasons[job_id] = strengths
                preferred_terms.extend(_preferred_terms_from_direction_job_record(strengths, title=title, requirements=requirements))
    return CalibrationProfile(
        feedback_by_job_id=feedback,
        wrong_reasons_by_job_id=wrong_reasons,
        direction_reasons_by_job_id=direction_reasons,
        wrong_reason_counts=_reason_counts(wrong_reasons),
        preferred_terms=tuple(dict.fromkeys(preferred_terms)),
        avoid_terms=tuple(dict.fromkeys(avoid_terms)),
    )


def feedback_adjustment(job: JobRecord, calibration: CalibrationProfile | None) -> tuple[int, FeedbackSignal | None]:
    if not calibration:
        return 0, None
    signal = calibration.feedback_by_job_id.get(job_feedback_id(job))
    if not signal:
        return 0, None
    return FEEDBACK_ADJUSTMENTS.get(signal, 0), signal


def preference_adjustment(text: str, calibration: CalibrationProfile | None) -> tuple[int, list[str]]:
    if not calibration:
        return 0, []
    matched_preferred = [term for term in calibration.preferred_terms if _contains_term(text, term)]
    matched_avoid = [term for term in calibration.avoid_terms if _contains_term(text, term)]
    adjustment = min(len(matched_preferred) * 2, 8) - min(len(matched_avoid) * 4, 16)
    rationale = []
    if matched_preferred:
        rationale.append(f"Preference match: {', '.join(matched_preferred[:3])}")
    if matched_avoid:
        rationale.append(f"Preference avoid signal: {', '.join(matched_avoid[:3])}")
    return adjustment, rationale


def _normalize_feedback_map(feedback: dict[str, str]) -> dict[str, FeedbackSignal]:
    normalized: dict[str, FeedbackSignal] = {}
    for job_id, raw in feedback.items():
        if isinstance(raw, dict):
            raw = raw.get("signal", "")
        if signal := _normalize_signal(str(raw)):
            normalized[job_id] = signal
    return normalized


def _normalize_signal(value: str) -> FeedbackSignal | None:
    normalized = value.strip().lower().replace("_", " ").replace("-", " ")
    if normalized in {"shortlist", "right job", "priority", "yes"}:
        return SHORTLIST
    if normalized in {"direction", "right direction", "maybe", "not priority", "not a priority"}:
        return DIRECTION
    if normalized in {"wrong", "wrong direction", "no", "reject"}:
        return WRONG
    return None


def _normalize_wrong_reasons_map(raw: dict[str, object]) -> dict[str, tuple[WrongReason, ...]]:
    return {job_id: reasons for job_id, value in raw.items() if (reasons := _normalize_wrong_reasons(value))}


def _normalize_direction_reasons_map(raw: dict[str, object]) -> dict[str, tuple[DirectionReason, ...]]:
    return {job_id: reasons for job_id, value in raw.items() if (reasons := _normalize_direction_reasons(value))}


def _normalize_wrong_reasons(value: object) -> tuple[WrongReason, ...]:
    if isinstance(value, str):
        candidates = re.split(r"[\n,;/|]+", value)
    elif isinstance(value, list):
        candidates = [str(item) for item in value]
    else:
        candidates = []
    reasons = [_normalize_wrong_reason(item) for item in candidates]
    return tuple(dict.fromkeys(reason for reason in reasons if reason))


def _normalize_direction_reasons(value: object) -> tuple[DirectionReason, ...]:
    if isinstance(value, str):
        candidates = re.split(r"[\n,;/|]+", value)
    elif isinstance(value, list):
        candidates = [str(item) for item in value]
    else:
        candidates = []
    reasons = [_normalize_direction_reason(item) for item in candidates]
    return tuple(dict.fromkeys(reason for reason in reasons if reason))


def _normalize_wrong_reason(value: str) -> WrongReason | None:
    normalized = value.strip().lower().replace("-", " ").replace("_", " ")
    normalized = re.sub(r"\s+", " ", normalized)
    aliases = {
        "too senior": TOO_SENIOR,
        "senior": TOO_SENIOR,
        "too junior": TOO_JUNIOR,
        "junior": TOO_JUNIOR,
        "wrong qualifications": WRONG_QUALIFICATIONS,
        "qualification mismatch": WRONG_QUALIFICATIONS,
        "qualifications": WRONG_QUALIFICATIONS,
        "wrong location": WRONG_LOCATION,
        "location": WRONG_LOCATION,
        "wrong job type": WRONG_JOB_TYPE,
        "job type": WRONG_JOB_TYPE,
        "wrong role": WRONG_JOB_TYPE,
    }
    return aliases.get(normalized)


def _normalize_direction_reason(value: str) -> DirectionReason | None:
    normalized = value.strip().lower().replace("-", " ").replace("_", " ")
    normalized = re.sub(r"\s+", " ", normalized)
    aliases = {
        "strong seniority match": STRONG_SENIORITY_MATCH,
        "seniority match": STRONG_SENIORITY_MATCH,
        "strong seniority": STRONG_SENIORITY_MATCH,
        "strong job type": STRONG_JOB_TYPE,
        "job type": STRONG_JOB_TYPE,
        "strong role type": STRONG_JOB_TYPE,
        "strong qualifications": STRONG_QUALIFICATIONS,
        "qualifications": STRONG_QUALIFICATIONS,
        "strong qualification match": STRONG_QUALIFICATIONS,
    }
    return aliases.get(normalized)


def _reason_counts(wrong_reasons: dict[str, tuple[WrongReason, ...]]) -> dict[WrongReason, int]:
    counts: dict[WrongReason, int] = {}
    for reasons in wrong_reasons.values():
        for reason in reasons:
            counts[reason] = counts.get(reason, 0) + 1
    return counts


def _avoid_terms_from_wrong_reasons(
    wrong_reasons: dict[str, tuple[WrongReason, ...]],
    jobs: dict[str, object],
) -> tuple[str, ...]:
    terms: list[str] = []
    for job_id, reasons in wrong_reasons.items():
        raw = jobs.get(job_id, {})
        if not isinstance(raw, dict):
            continue
        terms.extend(
            _avoid_terms_from_wrong_job_record(
                reasons,
                company=str(raw.get("company", "")),
                title=str(raw.get("title", "")),
                location=str(raw.get("location", "")),
                requirements=str(raw.get("requirements", "")),
            )
        )
    return tuple(dict.fromkeys(terms))


def _avoid_terms_from_wrong_job_record(
    reasons: tuple[WrongReason, ...],
    *,
    company: str,
    title: str,
    location: str,
    requirements: str,
) -> list[str]:
    terms: list[str] = []
    if WRONG_LOCATION in reasons:
        terms.extend(_clean_terms(location))
    if WRONG_JOB_TYPE in reasons:
        terms.extend(_clean_terms(title))
    if WRONG_QUALIFICATIONS in reasons:
        terms.extend(_clean_terms(requirements))
    return terms


def _preferred_terms_from_direction_reasons(
    direction_reasons: dict[str, tuple[DirectionReason, ...]],
    jobs: dict[str, object],
) -> tuple[str, ...]:
    terms: list[str] = []
    for job_id, reasons in direction_reasons.items():
        raw = jobs.get(job_id, {})
        if not isinstance(raw, dict):
            continue
        title = str(raw.get("title", ""))
        requirements = str(raw.get("requirements", ""))
        terms.extend(_preferred_terms_from_direction_job_record(reasons, title=title, requirements=requirements))
    return tuple(dict.fromkeys(terms))


def _preferred_terms_from_direction_job_record(
    reasons: tuple[DirectionReason, ...],
    *,
    title: str,
    requirements: str,
) -> list[str]:
    terms: list[str] = []
    if STRONG_JOB_TYPE in reasons:
        terms.extend(_clean_terms(title))
    if STRONG_QUALIFICATIONS in reasons:
        terms.extend(_clean_terms(requirements))
    if STRONG_SENIORITY_MATCH in reasons:
        terms.extend(_seniority_terms(title))
    return terms


def _seniority_terms(title: str) -> list[str]:
    title = title.lower()
    terms = []
    for term in ("associate", "analyst", "manager", "senior associate", "senior analyst", "program manager"):
        if term in title:
            terms.append(term)
    return terms


def _clean_terms(value: str) -> list[str]:
    value = re.sub(r"https?://\S+", " ", value.lower())
    value = re.sub(r"\s+", " ", value).strip(" ,;/|-")
    if not value or len(value) < 3 or value in {"unknown", "location tbd"}:
        return []
    return [value]


def _preference_terms(preferences: dict[str, str], keys: tuple[str, ...]) -> tuple[str, ...]:
    terms: list[str] = []
    for key in keys:
        value = preferences.get(key, "")
        for term in re.split(r"[\n,;/]+", value):
            cleaned = term.strip().lower()
            if len(cleaned) >= 3:
                terms.append(cleaned)
    return tuple(dict.fromkeys(terms))


def _normalize_header(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def _contains_term(text: str, term: str) -> bool:
    return term in text or term.replace(" / ", " ") in text
