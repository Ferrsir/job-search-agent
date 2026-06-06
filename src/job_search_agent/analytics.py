from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass

from job_search_agent.models import Classification, ScoredJob
from job_search_agent.calibration import job_feedback_id


QUALIFICATION_KEYWORDS = {
    "Aerospace / space": ("aerospace", "space", "satellite", "orbital", "defense"),
    "Business development": ("business development", "partnership", "partnerships", "sales strategy"),
    "Contracts": ("contract", "contracts", "procurement", "vendor", "far/dfars"),
    "Finance": ("financial", "finance", "fp&a", "budget", "forecast", "valuation"),
    "Government": ("government", "public sector", "federal", "dod", "policy"),
    "Market research": ("market research", "market intelligence", "competitive", "research"),
    "Operations": ("operations", "program management", "project management", "cross-functional"),
    "Strategy": ("strategy", "strategic", "growth", "commercial", "go-to-market"),
}


ROLE_FAMILY_KEYWORDS = {
    "Technical / Not Fit": (
        "engineer",
        "engineering",
        "technician",
        "avionics",
        "spacecraft integration",
        "automation controls",
        "test specialist",
        "test supervisor",
    ),
    "Partnerships / BD": ("partnership", "business development", "commercial", "growth", "sales"),
    "Strategy / BizOps": ("strategy", "strategic", "chief of staff", "business operations", "bizops"),
    "Investment / Finance": ("investment", "venture", "capital", "finance", "fp&a", "financial", "corp dev"),
    "Policy / Government": ("policy", "government affairs", "public sector", "federal", "regulatory"),
    "Research / Intelligence": ("research", "analyst", "intelligence", "market intelligence"),
    "Contracts / Legal": ("contract", "contracts", "counsel", "legal"),
    "Program / Operations": ("operations", "program", "project", "procurement", "supply chain"),
    "Communications / Marketing": ("communications", "marketing", "public relations", "content"),
    "People / Talent": ("people", "talent", "recruiting", "human resources", "hr business partner"),
}

TARGET_JOB_TYPES = {
    "Partnerships / BD",
    "Strategy / BizOps",
    "Investment / Finance",
    "Policy / Government",
    "Research / Intelligence",
    "Program / Operations",
    "Contracts / Legal",
    "Communications / Marketing",
    "People / Talent",
    "Other Target Roles",
}

GEO_POINT_COORDS = {
    "Austin": (45, 69),
    "Dallas-Fort Worth": (47, 62),
    "Remote": (28, 35),
    "Washington, DC": (77, 51),
    "Other US": (55, 48),
    "International": (87, 34),
}

CITY_POINT_COORDS = {
    "Austin": (50, 75),
    "Dallas-Fort Worth": (49, 68),
    "Washington, DC": (79, 53),
    "San Francisco Bay Area": (15, 53),
    "Los Angeles": (17, 67),
    "Denver / Boulder": (39, 55),
    "Huntsville": (65, 67),
    "San Diego": (17, 72),
    "Remote": (29, 32),
}

CITY_GEO_COORDS = {
    "Austin": (-97.7431, 30.2672),
    "Dallas-Fort Worth": (-97.0403, 32.8998),
    "Washington, DC": (-77.0369, 38.9072),
    "San Francisco Bay Area": (-122.05, 37.48),
    "Los Angeles": (-118.2437, 34.0522),
    "Denver / Boulder": (-105.0, 39.95),
    "Huntsville": (-86.5861, 34.7304),
    "San Diego": (-117.1611, 32.7157),
}


@dataclass(frozen=True)
class JobAnalysis:
    geography: str
    role_family: str
    qualifications: list[str]
    salary_min: int | None = None
    salary_max: int | None = None
    salary_text: str = ""
    seniority: str = ""
    degree_requirement: str = ""
    clearance_requirement: str = ""
    work_mode: str = ""
    contact_strength: int = 0


@dataclass(frozen=True)
class DashboardRow:
    label: str
    count: int
    share: int
    detail: str = ""


@dataclass(frozen=True)
class GeoPoint:
    label: str
    count: int
    share: int
    x: int
    y: int


@dataclass(frozen=True)
class CityJob:
    title: str
    company: str
    score: int
    url: str


