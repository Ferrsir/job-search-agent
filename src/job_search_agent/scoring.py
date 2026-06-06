from __future__ import annotations

import re

from job_search_agent.calibration import (
    DIRECTION,
    SHORTLIST,
    TOO_JUNIOR,
    TOO_SENIOR,
    WRONG,
    WRONG_JOB_TYPE,
    WRONG_LOCATION,
    WRONG_QUALIFICATIONS,
    CalibrationProfile,
    feedback_adjustment,
    preference_adjustment,
)
from job_search_agent.lifecycle import is_expired_job
from job_search_agent.models import Classification, JobRecord, ScoredJob


ROLE_KEYWORDS = {
    "investment banking intern": 25,
    "private equity intern": 25,
    "search fund intern": 25,
    "financial analyst intern": 24,
    "investment analyst intern": 24,
    "finance intern": 23,
    "valuation intern": 23,
    "corporate finance intern": 23,
    "m&a intern": 23,
    "equity research intern": 23,
    "wealth management intern": 21,
    "asset management intern": 21,
    "venture capital intern": 21,
    "analyst intern": 20,
    "summer analyst": 22,
    "finance internship": 22,
    "business internship": 18,
    "internship": 12,
    "strategic partnerships": 25,
    "partnerships": 23,
    "venture": 23,
    "investment": 22,
    "investment research": 24,
    "platform": 20,
    "corporate development": 22,
    "strategic finance": 22,
    "fp&a": 20,
    "investor relations": 18,
    "capital formation": 20,
    "government affairs": 22,
    "public policy": 21,
    "research analyst": 20,
    "strategy": 20,
    "market intelligence": 20,
    "business development": 14,
}

SECTOR_KEYWORDS = {
    "investment banking": 20,
    "private equity": 20,
    "search fund": 20,
    "valuation": 19,
    "m&a": 19,
    "corporate finance": 18,
    "financial analysis": 18,
    "equity research": 18,
    "asset management": 17,
    "wealth management": 17,
    "venture capital": 17,
    "fintech": 15,
    "commercial banking": 14,
    "regional bank": 13,
    "space": 20,
    "aerospace": 18,
    "venture": 18,
    "private capital": 18,
    "private equity": 18,
    "growth equity": 18,
    "capital markets": 16,
    "strategic finance": 16,
    "corporate development": 16,
    "quantum": 18,
    "osint": 18,
    "intelligence": 16,
    "advanced manufacturing": 16,
    "autonomy": 16,
    "drone": 16,
    "defense ai": 16,
    "cyber": 14,
    "dual-use": 16,
    "defense": 12,
}

WARM_PATH_KEYWORDS = {
    "svdg",
    "natsec100",
    "georgetown",
    "sponsor",
    "industry council",
}

AUTO_REJECT_PATTERNS = [
    r"\bentry[- ]level admin\b",
    r"\bsoftware engineer\b",
    r"\b(engineer|engineering manager|engineering lead|engineering director)\b",
    r"\btechnical degree required\b",
    r"\b(bachelor'?s|bs|ba|master'?s|ms|phd).{0,40}\b(engineering|computer science|cs|electrical|mechanical|aerospace engineering)\b",
    r"\b(engineering|computer science|cs|stem) degree required\b",
    r"\bactive security clearance\b",
    r"\bu\.?s\.? citizens? only\b",
    r"\bquota\b",
    r"\bpure sales\b",
]

TECHNICAL_MISMATCH_PATTERNS = [
    r"\b(c\+\+|python|java|rust|matlab|solidworks|cad|embedded|firmware|kubernetes|sql)\b",
    r"\b(machine learning|data scientist|software development|full stack|backend|frontend)\b",
    r"\bthermal|propulsion|avionics|electrical systems|mechanical design\b",
    r"\btechnical product manager\b",
]

ENGINEERING_TITLE_RE = re.compile(r"\bengineer(?:ing)?\b", re.I)


