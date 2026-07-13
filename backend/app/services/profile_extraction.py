from __future__ import annotations

import re
from dataclasses import dataclass, field

from .ontology import extract_skills, infer_domain, skill_domain


EXTRACTOR_VERSION = "profile-rules-v1.3.0"

SECTION_WORDS = {
    "profile",
    "summary",
    "education",
    "experience",
    "professional experience",
    "work experience",
    "research experience",
    "projects",
    "selected projects",
    "selected engineering projects",
    "technical skills",
    "skills",
    "languages",
    "tools",
    "awards",
    "achievements",
    "volunteering",
    "honors-awards",
    "hackathons",
}
LANGUAGES = ("arabic", "english", "hebrew", "french", "german", "spanish", "russian")
PROFICIENCY = ("native", "fluent", "professional", "working", "bilingual", "mother tongue")
ACTION_WORDS = ("built", "developed", "implemented", "created", "designed", "engineered", "delivered", "expanded")
ROLE_WORDS = (
    "tutor",
    "assistant",
    "secretary",
    "waitress",
    "mentor",
    "engineer",
    "developer",
    "intern",
    "manager",
    "analyst",
    "researcher",
    "consultant",
)
LOCATION_NAMES = (
    "be'er sheva",
    "beer sheva",
    "tel aviv",
    "jerusalem",
    "haifa",
    "nazareth",
    "nof hagalil",
    "baqa al-gharbya",
    "yokneam",
    "herzliya",
    "ramat gan",
    "israel",
    "remote",
    "hybrid",
)


@dataclass(frozen=True)
class ExtractedFact:
    fact_type: str
    value: str
    evidence: str
    confidence: float
    metadata: dict[str, object] = field(default_factory=dict)


def extract_profile_facts(source_type: str, text: str) -> list[ExtractedFact]:
    lines = _lines(text)
    if not lines:
        return []
    facts: list[ExtractedFact] = []
    declared_skill_evidence = _declared_skill_lines(lines)
    skill_evidence_lines = _skill_evidence_lines(lines)

    for skill in extract_skills(text):
        evidence = _best_skill_evidence(
            source_type,
            skill_evidence_lines,
            declared_skill_evidence,
            skill,
        )
        evidence_type = _skill_evidence_type(
            source_type,
            evidence,
            evidence in declared_skill_evidence,
        )
        facts.append(
            ExtractedFact(
                "skill",
                skill,
                evidence,
                _skill_confidence(source_type, evidence_type),
                {"evidence_type": evidence_type, "domain": skill_domain(skill)},
            )
        )

    for value, evidence in _projects(source_type, lines):
        facts.append(
            ExtractedFact(
                "project",
                value,
                evidence,
                0.82 if source_type in {"cv", "github"} else 0.7,
                {"evidence_type": "github_project" if source_type == "github" else "project"},
            )
        )

    for value, evidence in _experiences(lines):
        facts.append(ExtractedFact("experience", value, evidence, 0.76, {"evidence_type": "professional"}))

    for value, evidence in _education(lines):
        facts.append(ExtractedFact("education", value, evidence, 0.84, {"evidence_type": "education"}))

    semesters = _semesters_left(text)
    if semesters is not None:
        facts.append(
            ExtractedFact("semesters_left", str(semesters), evidence_for_term(lines, "semester"), 0.9)
        )

    location = _location(lines)
    if location:
        facts.append(ExtractedFact("location", location, evidence_for_term(lines, location.split(",")[0]), 0.72))

    availability = _availability(text)
    if availability:
        facts.append(ExtractedFact("availability", availability, evidence_for_term(lines, "available"), 0.76))

    authorization = _work_authorization(text)
    if authorization:
        facts.append(ExtractedFact("work_authorization", authorization, authorization, 0.76))

    for language, evidence in _languages(lines):
        facts.append(ExtractedFact("language", language, evidence, 0.78))

    skills = [fact.value for fact in facts if fact.fact_type == "skill"]
    if skills:
        facts.append(
            ExtractedFact(
                "domain",
                infer_domain(skills),
                ", ".join(skills[:8]),
                0.64,
                {"evidence_type": "inferred", "extractor_version": EXTRACTOR_VERSION},
            )
        )
    return _dedupe_facts(facts)