@dataclass(frozen=True)
class CityMarket:
    label: str
    count: int
    x: int
    y: int
    longitude: float | None
    latitude: float | None
    jobs: list[CityJob]


@dataclass(frozen=True)
class JobSignal:
    company: str
    geography: str
    role_family: str
    qualifications: tuple[str, ...]
    seniority: str
    work_mode: str
    degree_requirement: str
    clearance_requirement: str


@dataclass(frozen=True)
class AnalyticsDashboard:
    geography_role_demand: dict[str, list[DashboardRow]]
    top_companies_by_geography: dict[str, list[DashboardRow]]
    strongest_contacts: list[DashboardRow]
    qualification_demand: list[DashboardRow]
    salary_by_role_family: list[DashboardRow]
    role_family_mix: list[DashboardRow]
    seniority_mix: list[DashboardRow]
    work_mode_mix: list[DashboardRow]
    degree_mix: list[DashboardRow]
    clearance_mix: list[DashboardRow]
    score_bands: list[DashboardRow]
    geography_map: list[GeoPoint]
    city_markets: list[CityMarket]
    job_signals: dict[str, JobSignal]
    cleanup_count: int = 0


def analyze_job(scored: ScoredJob) -> JobAnalysis:
    text = _job_text(scored)
    salary_min, salary_max, salary_text = _salary(text)
    return JobAnalysis(
        geography=_geography(scored.job.location),
        role_family=_role_family(text),
        qualifications=_qualifications(text),
        salary_min=salary_min,
        salary_max=salary_max,
        salary_text=salary_text,
        seniority=_seniority(text),
        degree_requirement=_degree_requirement(text),
        clearance_requirement=_clearance_requirement(text),
        work_mode=_work_mode(scored.job.location, text),
        contact_strength=_contact_strength(scored),
    )


def analysis_sheet_values(scored: ScoredJob) -> dict[str, str]:
    analysis = analyze_job(scored)
    return {
        "geography": analysis.geography,
        "role family": analysis.role_family,
        "qualifications": ", ".join(analysis.qualifications),
        "salary min": str(analysis.salary_min or ""),
        "salary max": str(analysis.salary_max or ""),
        "salary text": analysis.salary_text,
        "seniority": analysis.seniority,
        "degree requirement": analysis.degree_requirement,
        "clearance requirement": analysis.clearance_requirement,
        "work mode": analysis.work_mode,
        "contact strength": str(analysis.contact_strength),
    }


def build_analytics_dashboard(scored_jobs: list[ScoredJob]) -> AnalyticsDashboard:
    rows = [(scored, analyze_job(scored)) for scored in scored_jobs]
    active = [
        (scored, analysis)
        for scored, analysis in rows
        if Classification.REJECTED_NOTABLE not in scored.labels
        and Classification.AUTO_REJECT not in scored.labels
        and Classification.EXPIRED not in scored.labels
    ]
    clean_active = [
        (scored, analysis)
        for scored, analysis in active
        if analysis.geography != "Needs cleanup" and analysis.role_family in TARGET_JOB_TYPES
    ]
    return AnalyticsDashboard(
        geography_role_demand=_geography_role_demand(clean_active),
        top_companies_by_geography=_top_companies_by_geography(clean_active),
        strongest_contacts=_strongest_contacts(clean_active),
        qualification_demand=_qualification_demand(clean_active),
        salary_by_role_family=_salary_by_role_family(clean_active),
        role_family_mix=_counter_rows(Counter(analysis.role_family for _, analysis in clean_active), total=len(clean_active)),
        seniority_mix=_counter_rows(Counter(analysis.seniority for _, analysis in clean_active), total=len(clean_active)),
        work_mode_mix=_counter_rows(Counter(analysis.work_mode for _, analysis in clean_active), total=len(clean_active)),
        degree_mix=_counter_rows(Counter(analysis.degree_requirement for _, analysis in clean_active), total=len(clean_active)),
        clearance_mix=_counter_rows(Counter(analysis.clearance_requirement for _, analysis in clean_active), total=len(clean_active)),
        score_bands=_score_bands(clean_active),
        geography_map=_geography_map(clean_active),
        city_markets=_city_markets(clean_active),
        job_signals={
            job_feedback_id(scored.job): JobSignal(
                company=_company_label(scored.job.company, scored.job.raw_text),
                geography=analysis.geography,
                role_family=analysis.role_family,
                qualifications=tuple(analysis.qualifications),
                seniority=analysis.seniority,
                work_mode=analysis.work_mode,
                degree_requirement=analysis.degree_requirement,
                clearance_requirement=analysis.clearance_requirement,
            )
            for scored, analysis in clean_active
        },
        cleanup_count=len(active) - len(clean_active),
    )