def score_job(
    job: JobRecord,
    warm_companies: set[str] | None = None,
    calibration: CalibrationProfile | None = None,
) -> ScoredJob:
    haystack = _haystack(job)
    auto_reject_reasons = _auto_reject_reasons(haystack)
    role_fit = 0 if auto_reject_reasons else _keyword_score(haystack, ROLE_KEYWORDS, 25)
    sector_fit = _keyword_score(haystack, SECTOR_KEYWORDS, 20)
    location_fit = _score_location(job.location)
    warm_intro = _score_warm_intro(job, haystack, warm_companies or set())
    career_upside = _score_career_upside(haystack, role_fit, sector_fit)
    compensation = _score_compensation(haystack)
    seniority = _score_seniority(haystack)
    student_fit = _score_student_fit(haystack)
    practicality = _score_practicality(job, haystack)
    technical_mismatch = _score_technical_mismatch(job, haystack)

    breakdown = {
        "Role fit": role_fit,
        "Sector fit": sector_fit,
        "Location fit": location_fit,
        "Warm intro potential": warm_intro,
        "Career upside": career_upside,
        "Compensation fit": compensation,
        "Seniority fit": seniority,
        "Student fit": student_fit,
        "Application practicality": practicality,
        "Technical mismatch": technical_mismatch,
    }
    feedback_delta, feedback_signal = feedback_adjustment(job, calibration)
    preference_delta, preference_rationale = preference_adjustment(haystack, calibration)
    reason_delta, reason_rationale = wrong_reason_adjustment(job, haystack, calibration)
    calibration_delta = feedback_delta + preference_delta + reason_delta
    if calibration_delta:
        breakdown["Feedback calibration"] = calibration_delta
    total = max(0, min(100, sum(breakdown.values())))
    labels = _classify(job, total, breakdown, auto_reject_reasons, feedback_signal)
    destination = (
        "Expired"
        if Classification.EXPIRED in labels
        else "Rejected Notable"
        if Classification.AUTO_REJECT in labels or feedback_signal == WRONG
        else "Active Roles"
    )
    rationale = auto_reject_reasons or _rationale(breakdown, labels)
    if feedback_signal:
        rationale.insert(0, f"Feedback signal: {feedback_signal}")
    rationale.extend(preference_rationale)
    rationale.extend(reason_rationale)
    return ScoredJob(
        job=job,
        total_score=total,
        labels=labels,
        score_breakdown=breakdown,
        rationale=rationale,
        destination_tab=destination,
    )


def score_jobs(
    jobs: list[JobRecord],
    warm_companies: set[str] | None = None,
    calibration: CalibrationProfile | None = None,
) -> list[ScoredJob]:
    return [score_job(job, warm_companies, calibration) for job in jobs]


def should_skip_job(job: JobRecord) -> bool:
    return bool(ENGINEERING_TITLE_RE.search(job.title) or ENGINEERING_TITLE_RE.search(job.company))


def _haystack(job: JobRecord) -> str:
    return " ".join(
        [job.title, job.company, job.location, job.notes, job.fit_summary, job.requirements_summary, job.raw_text]
    ).lower()


def _keyword_score(text: str, weighted_keywords: dict[str, int], max_score: int) -> int:
    matches = [score for keyword, score in weighted_keywords.items() if keyword in text]
    return min(max(matches, default=0), max_score)


def _score_location(location: str) -> int:
    loc = location.lower()
    if any(city in loc for city in ("denton", "plano", "frisco", "richardson", "irving", "addison")):
        return 15
    if "austin" in loc:
        return 13
    if "houston" in loc:
        return 12
    if "dallas" in loc or "fort worth" in loc or "dfw" in loc:
        return 15
    if "remote" in loc:
        return 12
    if "texas" in loc or "tx" in loc:
        return 11
    if "washington" in loc or re.search(r"\bdc\b", loc):
        return 6
    if not loc:
        return 5
    return 3


def _score_warm_intro(job: JobRecord, text: str, warm_companies: set[str]) -> int:
    company = job.company.lower()
    if any(company == warm.lower() or warm.lower() in company for warm in warm_companies):
        return 15
    if any(keyword in text for keyword in WARM_PATH_KEYWORDS):
        return 12
    return 5


def _score_career_upside(text: str, role_fit: int, sector_fit: int) -> int:
    if _looks_student_friendly(text) and role_fit >= 18:
        return 10
    if _looks_too_senior(text) or role_fit >= 22 and sector_fit >= 16:
        return 8
    if role_fit >= 18 and sector_fit >= 12:
        return 8
    return 5