def fact_key(fact_type: str, value: str) -> str:
    if fact_type == "project":
        raw = value.lower().strip()
        repository = re.match(r"project\s+([^\s:|]+)", raw)
        if repository:
            raw = repository.group(1)
        else:
            raw = re.split(r"\s*[:|]\s*", raw, maxsplit=1)[0]
        raw = re.sub(r"\([^)]*\)", " ", raw)
        raw = re.sub(r"^the\s+", "", raw)
        normalized = re.sub(r"[^a-z0-9+#.]+", " ", raw).strip()
    elif fact_type == "experience":
        normalized = re.sub(r"[^a-z0-9+#.]+", " ", value.lower()).strip()
        normalized = re.sub(r"\b(?:19|20)\d{2}\b|\bpresent\b", "", normalized)
        normalized = " ".join(normalized.split()[:12])
    else:
        normalized = re.sub(r"[^a-z0-9+#.]+", " ", value.lower()).strip()
    return f"{fact_type}:{normalized}"


def extracted_fact_key(fact: ExtractedFact) -> str:
    if fact.fact_type != "experience":
        return fact_key(fact.fact_type, fact.value)
    role = _canonical_role(fact.value)
    date_key = _date_key(fact.evidence)
    return f"experience:{role}:{date_key}" if date_key else fact_key(fact.fact_type, fact.value)


def evidence_for_term(lines: list[str], term: str) -> str:
    pattern = _term_pattern(term)
    candidates = [line for line in lines if re.search(pattern, line, re.IGNORECASE)]
    if not candidates:
        return term
    # Prefer concise, local evidence rather than the first flattened page line.
    return min(candidates, key=lambda line: (len(line) > 280, len(line)))[:320]


def _best_skill_evidence(
    source_type: str,
    lines: list[str],
    declared_lines: set[str],
    skill: str,
) -> str:
    candidates = [line for line in lines if re.search(_term_pattern(skill), line, re.IGNORECASE)]
    if not candidates:
        return skill

    def rank(line: str) -> tuple[float, int, int]:
        evidence_type = _skill_evidence_type(source_type, line, line in declared_lines)
        return (
            _skill_confidence(source_type, evidence_type),
            0 if len(line) > 280 else 1,
            -len(line),
        )

    return max(candidates, key=rank)[:320]


def _skill_evidence_lines(lines: list[str]) -> list[str]:
    """Add reconstructed project bullets so skills on a wrapped line keep their context."""
    output = list(lines)
    in_projects = False
    for index, line in enumerate(lines):
        section = _section(line)
        if section:
            in_projects = section in {"projects", "selected projects", "selected engineering projects", "hackathons"}
            continue
        if not in_projects:
            continue
        if any(re.search(rf"\b{word}\b", line.lower()) for word in ACTION_WORDS):
            joined = _join_project_continuation(lines, index, line)
            if joined != line:
                output.append(joined)
    return output


def _lines(text: str) -> list[str]:
    return [re.sub(r"\s+", " ", line).strip(" \t•▪◦") for line in text.splitlines() if line.strip()]


def _is_heading(line: str) -> bool:
    normalized = re.sub(r"[^a-z -]", "", line.lower()).strip()
    if normalized in SECTION_WORDS:
        return True
    words = normalized.split()
    return bool(words and len(words) <= 5 and all(word in {item for section in SECTION_WORDS for item in section.split()} for word in words))


def _section(line: str) -> str | None:
    normalized = re.sub(r"[^a-z ]", " ", line.lower())
    normalized = re.sub(r"\s+", " ", normalized).strip()
    for name in sorted(SECTION_WORDS, key=len, reverse=True):
        if normalized == name or (len(normalized.split()) <= 6 and re.search(rf"\b{re.escape(name)}\b", normalized)):
            return name
    return None