def _geography_role_demand(rows: list[tuple[ScoredJob, JobAnalysis]]) -> dict[str, list[DashboardRow]]:
    grouped: dict[str, Counter[str]] = defaultdict(Counter)
    totals: Counter[str] = Counter()
    for _, analysis in rows:
        grouped[analysis.geography][analysis.role_family] += 1
        totals[analysis.geography] += 1
    return {
        geography: _counter_rows(counter, total=totals[geography])
        for geography, counter in sorted(grouped.items(), key=lambda item: (-sum(item[1].values()), item[0]))
    }


def _top_companies_by_geography(rows: list[tuple[ScoredJob, JobAnalysis]]) -> dict[str, list[DashboardRow]]:
    grouped: dict[str, Counter[str]] = defaultdict(Counter)
    totals: Counter[str] = Counter()
    for scored, analysis in rows:
        company = _company_label(scored.job.company, scored.job.raw_text)
        if not company:
            continue
        grouped[analysis.geography][company] += 1
        totals[analysis.geography] += 1
    return {
        geography: _counter_rows(counter, total=totals[geography])
        for geography, counter in sorted(grouped.items(), key=lambda item: (-sum(item[1].values()), item[0]))
    }


def _strongest_contacts(rows: list[tuple[ScoredJob, JobAnalysis]]) -> list[DashboardRow]:
    contacts: Counter[str] = Counter()
    details: dict[str, set[str]] = defaultdict(set)
    for scored, analysis in rows:
        if scored.job.network_contacts:
            for contact in scored.job.network_contacts:
                label = contact.name
                if contact.company:
                    label = f"{contact.name} / {contact.company}"
                contacts[label] += max(1, analysis.contact_strength)
                details[label].add(scored.job.company)
        elif scored.job.network_summary:
            contacts[scored.job.network_summary] += 1
    total = max(sum(contacts.values()), 1)
    return [
        DashboardRow(label=label, count=count, share=round(count / total * 100), detail=", ".join(sorted(details[label])[:3]))
        for label, count in contacts.most_common(8)
    ]


def _qualification_demand(rows: list[tuple[ScoredJob, JobAnalysis]]) -> list[DashboardRow]:
    counter: Counter[str] = Counter()
    for _, analysis in rows:
        for qualification in analysis.qualifications:
            counter[qualification] += 1
    return _counter_rows(counter, total=len(rows))


def _salary_by_role_family(rows: list[tuple[ScoredJob, JobAnalysis]]) -> list[DashboardRow]:
    salary_points: dict[str, list[int]] = defaultdict(list)
    for _, analysis in rows:
        if analysis.salary_min and analysis.salary_max:
            salary_points[analysis.role_family].append(round((analysis.salary_min + analysis.salary_max) / 2))
        elif analysis.salary_min:
            salary_points[analysis.role_family].append(analysis.salary_min)
    values = []
    max_avg = 1
    for family, salaries in salary_points.items():
        avg = round(sum(salaries) / len(salaries))
        max_avg = max(max_avg, avg)
        values.append((family, avg, len(salaries)))
    return [
        DashboardRow(label=family, count=avg, share=round(avg / max_avg * 100), detail=f"{sample} postings")
        for family, avg, sample in sorted(values, key=lambda item: item[1], reverse=True)
    ]


def _score_bands(rows: list[tuple[ScoredJob, JobAnalysis]]) -> list[DashboardRow]:
    bands = [
        ("80+ priority", 80, 101),
        ("70-79 strong", 70, 80),
        ("60-69 promising", 60, 70),
        ("Under 60 monitor", 0, 60),
    ]
    total = len(rows)
    return [
        DashboardRow(
            label=label,
            count=sum(1 for scored, _ in rows if low <= scored.total_score < high),
            share=round(sum(1 for scored, _ in rows if low <= scored.total_score < high) / max(total, 1) * 100),
        )
        for label, low, high in bands
        if sum(1 for scored, _ in rows if low <= scored.total_score < high)
    ]


