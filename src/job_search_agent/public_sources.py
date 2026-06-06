from __future__ import annotations

import logging
import json
from datetime import date
from typing import Any
from urllib.parse import parse_qs, quote, urljoin, urlparse
from xml.etree import ElementTree

import requests
from bs4 import BeautifulSoup

from job_search_agent.models import JobRecord
from job_search_agent.parsers.common import collapse_space
from job_search_agent.requirements import summarize_requirements


LOGGER = logging.getLogger(__name__)

JOB_HINTS = (
    "job",
    "career",
    "opening",
    "role",
    "position",
    "greenhouse.io",
    "lever.co",
    "ashbyhq.com",
    "workdayjobs.com",
    "pinpointhq.com",
)

USER_AGENT = "job-search-agent/0.1"


def discover_public_jobs(
    source_urls: list[str],
    *,
    fetcher=requests.get,
    max_links_per_source: int = 25,
) -> list[JobRecord]:
    jobs: list[JobRecord] = []
    for source_url in source_urls:
        try:
            jobs.extend(_discover_from_source(source_url, fetcher, max_links_per_source))
        except requests.RequestException as exc:
            LOGGER.warning("Could not fetch public source %s: %s", source_url, exc)
    return jobs


def _discover_from_source(source_url: str, fetcher, max_links: int) -> list[JobRecord]:
    structured_jobs = _discover_from_structured_source(source_url, fetcher, max_links)
    if structured_jobs is not None:
        return structured_jobs

    response = fetcher(source_url, timeout=20, headers={"User-Agent": USER_AGENT})
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    json_ld_jobs = _jobs_from_json_ld(source_url, soup, max_links)
    if json_ld_jobs:
        return json_ld_jobs
    feed_jobs = _jobs_from_feed(source_url, response.text, max_links)
    if feed_jobs:
        return feed_jobs
    sitemap_jobs = _jobs_from_sitemap(source_url, response.text, max_links)
    if sitemap_jobs:
        return sitemap_jobs
    ats_links = _ats_links_from_page(source_url, soup, max_links)
    if ats_links:
        nested_jobs: list[JobRecord] = []
        for link in ats_links:
            try:
                nested_jobs.extend(_discover_from_source(link, fetcher, max_links - len(nested_jobs)))
            except requests.RequestException as exc:
                LOGGER.warning("Could not fetch nested public source %s: %s", link, exc)
            if len(nested_jobs) >= max_links:
                break
        if nested_jobs:
            return nested_jobs
    company = _company_name(source_url, soup)
    records: list[JobRecord] = []
    seen: set[str] = set()
    for link in soup.find_all("a", href=True):
        href = urljoin(source_url, link["href"])
        label = collapse_space(link.get_text(" "))
        haystack = f"{href} {label}".lower()
        if not label or not any(hint in haystack for hint in JOB_HINTS):
            continue
        if href in seen:
            continue
        seen.add(href)
        records.append(
            JobRecord(
                title=_title_from_label(label),
                company=company,
                location="Needs manual review",
                url=href,
                source="Public career page",
                source_email_id=f"public:{source_url}",
                source_alert_name=source_url,
                date_found=date.today(),
                notes="Public source discovery. Needs manual review.",
                fit_summary="Public posting surfaced from the source list; needs fit review.",
                raw_text=label,
            )
        )
        if len(records) >= max_links:
            break
    return records


def _jobs_from_json_ld(source_url: str, soup: BeautifulSoup, max_links: int) -> list[JobRecord]:
    records: list[JobRecord] = []
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        payload = _load_json(script.string or script.get_text())
        for item in _flatten_json_ld(payload):
            if _text(item.get("@type")).lower() != "jobposting":
                continue
            title = _text(item.get("title"))
            if not title:
                continue
            company = _text(_nested(item, "hiringOrganization", "name")) or _company_name(source_url, soup)
            location = _jobposting_location(item.get("jobLocation") or item.get("applicantLocationRequirements"))
            url = _text(item.get("url")) or source_url
            notes = _summary_from_fields(
                _text(item.get("employmentType")),
                _text(item.get("industry")),
                _text(item.get("datePosted")),
            )
            raw_text = _text(item.get("description") or item.get("responsibilities") or item.get("qualifications"))
            records.append(
                _record_from_structured_job(
                    title=title,
                    company=company,
                    location=location,
                    url=url,
                    source="Schema.org JobPosting",
                    source_url=source_url,
                    notes=notes or "Public page includes structured JobPosting metadata.",
                    raw_text=raw_text,
                )
            )
            if len(records) >= max_links:
                return records
    return records