def _projects(source_type: str, lines: list[str]) -> list[tuple[str, str]]:
    if source_type == "github":
        return [
            (line[:300], line[:320])
            for line in lines
            if re.match(r"^Project\s+\S+", line, re.IGNORECASE) and len(line) >= 18
        ][:15]

    output: list[tuple[str, str]] = []
    in_projects = False
    project_title = ""
    for index, line in enumerate(lines):
        section = _section(line)
        if section:
            in_projects = section in {"projects", "selected projects", "selected engineering projects", "hackathons"}
            project_title = ""
            continue
        lower = line.lower()
        has_action = any(re.search(rf"\b{word}\b", lower) for word in ACTION_WORDS)
        if in_projects and has_action:
            project_line = _join_project_continuation(lines, index, line)
            if output and project_line in output[-1][1]:
                # The preceding title/look-ahead pair already captured this
                # bullet; do not create a second action-only project.
                continue
            evidence = " ".join(part for part in (project_title, project_line) if part)[:320]
            value = f"{project_title}: {project_line}" if project_title else project_line
            output.append((value[:300], evidence))
            # Keep a real title for consecutive bullets so they reconcile to
            # one project key. Action-only entries remain independent.
            continue
        if has_action and "project" in lower and not any(phrase in lower for phrase in ("seeking", "collaborate", "experience in")):
            output.append((line[:300], line[:320]))
            continue
        has_title_separator = "|" in line
        if (not in_projects and not has_title_separator) or _is_heading(line) or len(line) > 150:
            continue
        if has_action or line.lower().startswith(("o ", "- ")):
            continue
        lookahead = lines[index + 1 : index + 5]
        action = next(
            (item for item in lookahead if any(re.search(rf"\b{word}\b", item.lower()) for word in ACTION_WORDS)),
            "",
        )
        if not action:
            if in_projects and _project_title_candidate(line):
                project_title = line.split("|", 1)[0].strip()
            continue
        title = line.split("|", 1)[0].strip()
        if title.lower() in {*LANGUAGES, *PROFICIENCY}:
            continue
        if "|" not in line and (
            len(title) > 70
            or len(extract_skills(title)) >= 2
            or title.endswith((".", ":"))
            or not title[:1].isupper()
            or sum(1 for word in title.split() if len(word) > 2 and word.isupper()) >= 2
        ):
            continue
        value = f"{title}: {action}" if title else action
        output.append((value[:300], " ".join([part for part in (title, action) if part])[:320]))
    return _dedupe_pairs(output)[:12]


def _join_project_continuation(lines: list[str], index: int, line: str) -> str:
    """Join PDF hard-wraps only when the current project line is visibly incomplete."""
    value = line
    for continuation in lines[index + 1 : index + 3]:
        if not re.search(r"(?:[,;:]|\b(?:and|or|with|using|including|for|to))$", value, re.IGNORECASE):
            break
        if _section(continuation) or _is_heading(continuation):
            break
        if any(re.search(rf"\b{word}\b", continuation.lower()) for word in ACTION_WORDS):
            break
        value = f"{value} {continuation}".strip()
    return value


def _project_title_candidate(line: str) -> bool:
    title = line.split("|", 1)[0].strip()
    return bool(
        2 <= len(title) <= 80
        and not _is_heading(title)
        and not title.endswith((".", ":"))
        and len(extract_skills(title)) < 2
        and title[:1].isupper()
    )


def _declared_skill_lines(lines: list[str]) -> set[str]:
    declared: set[str] = set()
    in_skills = False
    skill_sections = {"technical skills", "skills", "tools"}
    for line in lines:
        section = _section(line)
        if section:
            in_skills = section in skill_sections
            if in_skills and extract_skills(line):
                declared.add(line)
            continue
        if in_skills and extract_skills(line):
            declared.add(line)
    return declared


def _experiences(lines: list[str]) -> list[tuple[str, str]]:
    output: list[tuple[str, str]] = []
    in_experience = False
    for index, line in enumerate(lines):
        section = _section(line)
        if section:
            in_experience = section in {"experience", "professional experience", "work experience", "research experience"}
            continue
        lower = line.lower()
        if not any(re.search(rf"\b{word}\b", lower) for word in ROLE_WORDS):
            continue
        if len(line) > 180 or any(
            phrase in lower
            for phrase in (
                " with experience",
                "supporting students",
                "guided ",
                "tutored ",
                "mentored ",
                "experienced ",
                "i was ",
            )
        ):
            continue
        date_here = bool(re.search(r"\b(?:19|20)\d{2}\b|\bpresent\b", lower))
        nearby = lines[max(0, index - 1) : index + 2]
        date_line = next(
            (item for item in nearby if re.search(r"\b(?:19|20)\d{2}\b|\bpresent\b", item.lower())),
            "",
        )
        if not date_line:
            date_line = next((item for item in nearby if re.search(r"\b\d+\s+months?\b", item.lower())), "")
        if not (in_experience or date_here or date_line):
            continue
        value = _role_value(line)
        evidence = " ".join((line, date_line if date_line != line else "")).strip()
        if 4 <= len(value) <= 220:
            output.append((value[:220], evidence[:320]))
    return _dedupe_pairs(output)[:12]