def _score_compensation(text: str) -> int:
    hourly = re.search(r"\$?(\d{2})\s*(?:-|–|to)\s*\$?(\d{2})\s*/?\s*(?:hour|hr)", text)
    if hourly:
        low = int(hourly.group(1))
        high = int(hourly.group(2))
        if low >= 18 and high <= 35:
            return 6
        if high >= 18:
            return 4
    salary = re.search(r"\$?(\d{2,3})[kK]", text)
    if salary and int(salary.group(1)) >= 100:
        return 5
    if salary and int(salary.group(1)) < 80:
        return 1
    return 3


def _score_seniority(text: str) -> int:
    if _looks_too_advanced_for_ferris(text):
        return -12
    if _looks_student_friendly(text):
        return 12
    if re.search(r"\b(intern|internship|fellow|fellowship|entry[- ]level|campus|student)\b", text):
        return 8
    if re.search(r"\b(manager|lead|senior|principal|director)\b", text):
        return -8
    if re.search(r"\bassociate\b", text):
        return 3
    return 3


def _score_student_fit(text: str) -> int:
    if _looks_too_advanced_for_ferris(text):
        return -18
    if re.search(r"\b(freshman|freshmen|first[- ]year|1st[- ]year|sophomore|second[- ]year|2nd[- ]year|underclass)\b", text):
        return 18
    if re.search(r"\b(high school|incoming college|current student|currently enrolled|undergraduate student|campus)\b", text):
        return 14
    if _looks_student_friendly(text) and _looks_business_finance(text):
        return 14
    if re.search(r"\b(intern|internship|summer analyst|early career|student program|students and graduates)\b", text):
        return 8
    return 0


def _score_practicality(job: JobRecord, text: str) -> int:
    if "active security clearance" in text or "u.s. citizen" in text:
        return 0
    if _looks_completed_degree_required(text):
        return 1
    if job.url:
        return 5
    return 2


def _score_technical_mismatch(job: JobRecord, text: str) -> int:
    title = job.title.lower()
    if any(role in title for role in ("business development", "partnership", "strategy", "policy", "operations")):
        return 0
    if any(re.search(pattern, text) for pattern in TECHNICAL_MISMATCH_PATTERNS):
        return -12
    return 0


def wrong_reason_adjustment(
    job: JobRecord,
    text: str,
    calibration: CalibrationProfile | None,
) -> tuple[int, list[str]]:
    if not calibration or not calibration.wrong_reason_counts:
        return 0, []
    penalties: list[tuple[str, int]] = []
    counts = calibration.wrong_reason_counts
    if counts.get(TOO_SENIOR) and _looks_too_senior(text):
        penalties.append(("too senior", min(4 + counts[TOO_SENIOR] * 2, 10)))
    if counts.get(TOO_JUNIOR) and _looks_too_junior(text):
        penalties.append(("too junior", min(4 + counts[TOO_JUNIOR] * 2, 10)))
    if counts.get(WRONG_QUALIFICATIONS) and (
        _score_technical_mismatch(job, text) < 0 or any(re.search(pattern, text) for pattern in AUTO_REJECT_PATTERNS)
    ):
        penalties.append(("wrong qualifications", min(5 + counts[WRONG_QUALIFICATIONS] * 2, 12)))
    if counts.get(WRONG_LOCATION) and _location_matches_avoid(job.location, calibration.avoid_terms):
        penalties.append(("wrong location", min(4 + counts[WRONG_LOCATION] * 2, 10)))
    if counts.get(WRONG_JOB_TYPE) and _title_matches_avoid(job.title, calibration.avoid_terms):
        penalties.append(("wrong job type", min(4 + counts[WRONG_JOB_TYPE] * 2, 10)))
    if not penalties:
        return 0, []
    total_penalty = min(sum(amount for _, amount in penalties), 18)
    labels = ", ".join(label for label, _ in penalties[:3])
    return -total_penalty, [f"Wrong-direction reason calibration: {labels}"]


def _looks_too_senior(text: str) -> bool:
    return bool(re.search(r"\b(vp|vice president|chief|c-suite|executive|head of|principal|director|staff|senior manager)\b", text))