def _geography_map(rows: list[tuple[ScoredJob, JobAnalysis]]) -> list[GeoPoint]:
    counter = Counter(analysis.geography for _, analysis in rows)
    total = max(sum(counter.values()), 1)
    points = []
    for label, count in counter.most_common():
        if label not in GEO_POINT_COORDS:
            continue
        x, y = GEO_POINT_COORDS[label]
        points.append(GeoPoint(label=label, count=count, share=round(count / total * 100), x=x, y=y))
    return points


def _city_markets(rows: list[tuple[ScoredJob, JobAnalysis]]) -> list[CityMarket]:
    grouped: dict[str, list[ScoredJob]] = defaultdict(list)
    for scored, _ in rows:
        city = _city_bucket(scored.job.location)
        if city in CITY_POINT_COORDS:
            grouped[city].append(scored)
    markets: list[CityMarket] = []
    for city, jobs in grouped.items():
        x, y = CITY_POINT_COORDS[city]
        longitude, latitude = CITY_GEO_COORDS.get(city, (None, None))
        top_jobs = sorted(jobs, key=lambda scored: scored.total_score, reverse=True)[:5]
        markets.append(
            CityMarket(
                label=city,
                count=len(jobs),
                x=x,
                y=y,
                longitude=longitude,
                latitude=latitude,
                jobs=[
                    CityJob(
                        title=scored.job.title,
                        company=scored.job.company,
                        score=scored.total_score,
                        url=str(scored.job.url),
                    )
                    for scored in top_jobs
                ],
            )
        )
    return sorted(markets, key=lambda market: (-market.count, market.label))


def _counter_rows(counter: Counter[str], *, total: int, limit: int = 8) -> list[DashboardRow]:
    denominator = max(total, 1)
    return [
        DashboardRow(label=label, count=count, share=round(count / denominator * 100))
        for label, count in counter.most_common(limit)
    ]


def _job_text(scored: ScoredJob) -> str:
    job = scored.job
    return " ".join(
        [
            job.title,
            job.company,
            job.location,
            job.notes,
            job.fit_summary,
            job.requirements_summary,
            job.raw_text,
            " ".join(scored.rationale),
        ]
    ).lower()


def _geography(location: str) -> str:
    loc = location.lower()
    if _looks_polluted(location):
        return "Needs cleanup"
    if "austin" in loc:
        return "Austin"
    if "dallas" in loc or "fort worth" in loc or "dfw" in loc:
        return "Dallas-Fort Worth"
    if "remote" in loc:
        return "Remote"
    if "washington" in loc or re.search(r"\bd\.?c\.?\b", loc):
        return "Washington, DC"
    if "tx" in loc or "texas" in loc:
        return "Other US"
    if any(state in loc for state in ("ca", "co", "al", "ny", "va", "md", "fl", "ma", "california", "colorado")):
        return "Other US"
    if any(city in loc for city in ("london", "tokyo", "riyadh", "new delhi", "the hague", "abu dhabi", "melbourne", "munich")):
        return "International"
    return "Unknown"


def _city_bucket(location: str) -> str:
    loc = location.lower()
    if _looks_polluted(location):
        return "Needs cleanup"
    if "remote" in loc:
        return "Remote"
    if "austin" in loc:
        return "Austin"
    if "dallas" in loc or "fort worth" in loc or "dfw" in loc:
        return "Dallas-Fort Worth"
    if "washington" in loc or re.search(r"\bd\.?c\.?\b", loc):
        return "Washington, DC"
    if "san francisco" in loc or "bay area" in loc or "palo alto" in loc or "menlo park" in loc:
        return "San Francisco Bay Area"
    if "los angeles" in loc or "redondo beach" in loc or "el segundo" in loc or "mojave" in loc:
        return "Los Angeles"
    if "denver" in loc or "boulder" in loc or "westminster" in loc:
        return "Denver / Boulder"
    if "huntsville" in loc:
        return "Huntsville"
    if "san diego" in loc:
        return "San Diego"
    return "Other"


def _role_family(text: str) -> str:
    for family, keywords in ROLE_FAMILY_KEYWORDS.items():
        if any(keyword in text for keyword in keywords):
            return family
    return "Other Target Roles"