def _education(lines: list[str]) -> list[tuple[str, str]]:
    output: list[tuple[str, str]] = []
    degree_patterns = (
        (r"\b(?:m\.?\s*sc\.?|master(?:'s)?(?: degree)?)\b", "M.Sc."),
        (r"\b(?:b\.?\s*sc\.?|bachelor of science|bachelor of applied science|basc)\b", "B.Sc."),
        (r"\b(?:b\.?\s*a\.?|bachelor of arts)\b", "B.A."),
    )
    fields = (
        ("management information systems", "Management Information Systems"),
        ("computer science", "Computer Science"),
        ("software engineering", "Software Engineering"),
        ("computer engineering", "Computer Engineering"),
        ("electrical engineering", "Electrical Engineering"),
        ("information systems", "Information Systems"),
        ("artificial intelligence", "Artificial Intelligence"),
        ("computational science", "Computational Science"),
    )
    for index, line in enumerate(lines):
        context = " ".join(lines[max(0, index - 1) : index + 2])
        lower = context.lower()
        degree = next((label for pattern, label in degree_patterns if re.search(pattern, lower)), "")
        field = next((label for token, label in fields if token in lower), "")
        if degree and field:
            output.append((f"{degree} in {field}", context[:320]))
    return _dedupe_pairs(output)


def _languages(lines: list[str]) -> list[tuple[str, str]]:
    output: list[tuple[str, str]] = []
    in_languages = False
    for index, line in enumerate(lines):
        section = _section(line)
        if section:
            in_languages = section == "languages"
            # Layout extraction often puts the first language on the same line
            # as the section heading (for example, "LANGUAGES Arabic Native").
            if not any(language in line.lower() for language in LANGUAGES):
                continue
        lower = line.lower()
        nearby = " ".join(lines[index : index + 3]).lower()
        standalone_with_level = lower in LANGUAGES and any(level in nearby for level in PROFICIENCY)
        explicit = any(level in lower for level in PROFICIENCY) or lower.startswith("fluent in ") or standalone_with_level
        if not (in_languages or explicit):
            continue
        for language in LANGUAGES:
            if re.search(_term_pattern(language), line, re.IGNORECASE):
                output.append((language, line[:320]))
    return _dedupe_pairs(output)


def _location(lines: list[str]) -> str:
    for line in lines[:18]:
        lower = line.lower()
        hits = [name for name in LOCATION_NAMES if re.search(_term_pattern(name), lower, re.IGNORECASE)]
        if hits:
            city = next((name for name in hits if name not in {"israel", "remote", "hybrid"}), "")
            if city:
                display_city = city.title().replace("Beer", "Be'er").replace("Be'Er", "Be'er")
                return f"{display_city}, Israel" if "israel" in lower else display_city
            return hits[0].title()
    return ""


def _semesters_left(text: str) -> int | None:
    patterns = (
        r"\b(\d+)\s+semesters?\s+(?:remaining|left|to go)\b",
        r"\b(?:remaining|left)\s*[:\-]?\s*(\d+)\s+semesters?\b",
    )
    values = [int(value) for pattern in patterns for value in re.findall(pattern, text.lower())]
    return min(values) if values else None


def _availability(text: str) -> str:
    lower = text.lower()
    for pattern, value in (
        (r"available\s+(?:to\s+)?start\s+immediately|immediate availability", "Available immediately"),
        (r"available\s+full[- ]time|full[- ]time availability", "Available full-time"),
        (r"available\s+part[- ]time|part[- ]time availability", "Available part-time"),
        (r"available\s+(\d+(?:\s*[-–]\s*\d+)?)\s+(?:days|hours)\s+(?:a|per)\s+week", ""),
    ):
        match = re.search(pattern, lower)
        if match:
            return value or match.group(0).capitalize()
    return ""