def _looks_too_junior(text: str) -> bool:
    return bool(re.search(r"\b(intern|internship|fellow|fellowship|entry[- ]level|junior|assistant|coordinator)\b", text))


def _looks_student_friendly(text: str) -> bool:
    return bool(
        re.search(
            r"\b(intern|internship|summer analyst|student|students|campus|early career|undergraduate|freshman|freshmen|first[- ]year|sophomore|second[- ]year|currently enrolled)\b",
            text,
        )
    )


def _looks_business_finance(text: str) -> bool:
    return bool(
        re.search(
            r"\b(finance|financial|investment|banking|private equity|search fund|valuation|m&a|corporate finance|equity research|wealth management|asset management|venture capital|business|accounting|advisory|consulting)\b",
            text,
        )
    )


def _looks_completed_degree_required(text: str) -> bool:
    return bool(
        re.search(
            r"\b(bachelor'?s degree required|completed bachelor'?s|degree required|graduate degree|required graduation date|must have graduated)\b",
            text,
        )
    )


def _looks_too_advanced_for_ferris(text: str) -> bool:
    if _looks_too_senior(text):
        return True
    return bool(
        re.search(
            r"\b(rising senior|senior standing|juniors? and seniors?|class of 202[6-8]|mba|master'?s|graduate student|graduate degree|phd|postgraduate|completed bachelor'?s|bachelor'?s degree required|must have graduated)\b",
            text,
        )
    )


def _location_matches_avoid(location: str, avoid_terms: tuple[str, ...]) -> bool:
    location = location.lower()
    return any(term in location or location in term for term in avoid_terms if len(term) >= 3)


def _title_matches_avoid(title: str, avoid_terms: tuple[str, ...]) -> bool:
    title = title.lower()
    title_tokens = set(re.findall(r"[a-z0-9]+", title))
    for term in avoid_terms:
        term_tokens = {token for token in re.findall(r"[a-z0-9]+", term.lower()) if len(token) >= 4}
        if term in title or (term_tokens and len(title_tokens & term_tokens) >= min(2, len(term_tokens))):
            return True
    return False


def _auto_reject_reasons(text: str) -> list[str]:
    reasons = []
    for pattern in AUTO_REJECT_PATTERNS:
        if re.search(pattern, text):
            signal = pattern.replace(r"\b", "")
            reasons.append(f"Auto-reject signal: {signal}")
    return reasons


def _classify(
    job: JobRecord,
    total: int,
    breakdown: dict[str, int],
    auto_reject_reasons: list[str],
    feedback_signal: str | None = None,
) -> list[Classification]:
    if is_expired_job(job):
        return [Classification.EXPIRED]
    if auto_reject_reasons:
        return [Classification.AUTO_REJECT]
    if feedback_signal == WRONG:
        return [Classification.REJECTED_NOTABLE]
    labels: list[Classification] = []
    loc = job.location.lower()
    if feedback_signal == SHORTLIST or total >= 75:
        labels.append(Classification.APPLY_NOW)
    elif feedback_signal == DIRECTION or total >= 62 or breakdown["Warm intro potential"] >= 12:
        labels.append(Classification.WARM_INTRO_FIRST)
    else:
        labels.append(Classification.MONITOR)
    if "remote" in loc:
        labels.append(Classification.REMOTE_MATCH)
    if "austin" in loc:
        labels.append(Classification.AUSTIN_MATCH)
    if "dallas" in loc or "fort worth" in loc or "dfw" in loc:
        labels.append(Classification.DALLAS_MATCH)
    return labels


def _rationale(breakdown: dict[str, int], labels: list[Classification]) -> list[str]:
    top = sorted(
        ((name, score) for name, score in breakdown.items() if score > 0),
        key=lambda item: item[1],
        reverse=True,
    )[:3]
    rationale = [f"{name}: {score}" for name, score in top]
    if breakdown.get("Technical mismatch", 0) < 0:
        rationale.append("Penalty: role appears more technical than target profile")
    if breakdown.get("Seniority fit", 0) < 0 or breakdown.get("Student fit", 0) < 0:
        rationale.append("Penalty: role appears aimed at senior, graduate, or completed-degree candidates")
    return rationale + [f"Label: {label}" for label in labels]