def _jobs_from_feed(source_url: str, text: str, max_links: int) -> list[JobRecord]:
    stripped = text.lstrip()
    if not stripped.startswith("<") or not any(marker in stripped[:300].lower() for marker in ("<rss", "<feed", "<rdf")):
        return []
    try:
        root = ElementTree.fromstring(text)
    except ElementTree.ParseError:
        return []
    records: list[JobRecord] = []
    company = _feed_title(root) or urlparse(source_url).netloc
    for item in _feed_items(root):
        title = _xml_child_text(item, "title")
        link = _feed_link(item)
        summary = _xml_child_text(item, "description") or _xml_child_text(item, "summary")
        link_path = urlparse(link).path if link else ""
        haystack = f"{title} {link_path} {summary}".lower()
        if not title or not any(hint in haystack for hint in JOB_HINTS):
            continue
        records.append(
            _record_from_structured_job(
                title=title,
                company=company,
                location="Needs manual review",
                url=urljoin(source_url, link) if link else source_url,
                source="Public RSS/Atom feed",
                source_url=source_url,
                notes="Public feed item matched job-search terms; review fit details before prioritizing.",
                raw_text=summary,
            )
        )
        if len(records) >= max_links:
            break
    return records


def _jobs_from_sitemap(source_url: str, text: str, max_links: int) -> list[JobRecord]:
    stripped = text.lstrip()
    if not stripped.startswith("<") or "<urlset" not in stripped[:500].lower():
        return []
    try:
        root = ElementTree.fromstring(text)
    except ElementTree.ParseError:
        return []
    records: list[JobRecord] = []
    company = urlparse(source_url).netloc
    seen: set[str] = set()
    for url_node in _xml_children(root, "url"):
        loc = _xml_child_text(url_node, "loc")
        if not loc or loc in seen:
            continue
        haystack = loc.lower()
        if not any(hint in haystack for hint in JOB_HINTS):
            continue
        seen.add(loc)
        records.append(
            JobRecord(
                title=_title_from_url(loc),
                company=company,
                location="Needs manual review",
                url=loc,
                source="Public sitemap",
                source_email_id=f"public:{source_url}",
                source_alert_name=source_url,
                date_found=date.today(),
                notes="Public sitemap URL matched job-search terms; review fit details before prioritizing.",
                fit_summary="Public sitemap URL matched job-search terms; review fit details before prioritizing.",
                raw_text=loc,
            )
        )
        if len(records) >= max_links:
            break
    return records


def _ats_links_from_page(source_url: str, soup: BeautifulSoup, max_links: int) -> list[str]:
    links: list[str] = []
    seen: set[str] = set()
    for link in soup.find_all("a", href=True):
        href = urljoin(source_url, link["href"])
        host = urlparse(href).netloc.lower()
        if not any(
            domain in host
            for domain in ("boards.greenhouse.io", "jobs.lever.co", "jobs.ashbyhq.com", "pinpointhq.com")
        ):
            continue
        if href in seen:
            continue
        seen.add(href)
        links.append(href)
        if len(links) >= max_links:
            break
    return links


def _discover_from_structured_source(source_url: str, fetcher, max_links: int) -> list[JobRecord] | None:
    parsed = urlparse(source_url)
    host = parsed.netloc.lower()
    if token := _greenhouse_token(parsed):
        return _fetch_greenhouse_jobs(token, fetcher, max_links, source_url)
    if site := _lever_site(parsed):
        return _fetch_lever_jobs(site, fetcher, max_links, source_url)
    if board := _ashby_board(parsed):
        return _fetch_ashby_jobs(board, fetcher, max_links, source_url)
    if _is_pinpoint_posting(parsed):
        return [_fetch_pinpoint_posting(source_url, fetcher)]
    if "greenhouse" in host or "lever.co" in host or "ashbyhq.com" in host or "pinpointhq.com" in host:
        LOGGER.info("Could not infer ATS token from %s; falling back to HTML discovery", source_url)
    return None