def _qualifications(text: str) -> list[str]:
    matches = [label for label, keywords in QUALIFICATION_KEYWORDS.items() if any(keyword in text for keyword in keywords)]
    if "degree" in text or "bachelor" in text or "master" in text:
        matches.append("Degree")
    if "clearance" in text:
        matches.append("Clearance")
    return matches[:6] or ["General business experience"]


def _salary(text: str) -> tuple[int | None, int | None, str]:
    matches = re.findall(r"\$?\s*(\d{2,3})(?:,\d{3})?\s*(k|000)?(?:\s*[-–]\s*\$?\s*(\d{2,3})(?:,\d{3})?\s*(k|000)?)?", text, re.I)
    candidates: list[tuple[int, int | None]] = []
    for low, low_suffix, high, high_suffix in matches:
        low_value = _salary_value(low, low_suffix)
        high_value = _salary_value(high, high_suffix or low_suffix) if high else None
        if low_value and 50_000 <= low_value <= 350_000:
            candidates.append((low_value, high_value if high_value and 50_000 <= high_value <= 400_000 else None))
    if not candidates:
        return None, None, ""
    low, high = candidates[0]
    salary_text = f"${low:,}"
    if high:
        salary_text = f"{salary_text}-${high:,}"
    return low, high, salary_text


def _salary_value(value: str, suffix: str) -> int | None:
    if not value:
        return None
    number = int(value)
    if suffix.lower() == "k" or number < 1000:
        return number * 1000
    return number


def _seniority(text: str) -> str:
    if re.search(r"\b(vp|vice president|director|head of)\b", text):
        return "Director+"
    if re.search(r"\b(principal|lead|senior|staff)\b", text):
        return "Senior / Lead"
    if re.search(r"\b(manager|associate|specialist)\b", text):
        return "Mid-level"
    if re.search(r"\b(entry|junior|intern|fellow)\b", text):
        return "Early"
    return "Unspecified"


def _degree_requirement(text: str) -> str:
    if re.search(r"\b(master'?s|mba|graduate degree)\b", text):
        return "Graduate degree mentioned"
    if re.search(r"\b(bachelor'?s|ba|bs|degree)\b", text):
        return "Bachelor's mentioned"
    return "No explicit degree found"


def _clearance_requirement(text: str) -> str:
    if re.search(r"\b(no|not)\s+(active\s+)?security clearance\s+(is\s+)?required\b", text):
        return "No clearance required"
    if "active security clearance" in text:
        return "Active clearance required"
    if "clearance" in text:
        return "Clearance mentioned"
    if "u.s. citizen" in text or "us citizen" in text:
        return "Citizenship mentioned"
    return "No clearance signal"


def _work_mode(location: str, text: str) -> str:
    haystack = f"{location} {text}".lower()
    if "remote" in haystack:
        return "Remote"
    if "hybrid" in haystack:
        return "Hybrid"
    if "on-site" in haystack or "onsite" in haystack:
        return "On-site"
    return "Unspecified"


def _contact_strength(scored: ScoredJob) -> int:
    if scored.job.network_contacts:
        return min(100, 30 + len(scored.job.network_contacts) * 20 + scored.total_score // 4)
    if scored.job.network_summary:
        return 25
    return 0


def _company_label(company: str, raw_text: str = "") -> str:
    value = company.strip()
    haystack = f"{company} {raw_text}".lower()
    if not value or _looks_polluted(value):
        return ""
    known = {
        "shieldai": "Shield AI",
        "shield ai": "Shield AI",
        "cesiumastro": "CesiumAstro",
        "cesium astro": "CesiumAstro",
        "impulse space": "Impulse Space",
        "fedtech": "FedTech",
    }
    key = re.sub(r"[^a-z0-9 ]+", "", value.lower()).strip()
    if key == "careers" and "impulse" in haystack:
        return "Impulse Space"
    return known.get(key, value)


def _looks_polluted(value: str) -> bool:
    normalized = value.strip().lower()
    if not normalized:
        return False
    return (
        "|" in normalized
        or "http://" in normalized
        or "https://" in normalized
        or len(normalized) > 80
        or bool(re.search(r"[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}", normalized))
    )
