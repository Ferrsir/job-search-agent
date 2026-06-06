from __future__ import annotations

import re

from job_search_agent.parsers.common import collapse_space


REQUIREMENT_HEADERS = (
    "requirements",
    "qualifications",
    "what you bring",
    "what you'll bring",
    "what you will bring",
    "you have",
    "you'll have",
    "minimum qualifications",
    "basic qualifications",
    "preferred qualifications",
    "about you",
)


def summarize_requirements(text: str, *, max_items: int = 3, max_chars: int = 260) -> str:
    cleaned = collapse_space(text)
    if not cleaned:
        return ""
    section = _requirement_section(cleaned) or cleaned
    candidates = _candidate_sentences(section)
    useful = [candidate for candidate in candidates if _looks_like_requirement(candidate)]
    if not useful:
        useful = candidates
    summary = "; ".join(useful[:max_items])
    return summary[:max_chars].rstrip(" ;,.") if summary else ""


def _requirement_section(text: str) -> str:
    lower = text.lower()
    starts = [lower.find(header) for header in REQUIREMENT_HEADERS if lower.find(header) != -1]
    if not starts:
        return ""
    start = min(starts)
    tail = text[start:]
    next_header = re.search(
        r"\b(benefits|compensation|about us|about the company|equal opportunity|application process|responsibilities)\b",
        tail[80:].lower(),
    )
    if next_header:
        return tail[: next_header.start() + 80]
    return tail


def _candidate_sentences(text: str) -> list[str]:
    pieces = re.split(r"(?:[.;]\s+|\s+-\s+|\s+•\s+|\s+\*\s+)", text)
    candidates = []
    for piece in pieces:
        cleaned = collapse_space(piece).strip(" :-")
        if 35 <= len(cleaned) <= 220:
            candidates.append(cleaned)
    return candidates


def _looks_like_requirement(text: str) -> bool:
    lower = text.lower()
    return any(
        signal in lower
        for signal in (
            "experience",
            "degree",
            "background",
            "ability",
            "able to",
            "familiarity",
            "knowledge",
            "proven",
            "years",
            "clearance",
            "citizen",
            "required",
            "preferred",
        )
    )