def _fetch_greenhouse_jobs(token: str, fetcher, max_links: int, source_url: str) -> list[JobRecord]:
    api_url = f"https://boards-api.greenhouse.io/v1/boards/{quote(token)}/jobs?content=true"
    response = fetcher(api_url, timeout=20, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    response.raise_for_status()
    payload = response.json()
    jobs = payload.get("jobs", []) if isinstance(payload, dict) else []
    return [
        _record_from_structured_job(
            title=_text(job.get("title")),
            company=token,
            location=_text(_nested(job, "location", "name")),
            url=_text(job.get("absolute_url")),
            source="Greenhouse public board",
            source_url=source_url,
            notes=_summary_from_fields(
                _text(_nested(job, "departments", 0, "name")),
                _text(_nested(job, "offices", 0, "name")),
            ),
            raw_text=_text(job.get("content")),
        )
        for job in jobs[:max_links]
        if isinstance(job, dict)
    ]


def _fetch_lever_jobs(site: str, fetcher, max_links: int, source_url: str) -> list[JobRecord]:
    api_url = f"https://api.lever.co/v0/postings/{quote(site)}?mode=json"
    response = fetcher(api_url, timeout=20, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    response.raise_for_status()
    jobs = response.json()
    if not isinstance(jobs, list):
        return []
    return [
        _record_from_structured_job(
            title=_text(job.get("text")),
            company=site,
            location=_text(_nested(job, "categories", "location")),
            url=_text(job.get("hostedUrl") or job.get("applyUrl")),
            source="Lever public postings API",
            source_url=source_url,
            notes=_summary_from_fields(
                _text(_nested(job, "categories", "team")),
                _text(_nested(job, "categories", "department")),
                _text(job.get("workplaceType")),
            ),
            raw_text=_text(job.get("descriptionPlain") or job.get("description")),
        )
        for job in jobs[:max_links]
        if isinstance(job, dict)
    ]


def _fetch_ashby_jobs(board: str, fetcher, max_links: int, source_url: str) -> list[JobRecord]:
    api_url = f"https://api.ashbyhq.com/posting-api/job-board/{quote(board)}"
    response = fetcher(api_url, timeout=20, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    response.raise_for_status()
    payload = response.json()
    jobs = payload.get("jobs", []) if isinstance(payload, dict) else []
    return [
        _record_from_structured_job(
            title=_text(job.get("title")),
            company=board,
            location=_location_from_ashby(job.get("location")),
            url=_text(job.get("jobUrl") or job.get("applyUrl")),
            source="Ashby public job board API",
            source_url=source_url,
            notes=_summary_from_fields(
                _text(job.get("department")),
                _text(job.get("employmentType")),
                _text(job.get("team")),
            ),
            raw_text=_text(job.get("descriptionPlain") or job.get("descriptionHtml")),
        )
        for job in jobs[:max_links]
        if isinstance(job, dict)
    ]


def _fetch_pinpoint_posting(source_url: str, fetcher) -> JobRecord:
    response = fetcher(source_url, timeout=20, headers={"User-Agent": USER_AGENT})
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    details = _pinpoint_details(soup)
    company = _pinpoint_company(source_url, soup)
    title_node = soup.find("h1")
    title = _text(title_node.get_text(" ")) if title_node else _title_from_url(source_url)
    location = details.get("Location", "")
    notes = _summary_from_fields(
        details.get("Department", ""),
        details.get("Employment Type", ""),
        details.get("Workplace type", ""),
        details.get("Compensation", ""),
    )
    return _record_from_structured_job(
        title=title,
        company=company,
        location=location,
        url=source_url,
        source="Pinpoint public posting",
        source_url=source_url,
        notes=notes or "Public Pinpoint posting surfaced from a tracked careers page.",
        raw_text=soup.get_text(" "),
    )


def _record_from_structured_job(
    *,
    title: str,
    company: str,
    location: str,
    url: str,
    source: str,
    source_url: str,
    notes: str,
    raw_text: str,
) -> JobRecord:
    fit_hint = notes or "Structured public posting surfaced from a tracked ATS board; review fit details before prioritizing."
    return JobRecord(
        title=title or "Needs manual review",
        company=company,
        location=location or "Needs manual review",
        url=url,
        source=source,
        source_email_id=f"public:{source_url}",
        source_alert_name=source_url,
        date_found=date.today(),
        notes=fit_hint,
        fit_summary=fit_hint,
        requirements_summary=summarize_requirements(raw_text),
        raw_text=collapse_space(BeautifulSoup(raw_text, "html.parser").get_text(" ")) if raw_text else fit_hint,
    )


def _company_name(source_url: str, soup: BeautifulSoup) -> str:
    title = collapse_space(soup.title.get_text(" ")) if soup.title else ""
    if title:
        return title.split("|")[0].split("-")[0].strip()
    return source_url.split("//", 1)[-1].split("/", 1)[0]


def _title_from_label(label: str) -> str:
    cleaned = label.strip(" -|")
    if len(cleaned) > 120:
        return "Needs manual review"
    return cleaned or "Needs manual review"


def _title_from_url(url: str) -> str:
    parts = [part for part in urlparse(url).path.split("/") if part]
    slug = parts[-1] if parts else urlparse(url).netloc
    title = slug.rsplit(".", 1)[0].replace("-", " ").replace("_", " ")
    return collapse_space(title).title() or "Needs manual review"


def _greenhouse_token(parsed) -> str:
    host = parsed.netloc.lower()
    parts = [part for part in parsed.path.split("/") if part]
    if host in {"boards.greenhouse.io", "job-boards.greenhouse.io"} and parts:
        return parts[0]
    if host == "boards-api.greenhouse.io" and len(parts) >= 3 and parts[0] == "v1" and parts[1] == "boards":
        return parts[2]
    if "greenhouse.io" in host:
        query = parse_qs(parsed.query)
        for key in ("for", "b", "token"):
            if query.get(key):
                return query[key][0]
    return ""


def _lever_site(parsed) -> str:
    host = parsed.netloc.lower()
    parts = [part for part in parsed.path.split("/") if part]
    if host in {"jobs.lever.co", "api.lever.co"} and parts:
        if parts[0] == "v0" and len(parts) >= 3 and parts[1] == "postings":
            return parts[2]
        return parts[0]
    return ""


def _ashby_board(parsed) -> str:
    host = parsed.netloc.lower()
    parts = [part for part in parsed.path.split("/") if part]
    if host == "jobs.ashbyhq.com" and parts:
        return parts[0]
    if host == "api.ashbyhq.com" and len(parts) >= 3 and parts[0] == "posting-api" and parts[1] == "job-board":
        return parts[2]
    return ""


def _is_pinpoint_posting(parsed) -> bool:
    return parsed.netloc.lower().endswith("pinpointhq.com") and "/postings/" in parsed.path


def _pinpoint_company(source_url: str, soup: BeautifulSoup) -> str:
    title = collapse_space(soup.title.get_text(" ")) if soup.title else ""
    if "|" in title:
        parts = [part.strip() for part in title.split("|") if part.strip()]
        if len(parts) >= 2:
            return parts[1].replace("Careers", "").strip() or parts[1]
    host = urlparse(source_url).netloc
    return host.split(".", 1)[0]


def _pinpoint_details(soup: BeautifulSoup) -> dict[str, str]:
    labels = {"Department", "Employment Type", "Location", "Workplace type", "Compensation"}
    text_nodes = [collapse_space(node) for node in soup.get_text("\n").splitlines()]
    text_nodes = [node for node in text_nodes if node]
    details: dict[str, str] = {}
    for index, node in enumerate(text_nodes):
        if node in labels and index + 1 < len(text_nodes):
            value = text_nodes[index + 1]
            if value not in labels:
                details[node] = value
    return details


def _nested(value: Any, *keys: str | int) -> Any:
    current = value
    for key in keys:
        if isinstance(key, int):
            if not isinstance(current, list) or len(current) <= key:
                return ""
            current = current[key]
        elif isinstance(current, dict):
            current = current.get(key, "")
        else:
            return ""
    return current


def _location_from_ashby(value: Any) -> str:
    if isinstance(value, dict):
        return _text(value.get("name") or value.get("location"))
    return _text(value)


def _jobposting_location(value: Any) -> str:
    if isinstance(value, list):
        return " / ".join(filter(None, (_jobposting_location(item) for item in value)))
    if not isinstance(value, dict):
        return _text(value)
    address = value.get("address")
    if isinstance(address, dict):
        return ", ".join(
            item
            for item in [
                _text(address.get("addressLocality")),
                _text(address.get("addressRegion")),
                _text(address.get("addressCountry")),
            ]
            if item
        )
    return _text(value.get("name") or value.get("location"))


def _summary_from_fields(*fields: str) -> str:
    values = [field for field in fields if field]
    if not values:
        return ""
    return f"Structured public posting signals: {', '.join(values)}."


def _text(value: Any) -> str:
    if value is None:
        return ""
    return collapse_space(str(value))


def _load_json(text: str) -> Any:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _flatten_json_ld(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        flattened: list[dict[str, Any]] = []
        for item in value:
            flattened.extend(_flatten_json_ld(item))
        return flattened
    if not isinstance(value, dict):
        return []
    graph = value.get("@graph")
    if isinstance(graph, list):
        return [value, *_flatten_json_ld(graph)]
    return [value]


def _strip_namespace(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def _xml_children(node, name: str):
    return [child for child in list(node) if _strip_namespace(child.tag) == name.lower()]


def _xml_child_text(node, name: str) -> str:
    for child in list(node):
        if _strip_namespace(child.tag) == name.lower() and child.text:
            return collapse_space(child.text)
    return ""


def _feed_items(root) -> list:
    items = []
    for node in root.iter():
        if _strip_namespace(node.tag) in {"item", "entry"}:
            items.append(node)
    return items


def _feed_title(root) -> str:
    for node in root.iter():
        if _strip_namespace(node.tag) == "title" and node.text:
            return collapse_space(node.text)
    return ""


def _feed_link(item) -> str:
    direct = _xml_child_text(item, "link")
    if direct:
        return direct
    for child in list(item):
        if _strip_namespace(child.tag) == "link":
            href = child.attrib.get("href")
            if href:
                return href
    return ""