def _work_authorization(text: str) -> str:
    lower = text.lower()
    if "authorized to work in israel" in lower or "israeli citizen" in lower:
        return "Authorized to work in Israel"
    if "requires sponsorship" in lower or "need sponsorship" in lower:
        return "Requires work sponsorship"
    return ""


def _skill_evidence_type(source_type: str, evidence: str, declared: bool = False) -> str:
    lower = evidence.lower()
    if source_type == "manual":
        return "self_reported"
    if source_type == "github":
        return "github_project"
    if any(re.search(rf"\b{word}\b", lower) for word in ACTION_WORDS):
        return "project"
    if any(word in lower for word in ("course", "coursework", "studied", "university")):
        return "coursework"
    if source_type.startswith("linkedin") and any(word in lower for word in ROLE_WORDS):
        return "professional"
    if declared:
        return "declared_skill"
    return "cv_mention"


def _role_value(line: str) -> str:
    value = re.sub(
        r"^\s*(?:\d{1,2}[./])?(?:19|20)\d{2}\s*(?:[-–—]\s*(?:present|(?:\d{1,2}[./])?(?:19|20)\d{2}))?\s*[:|-]?\s*",
        "",
        line,
        flags=re.IGNORECASE,
    ).strip()
    patterns = (
        r"Private Python Tutor",
        r"Private Tutor(?:\s*[—–-].*)?",
        r"University Tutor(?:\s*[—–-].*)?",
        r"Computer Science Tutor(?:\s*[—–-].*)?",
        r"Teaching Assistant(?:\s*[—–-].*)?",
        r"Administrative Assistant(?:\s*[—–-].*)?",
        r"Education Mentor(?:\s*[—–-].*)?",
        r"Secretary(?:\s+in\s+.*)?",
        r"Waitress(?:\s+at\s+.*)?",
        r"Mentor(?:\s*[—–-].*)?",
    )
    for pattern in patterns:
        match = re.search(pattern, value, re.IGNORECASE)
        if match:
            return match.group(0).strip()
    return value


def _canonical_role(value: str) -> str:
    lower = value.lower()
    if "assistant" in lower:
        return "assistant"
    if "tutor" in lower:
        return "tutor"
    if "mentor" in lower:
        return "mentor"
    if "secretary" in lower:
        return "secretary"
    if "waitress" in lower:
        return "waitress"
    return re.sub(r"[^a-z0-9]+", " ", lower).strip()


def _date_key(evidence: str) -> str:
    years = re.findall(r"\b(?:19|20)\d{2}\b", evidence.lower())
    present = bool(re.search(r"\bpresent\b", evidence.lower()))
    if not years:
        return ""
    start = years[0]
    end = "present" if present else years[-1]
    return f"{start}-{end}"


def _skill_confidence(source_type: str, evidence_type: str) -> float:
    if evidence_type == "professional":
        return 0.9
    if evidence_type in {"project", "github_project"}:
        return 0.82
    if evidence_type == "coursework":
        return 0.68
    if evidence_type == "declared_skill":
        return 0.76
    if source_type == "manual":
        return 0.56
    return 0.66


def _term_pattern(term: str) -> str:
    escaped = re.escape(term).replace(r"\ ", r"\s+")
    return rf"(?<![a-z0-9]){escaped}(?![a-z0-9])"


def _dedupe_pairs(values: list[tuple[str, str]]) -> list[tuple[str, str]]:
    output: list[tuple[str, str]] = []
    seen: set[str] = set()
    for value, evidence in values:
        key = re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()
        if key and key not in seen:
            seen.add(key)
            output.append((value, evidence))
    return output


def _dedupe_facts(facts: list[ExtractedFact]) -> list[ExtractedFact]:
    output: list[ExtractedFact] = []
    seen: set[str] = set()
    for fact in facts:
        key = fact_key(fact.fact_type, fact.value)
        if key not in seen:
            seen.add(key)
            output.append(fact)
    return output
