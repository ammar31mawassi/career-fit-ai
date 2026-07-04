from __future__ import annotations

import html
import ipaddress
import json
import re
import socket
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, field, replace
from html.parser import HTMLParser

from .ontology import ONTOLOGY_VERSION, extract_skills, infer_domain, skill_domain
from .text import clean_text


USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"
)

JOB_READER_VERSION = "reader-v2.0.0"

CAREER_HINTS = ("career", "careers", "job", "jobs", "position", "greenhouse", "lever", "workday", "comeet", "workable")
MUST_HINTS = ("must", "required", "requirements", "qualification", "you have", "minimum", "mandatory")
PREFERRED_HINTS = ("preferred", "advantage", "a plus", "bonus", "ideally")
NICE_HINTS = ("nice to have", "nice-to-have", "optional")


@dataclass(frozen=True)
class RequirementGroup:
    priority: str
    mode: str
    skills: list[str]
    evidence: str


@dataclass(frozen=True)
class JobRequirements:
    must_have_skills: list[str]
    preferred_skills: list[str]
    nice_to_have_skills: list[str]
    all_skills: list[str]
    min_years_experience: float
    seniority: str
    education: str
    work_mode: str
    domain: str
    summary: str
    languages: list[str]
    location_requirement: str
    work_authorization: str
    availability: str
    responsibilities: list[str]
    evidence_by_requirement: dict[str, str]
    ontology_version: str = ONTOLOGY_VERSION
    skill_groups: list[RequirementGroup] = field(default_factory=list)
    experience_requirement_known: bool = False
    reader_version: str = JOB_READER_VERSION
    extraction_completeness: float = 0.0

    def to_json(self) -> str:
        return json.dumps(asdict(self), sort_keys=True)


@dataclass(frozen=True)
class ExtractedJob:
    source_url: str
    company: str
    role: str
    location: str
    description_text: str
    source_title: str
    source_confidence: float
    application_link: str
    requirements: JobRequirements


def extract_job_from_input(
    source_url: str,
    company: str,
    role: str,
    description_text: str,
) -> ExtractedJob:
    source_url = source_url.strip()
    company = company.strip()
    role = role.strip()
    pasted_text = _normalize_job_text(description_text)
    if source_url:
        validate_public_job_url(source_url)
    if pasted_text:
        title = role or "Pasted job description"
        text = pasted_text
        guessed_company = company or _company_from_url(source_url)
        guessed_role = role or _role_from_text(text) or _role_from_title(title)
        method = "pasted"
        confidence = _source_confidence(guessed_company, guessed_role, source_url, title, text, method)
        application_link = source_url
        location = _guess_location(text)
    else:
        html_text = _fetch(source_url)
        source = _structured_source(source_url, html_text)
        parser = _JobHtmlParser(source_url)
        parser.feed(html_text)
        if source is None:
            scoped_parts = parser.main_text_parts if len(" ".join(parser.main_text_parts)) >= 180 else parser.text_parts
            text = _normalize_job_text("\n".join(scoped_parts))[:20000]
            meta_text = _normalize_job_text(
                parser.meta.get("og:description") or parser.meta.get("description") or ""
            )
            if len(meta_text) >= 500 and _looks_like_page_failure(text):
                text = meta_text[:20000]
                method = "meta_description"
            else:
                method = "scoped_html"
            title = _extract_title(html_text) or parser.title or role
            guessed_company = (
                company
                or _company_from_metadata(parser.meta, title, source_url)
                or _company_from_url(source_url)
            )
            guessed_role = (
                role
                or _role_from_metadata(parser.meta, title, source_url)
                or _role_from_text(text)
                or _role_from_title(title)
            )
            location = _guess_location(text)
            application_link = _find_application_link(parser.links, source_url)
        else:
            text = _normalize_job_text(source["description"])[:20000]
            title = source["title"] or _extract_title(html_text) or parser.title or role
            guessed_company = company or source["company"] or _company_from_url(source_url)
            guessed_role = role or source["title"] or _role_from_title(title)
            location = source["location"] or _guess_location(text)
            application_link = source["application_link"] or _find_application_link(parser.links, source_url)
            method = source["method"]
        text = _trim_provider_noise(text, source_url)
        confidence = _source_confidence(
            guessed_company, guessed_role, source_url, title, text, method
        )
        _validate_job_content(guessed_role, text, confidence)

    requirements = classify_requirements(text, guessed_role)
    requirements = replace(
        requirements,
        reader_version=JOB_READER_VERSION,
        extraction_completeness=_requirement_completeness(requirements, text),
    )
    return ExtractedJob(
        source_url=source_url,
        company=guessed_company,
        role=guessed_role,
        location=location,
        description_text=text[:20000],
        source_title=title[:220],
        source_confidence=confidence,
        application_link=application_link,
        requirements=requirements,
    )


def classify_requirements(text: str, role: str = "") -> JobRequirements:
    lower = text.lower()
    segments = _requirement_segments(text)
    sentences = [segment for _, segment in segments]
    must_sentences = [segment for priority, segment in segments if priority == "must"]
    preferred_sentences = [segment for priority, segment in segments if priority == "preferred"]
    nice_sentences = [segment for priority, segment in segments if priority == "nice"]
    responsibility_sentences = [segment for priority, segment in segments if priority == "responsibility"]

    all_skills = extract_skills(text)
    groups = _skill_groups(segments)
    grouped = {skill for group in groups for skill in group.skills}
    raw_must = [skill for skill in _skills_from_sentences(must_sentences) if skill not in grouped]
    soft_must = [skill for skill in raw_must if skill_domain(skill) == "professional"]
    must_have = [skill for skill in raw_must if skill_domain(skill) != "professional"]
    preferred = [
        skill
        for skill in [*_skills_from_sentences(preferred_sentences), *soft_must]
        if skill not in must_have and skill not in grouped
    ]
    nice = [
        skill
        for skill in _skills_from_sentences(nice_sentences)
        if skill not in must_have and skill not in preferred and skill not in grouped
    ]
    inferred = [
        skill
        for skill in _skills_from_sentences(responsibility_sentences)
        if skill not in must_have and skill not in preferred and skill not in nice and skill not in grouped
    ]
    preferred = _dedupe([*preferred, *inferred])
    nice = _dedupe(
        [
            *nice,
            *[
                skill
                for skill in all_skills
                if skill not in must_have and skill not in preferred and skill not in grouped
            ],
        ]
    )
    min_years, experience_known = _experience_requirement(lower)

    return JobRequirements(
        must_have_skills=must_have,
        preferred_skills=preferred,
        nice_to_have_skills=nice,
        all_skills=all_skills,
        min_years_experience=min_years,
        seniority=_seniority(role, lower, min_years),
        education=_education(lower),
        work_mode=_work_mode(lower),
        domain=_domain(f"{role.lower()} {lower}", all_skills),
        summary=_summary(sentences),
        languages=_languages(lower),
        location_requirement=_guess_location(text),
        work_authorization=_work_authorization(lower),
        availability=_availability(lower),
        responsibilities=responsibility_sentences[:6],
        evidence_by_requirement=_requirement_evidence(segments),
        skill_groups=groups,
        experience_requirement_known=experience_known,
        extraction_completeness=0.0,
    )


def requirements_from_json(value: str) -> JobRequirements:
    if not value:
        return JobRequirements([], [], [], [], 0.0, "unspecified", "", "", "", "", [], "", "", "", [], {})
    payload = json.loads(value)
    groups = [
        RequirementGroup(
            priority=str(item.get("priority") or "must"),
            mode=str(item.get("mode") or "one_of"),
            skills=[str(skill) for skill in item.get("skills") or []],
            evidence=str(item.get("evidence") or ""),
        )
        for item in payload.get("skill_groups") or []
        if isinstance(item, dict)
    ]
    return JobRequirements(
        must_have_skills=list(payload.get("must_have_skills") or []),
        preferred_skills=list(payload.get("preferred_skills") or []),
        nice_to_have_skills=list(payload.get("nice_to_have_skills") or []),
        all_skills=list(payload.get("all_skills") or []),
        min_years_experience=float(payload.get("min_years_experience") or 0.0),
        seniority=str(payload.get("seniority") or "unspecified"),
        education=str(payload.get("education") or ""),
        work_mode=str(payload.get("work_mode") or ""),
        domain=str(payload.get("domain") or ""),
        summary=str(payload.get("summary") or ""),
        languages=list(payload.get("languages") or []),
        location_requirement=str(payload.get("location_requirement") or ""),
        work_authorization=str(payload.get("work_authorization") or ""),
        availability=str(payload.get("availability") or ""),
        responsibilities=list(payload.get("responsibilities") or []),
        evidence_by_requirement=dict(payload.get("evidence_by_requirement") or {}),
        ontology_version=str(payload.get("ontology_version") or ONTOLOGY_VERSION),
        skill_groups=groups,
        experience_requirement_known=bool(payload.get("experience_requirement_known", False)),
        reader_version=str(payload.get("reader_version") or ""),
        extraction_completeness=float(payload.get("extraction_completeness") or 0.0),
    )


def validate_public_job_url(url: str) -> None:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("Only HTTP and HTTPS job URLs are supported.")
    if not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("The job URL must contain a valid public hostname.")
    hostname = parsed.hostname.rstrip(".").lower()
    if hostname == "localhost" or hostname.endswith(".localhost"):
        raise ValueError("Local job URLs are not allowed.")
    if parsed.port not in {None, 80, 443}:
        raise ValueError("Job URLs may only use standard HTTP or HTTPS ports.")
    try:
        addresses = socket.getaddrinfo(hostname, parsed.port or 443, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise urllib.error.URLError(f"Could not resolve job URL hostname: {hostname}") from exc
    for address in addresses:
        ip = ipaddress.ip_address(address[4][0].split("%", 1)[0])
        if not ip.is_global:
            raise ValueError("Job URLs must not resolve to private or local network addresses.")


class _PublicOnlyRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validate_public_job_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _fetch(url: str) -> str:
    validate_public_job_url(url)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    opener = urllib.request.build_opener(_PublicOnlyRedirectHandler())
    with opener.open(request, timeout=15) as response:
        content_type = response.headers.get("content-type", "")
        if "text" not in content_type and "html" not in content_type and "xml" not in content_type:
            raise ValueError(f"Unsupported content type: {content_type}")
        return response.read(2_000_000).decode("utf-8", errors="ignore")


def _fetch_json(url: str) -> dict:
    validate_public_job_url(url)
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        },
    )
    opener = urllib.request.build_opener(_PublicOnlyRedirectHandler())
    with opener.open(request, timeout=15) as response:
        content_type = response.headers.get("content-type", "")
        if "json" not in content_type:
            raise ValueError(f"Unsupported ATS content type: {content_type}")
        payload = json.loads(response.read(2_000_000).decode("utf-8", errors="ignore"))
    return payload if isinstance(payload, dict) else {}


def _structured_source(url: str, html_text: str) -> dict[str, str] | None:
    workday = _workday_source(url)
    if workday:
        return workday
    job_posting = _json_ld_job_posting(html_text)
    if not job_posting:
        return None
    description = str(job_posting.get("description") or "")
    title = clean_text(str(job_posting.get("title") or ""))
    organization = job_posting.get("hiringOrganization") or {}
    company = clean_text(str(organization.get("name") or "")) if isinstance(organization, dict) else ""
    return {
        "title": title,
        "company": company,
        "location": _json_ld_location(job_posting),
        "description": _html_fragment_text(description),
        "application_link": str(job_posting.get("url") or url),
        "method": "json_ld",
    }


def _workday_source(url: str) -> dict[str, str] | None:
    parsed = urllib.parse.urlparse(url)
    host = (parsed.hostname or "").lower()
    match = re.match(r"^(?P<tenant>[a-z0-9-]+)\.wd\d+\.myworkdayjobs\.com$", host)
    if not match:
        return None
    parts = [urllib.parse.unquote(part) for part in parsed.path.split("/") if part]
    try:
        job_index = next(index for index, part in enumerate(parts) if part.lower() == "job")
    except StopIteration:
        return None
    if job_index < 1 or job_index + 1 >= len(parts):
        return None
    site = parts[job_index - 1]
    job_path = "/".join(parts[job_index + 1 :])
    tenant = match.group("tenant")
    api_url = (
        f"https://{host}/wday/cxs/{urllib.parse.quote(tenant)}/"
        f"{urllib.parse.quote(site)}/job/"
        + "/".join(urllib.parse.quote(part) for part in job_path.split("/"))
    )
    try:
        payload = _fetch_json(api_url)
    except Exception:
        return None
    info = payload.get("jobPostingInfo")
    if not isinstance(info, dict):
        return None
    company = tenant.upper() if len(tenant) <= 4 else tenant.replace("-", " ").title()
    return {
        "title": clean_text(str(info.get("title") or "")),
        "company": company,
        "location": clean_text(str(info.get("location") or info.get("jobRequisitionLocation") or "")),
        "description": _html_fragment_text(str(info.get("jobDescription") or "")),
        "application_link": str(info.get("externalUrl") or url),
        "method": "workday_api",
    }


def _json_ld_job_posting(html_text: str) -> dict | None:
    parser = _JsonLdParser()
    parser.feed(html_text)
    for raw in parser.blocks:
        try:
            payload = json.loads(html.unescape(raw))
        except (json.JSONDecodeError, TypeError):
            continue
        for item in _walk_json(payload):
            item_type = item.get("@type")
            types = item_type if isinstance(item_type, list) else [item_type]
            if any(str(value).lower() == "jobposting" for value in types):
                return item
    return None


def _walk_json(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk_json(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_json(child)


def _json_ld_location(posting: dict) -> str:
    values: list[str] = []
    locations = posting.get("jobLocation") or []
    if isinstance(locations, dict):
        locations = [locations]
    for location in locations if isinstance(locations, list) else []:
        if not isinstance(location, dict):
            continue
        address = location.get("address") or {}
        if not isinstance(address, dict):
            continue
        values.extend(
            str(address.get(key) or "")
            for key in ("addressLocality", "addressRegion", "addressCountry")
        )
    if str(posting.get("jobLocationType") or "").upper() == "TELECOMMUTE":
        values.append("Remote")
    return ", ".join(_dedupe([clean_text(value) for value in values if value])) or "Not specified"


def _html_fragment_text(value: str) -> str:
    parser = _FragmentTextParser()
    parser.feed(value)
    return _normalize_job_text("\n".join(parser.parts))


def _normalize_job_text(value: str) -> str:
    value = html.unescape(value).replace("\u00a0", " ")
    value = re.sub(r"(?i)<br\s*/?>|</(?:p|div|li|h[1-6])>", "\n", value)
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"[•●▪◦]", "\n• ", value)
    lines = [re.sub(r"[ \t]+", " ", line).strip(" \t") for line in value.splitlines()]
    output: list[str] = []
    for line in lines:
        if line and (not output or line != output[-1]):
            output.append(line)
    return "\n".join(output).strip()


def _validate_job_content(role: str, text: str, confidence: float) -> None:
    normalized_role = role.strip().lower()
    if normalized_role in {
        "",
        "unknown role",
        "pasted job description",
        "back to jobs",
        "an error occured. please try again",
        "an error occurred. please try again",
    } or normalized_role.startswith("object(stdclass)"):
        raise ValueError(
            "Could not identify the job title from this page. Add the title or paste the description."
        )
    lower = text.lower()
    meaningful = len(text) >= 180 and any(
        hint in lower
        for hint in (
            "experience",
            "qualification",
            "requirement",
            "responsibilit",
            "what you",
            "about the role",
            "job description",
        )
    )
    if not meaningful or confidence < 0.5:
        raise ValueError(
            "Could not extract a complete job posting from this URL. Paste the description and submit again."
        )


def _looks_like_page_failure(text: str) -> bool:
    preview = text[:500].lower()
    return any(
        phrase in preview
        for phrase in (
            "an error occured",
            "an error occurred",
            "please try again",
            "currently no open positions",
            "{{ position.",
            "object(stdclass)",
        )
    )


def _requirement_completeness(requirements: JobRequirements, text: str) -> float:
    checks = [
        bool(requirements.all_skills or requirements.skill_groups),
        bool(requirements.summary and "Could not extract" not in requirements.summary),
        bool(requirements.evidence_by_requirement),
        bool(requirements.responsibilities),
        requirements.experience_requirement_known,
        bool(requirements.education),
        len(text) >= 500,
    ]
    return round(sum(checks) / len(checks), 3)


def _requirement_segments(text: str) -> list[tuple[str, str]]:
    text = re.sub(
        r"\s+[\u2013\u2014-]\s*(must|required|mandatory|advantage|preferred)\b",
        lambda match: f" {match.group(0).strip()}.\n",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"(?i)\b(requirements?|qualifications?|preferred(?: qualifications?)?|nice[- ]to[- ]have|responsibilities)\s*:?",
        r"\n\1:",
        text,
    )
    expanded = re.sub(
        r"(?i)(?<!^)\b(requirements?|qualifications?|preferred|nice[- ]to[- ]have|responsibilities|what you(?:'|’)ll do)\s*:",
        r"\n\1:",
        text,
    )
    raw_parts = re.split(r"\n+|[•*]|(?<=[.!?;])\s+", expanded)
    # Use the compound-heading normalization above as the source of truth.
    # The legacy pass splits “Preferred qualifications” into two headings.
    raw_parts = re.split(r"\n+|[•*]|(?<=[.!?;])\s+", text)
    current = "unspecified"
    segments: list[tuple[str, str]] = []
    for raw in raw_parts:
        segment = clean_text(raw)
        if not segment:
            continue
        lower = segment.lower()
        if re.match(r"^(requirements?|qualifications?)\s*:", lower):
            current = "must"
        elif re.match(r"^preferred(?: qualifications?)?\s*:", lower):
            current = "preferred"
        elif re.match(r"^nice[- ]to[- ]have\s*:", lower):
            current = "nice"
        elif re.match(r"^(responsibilities|what you(?:'|’)ll do)\s*:", lower):
            current = "responsibility"

        priority = current
        if any(hint in lower for hint in NICE_HINTS):
            priority = "nice"
        elif any(hint in lower for hint in PREFERRED_HINTS):
            priority = "preferred"
        elif any(hint in lower for hint in MUST_HINTS):
            priority = "must"
        segments.append((priority, segment))
    return segments


def _skill_groups(segments: list[tuple[str, str]]) -> list[RequirementGroup]:
    groups: list[RequirementGroup] = []
    seen: set[tuple[str, str, tuple[str, ...]]] = set()
    for priority, segment in segments:
        if priority not in {"must", "preferred", "nice"}:
            continue
        skills = extract_skills(segment)
        if len(skills) < 2 or not _is_alternative_requirement(segment):
            continue
        key = (priority, "one_of", tuple(sorted(skills)))
        if key in seen:
            continue
        seen.add(key)
        groups.append(
            RequirementGroup(
                priority=priority,
                mode="one_of",
                skills=skills,
                evidence=segment[:500],
            )
        )
    return groups


def _is_alternative_requirement(segment: str) -> bool:
    lower = segment.lower()
    return any(
        re.search(pattern, lower)
        for pattern in (
            r"\bone\s+or\s+more\b",
            r"\bone\s+of\b",
            r"\bany\s+of\b",
            r"\bsuch\s+as\b",
            r"\be\.g\.\s*,?",
            r"\bfor\s+example\b",
            r"\bor\b",
        )
    )


def _requirement_evidence(segments: list[tuple[str, str]]) -> dict[str, str]:
    evidence: dict[str, str] = {}
    evidence_priority: dict[str, int] = {}
    rank = {"must": 0, "preferred": 1, "nice": 2, "responsibility": 3, "unspecified": 4}
    for priority, segment in segments:
        for skill in extract_skills(segment):
            current_rank = evidence_priority.get(skill, 99)
            next_rank = rank.get(priority, 4)
            if next_rank < current_rank:
                evidence[skill] = segment[:320]
                evidence_priority[skill] = next_rank
    return evidence


def _find_terms(text: str, terms: list[str]) -> list[str]:
    hits: list[str] = []
    for term in terms:
        pattern = re.escape(term.lower()).replace(r"\ ", r"\s+")
        if re.search(rf"(?<![a-z0-9+#.]){pattern}(?![a-z0-9+#.])", text):
            hits.append(term)
    return hits


def _dedupe(values: list[str]) -> list[str]:
    output: list[str] = []
    for value in values:
        cleaned = value.strip()
        if cleaned and cleaned not in output:
            output.append(cleaned)
    return output


def _skills_from_sentences(sentences: list[str]) -> list[str]:
    return _dedupe([skill for sentence in sentences for skill in extract_skills(sentence)])


def _experience_requirement(lower: str) -> tuple[float, bool]:
    number_words = {
        "one": "1",
        "two": "2",
        "three": "3",
        "four": "4",
        "five": "5",
        "six": "6",
        "seven": "7",
        "eight": "8",
        "nine": "9",
        "ten": "10",
    }
    normalized = re.sub(
        r"\b(?:" + "|".join(number_words) + r")\b",
        lambda match: number_words[match.group(0)],
        lower,
    )
    range_pattern = re.compile(
        r"\b(\d+(?:\.\d+)?)\s*(?:[-–—]|\bto\b)\s*"
        r"(\d+(?:\.\d+)?)\+?\s*(?:years?|yrs)\b"
    )
    range_minimums = [float(match.group(1)) for match in range_pattern.finditer(normalized)]
    normalized = range_pattern.sub(" ", normalized)
    patterns = (
        r"\b(\d+(?:\.\d+)?)\+?\s*(?:years?|yrs)(?:\s+of)?\s+(?:[a-z][a-z0-9+#./-]*\s+){0,4}experience\b",
        r"\b(\d+(?:\.\d+)?)\+?\s*(?:years?|yrs)(?:\s+of)?(?:\s+(?:professional|relevant|software|backend|frontend|development|industry))*\s+experience\b",
        r"\b(\d+(?:\.\d+)?)\+?\s*(?:years?|yrs)\s+of\s+(?:professional\s+|relevant\s+|industry\s+)?experience\b",
        r"\b(\d+(?:\.\d+)?)\+?\s*(?:years?|yrs)\s+(?:working|developing|building|using|with|in)\b",
        r"\b(?:minimum|at least)\s+(\d+(?:\.\d+)?)\+?\s*(?:years?|yrs)\b",
    )
    values = [
        *range_minimums,
        *[float(value) for pattern in patterns for value in re.findall(pattern, normalized)],
    ]
    if values:
        return max(values), True
    if any(
        term in lower
        for term in (
            "no experience required",
            "no previous experience",
            "entry level",
            "entry-level",
            "student position",
            "internship",
        )
    ):
        return 0.0, True
    return 0.0, False


def _min_years(lower: str) -> float:
    return _experience_requirement(lower)[0]


def _seniority(role: str, lower: str, min_years: float) -> str:
    title = role.lower()
    if any(term in title for term in ("senior", "staff", "principal", "lead")):
        return "senior"
    if any(term in title for term in ("student", "intern", "internship")):
        return "student"
    if any(term in title for term in ("junior", "entry level", "entry-level", "new grad")):
        return "junior"
    if min_years >= 3:
        return "experienced"
    if min_years > 0:
        return "junior"
    if any(term in lower[:2500] for term in ("senior role", "lead engineer", "principal engineer")):
        return "senior"
    return "unspecified"


def _education(lower: str) -> str:
    if "computer science" in lower:
        return "Computer Science"
    if "b.sc" in lower or "bachelor" in lower or "degree" in lower:
        return "Relevant degree"
    return ""


def _work_mode(lower: str) -> str:
    terms = [term for term in ("remote", "hybrid", "onsite", "part-time", "full-time") if term in lower]
    return ", ".join(terms)


def _domain(lower: str, skills: list[str]) -> str:
    if any(_has_phrase(lower, term) for term in ("full stack", "full-stack")):
        return "full-stack"
    if any(_has_phrase(lower, term) for term in ("embedded", "firmware", "low-level", "linux driver")):
        return "embedded/systems"
    if any(_has_phrase(lower, term) for term in ("android", "ios", "mobile")):
        return "mobile"
    if any(_has_phrase(lower, term) for term in ("devops", "cloud", "site reliability")):
        return "cloud"
    if any(_has_phrase(lower, term) for term in ("quality assurance", "qa", "test automation")):
        return "qa"
    if any(_has_phrase(lower, term) for term in ("cybersecurity", "security engineer", "application security")):
        return "security"
    if any(_has_phrase(lower, term) for term in ("machine learning", "ai", "data science")):
        return "ai/data"
    if any(_has_phrase(lower, term) for term in ("data engineer", "data engineering", "etl")):
        return "data"
    if any(_has_phrase(lower, term) for term in ("backend", "api", "server", "database")):
        return "backend"
    if any(_has_phrase(lower, term) for term in ("frontend", "react", "ui", "web")):
        return "frontend"
    return infer_domain(skills)


def _has_phrase(text: str, phrase: str) -> bool:
    escaped = re.escape(phrase).replace(r"\ ", r"\s+")
    return bool(re.search(rf"(?<![a-z0-9]){escaped}(?![a-z0-9])", text))


def _languages(lower: str) -> list[str]:
    supported = ("english", "hebrew", "arabic", "french", "german", "spanish", "russian")
    return [language for language in supported if re.search(rf"\b{language}\b", lower)]


def _work_authorization(lower: str) -> str:
    if any(
        phrase in lower
        for phrase in (
            "must be authorized to work",
            "work authorization required",
            "without sponsorship",
            "no sponsorship",
        )
    ):
        return "Work authorization required; sponsorship unavailable"
    if "security clearance" in lower:
        return "Security clearance required"
    return ""


def _availability(lower: str) -> str:
    if "full-time" in lower or "full time" in lower:
        return "full-time"
    if "part-time" in lower or "part time" in lower:
        return "part-time"
    if "immediate start" in lower or "start immediately" in lower:
        return "immediate"
    return ""


def _summary(sentences: list[str]) -> str:
    selected = [
        sentence
        for sentence in sentences
        if 35 <= len(sentence) <= 260
        and any(hint in sentence.lower() for hint in ("require", "qualification", "experience", "responsibilit", "you will"))
    ]
    if not selected:
        selected = [sentence for sentence in sentences if 45 <= len(sentence) <= 220]
    return " ".join(selected[:4])[:900] or "Could not extract a clean requirements summary."


def _guess_location(text: str) -> str:
    terms = ["Israel", "Jerusalem", "Tel Aviv", "Haifa", "Remote", "Hybrid", "Yokneam", "Ramat Gan", "Herzliya"]
    hits = _find_terms(text.lower(), terms)
    return ", ".join(hits[:4]) if hits else "Not specified"


def _trim_provider_noise(text: str, url: str) -> str:
    host = (urllib.parse.urlparse(url).hostname or "").lower()
    if "linkedin.com" not in host:
        return text
    cutoff_markers = {
        "similar jobs",
        "people also viewed",
        "explore top content on linkedin",
    }
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if line.strip().lower() in cutoff_markers:
            candidate = "\n".join(lines[:index]).strip()
            if len(candidate) >= 300:
                return candidate
    return text


def _extract_title(html_text: str) -> str:
    match = re.search(r"<title[^>]*>(.*?)</title>", html_text, flags=re.IGNORECASE | re.DOTALL)
    return clean_text(html.unescape(match.group(1))) if match else ""


def _find_application_link(links: list[str], fallback: str) -> str:
    for link in links:
        lower = link.lower()
        if any(hint in lower for hint in ("apply", "application", "greenhouse", "lever", "workday", "comeet", "workable")):
            return link
    return fallback


def _source_confidence(
    company: str,
    role: str,
    url: str,
    title: str,
    text: str,
    method: str,
) -> float:
    parsed = urllib.parse.urlparse(url)
    host_path = f"{parsed.netloc} {parsed.path}".lower()
    visible = f"{title} {text[:5000]}".lower()
    score = 0.0
    if role and role.lower() not in {"unknown role", "pasted job description"}:
        score += 0.2
    if company and company.lower() != "unknown company":
        score += 0.1
    if len(text) >= 180:
        score += 0.2
    if len(text) >= 700:
        score += 0.1
    if any(hint in host_path for hint in CAREER_HINTS):
        score += 0.1
    if any(hint in visible for hint in ("apply", "requirements", "qualifications", "responsibilities", "experience")):
        score += 0.15
    if method in {"json_ld", "workday_api"}:
        score += 0.15
    elif method == "pasted":
        score += 0.1
    return min(score, 1.0)


def _company_from_metadata(meta: dict[str, str], title: str, url: str) -> str:
    og_title = meta.get("og:title") or ""
    host = (urllib.parse.urlparse(url).hostname or "").lower()
    if "linkedin.com" in host:
        match = re.match(r"(.+?)\s+hiring\s+.+", og_title, flags=re.IGNORECASE)
        if match:
            return clean_text(match.group(1))
    for candidate_title in _dedupe([og_title, title]):
        match = re.search(
            r"(?:Job opportunity:\s*.+?|Job Application for\s+.+?)\s+at\s+(.+?)(?:\s*\|\s*|\s+[\-–—]\s+|$)",
            candidate_title,
            flags=re.IGNORECASE,
        )
        if match:
            return clean_text(match.group(1))
    match = re.match(r"(.+?)\s+careers?\s*[-|]\s*.+", og_title, flags=re.IGNORECASE)
    if match:
        return clean_text(match.group(1))
    site = meta.get("og:site_name") or meta.get("application-name") or ""
    site = re.sub(r"(?i)\s+(careers?|jobs?)$", "", clean_text(site))
    if site.lower() in {"linkedin", "greenhouse", "comeet", "spark hire recruit"}:
        return ""
    return site[:160]


def _role_from_metadata(meta: dict[str, str], title: str, url: str) -> str:
    og_title = clean_text(meta.get("og:title") or "")
    host = (urllib.parse.urlparse(url).hostname or "").lower()
    if "linkedin.com" in host:
        match = re.match(
            r".+?\s+hiring\s+(.+?)\s+in\s+.+?(?:\s*\|\s*LinkedIn)?$",
            og_title,
            flags=re.IGNORECASE,
        )
        if match:
            return clean_text(match.group(1))
    for pattern in (
        r"Job opportunity:\s*(.+?)\s+at\s+.+$",
        r"Job Application for\s+(.+?)\s+at\s+.+$",
        r".+?\s+careers?\s*[-|]\s*(.+)$",
    ):
        match = re.match(pattern, og_title, flags=re.IGNORECASE)
        if match:
            return clean_text(match.group(1))
    if og_title and not any(
        generic in og_title.lower()
        for generic in ("careers", "current openings", "collaborative recruiting")
    ):
        return _role_from_title(og_title)
    return ""


def _company_from_url(url: str) -> str:
    if not url:
        return "Unknown Company"
    parsed = urllib.parse.urlparse(url)
    host = (parsed.hostname or "").lower()
    path_parts = [urllib.parse.unquote(part) for part in parsed.path.split("/") if part]
    if "greenhouse.io" in host and path_parts:
        return path_parts[0].replace("-", " ").title()
    if "comeet.com" in host and len(path_parts) >= 2 and path_parts[0].lower() == "jobs":
        return path_parts[1].replace("-", " ").title()
    ignored = {"www", "jobs", "job", "careers", "career", "com", "co", "org", "net"}
    parts = [part for part in (parsed.hostname or "").split(".") if part and part.lower() not in ignored]
    if not parts:
        return "Unknown Company"
    company = parts[0].replace("-", " ").title()
    return company.upper() if len(company) <= 4 and company.isalpha() else company


def _role_from_title(title: str) -> str:
    title = clean_text(title)
    title = re.split(r"\s+[|–—-]\s+", title)[0]
    return title[:180] or "Unknown Role"


def _role_from_text(text: str) -> str:
    for line in text.splitlines()[:8]:
        candidate = clean_text(line)
        if 4 <= len(candidate) <= 180 and not any(
            hint in candidate.lower()
            for hint in (
                "description",
                "requirements",
                "qualifications",
                "responsibilities",
                "see all",
                "open roles",
                "job openings",
                "careers",
            )
        ):
            return candidate
    return ""


def _main_token(company: str) -> str:
    tokens = re.findall(r"[a-z0-9]+", company.lower())
    ignored = {"inc", "ltd", "llc", "corp", "corporation", "company", "israel"}
    tokens = [token for token in tokens if token not in ignored and len(token) > 2]
    return tokens[0] if tokens else ""


def _role_tokens(role: str) -> list[str]:
    ignored = {"and", "the", "for", "with", "engineer", "developer", "software", "student", "intern"}
    tokens = re.findall(r"[a-z0-9+#.]+", role.lower())
    return [token for token in tokens if token not in ignored and len(token) > 2]


class _JobHtmlParser(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__()
        self.base_url = base_url
        self.text_parts: list[str] = []
        self.main_text_parts: list[str] = []
        self.links: list[str] = []
        self.meta: dict[str, str] = {}
        self.title = ""
        self._skip_depth = 0
        self._main_depth = 0
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {key.lower(): value or "" for key, value in attrs}
        if tag in {"script", "style", "noscript", "svg", "nav", "header", "footer", "form"}:
            self._skip_depth += 1
            return
        if tag in {"main", "article"} or attributes.get("role", "").lower() == "main":
            self._main_depth += 1
        if tag == "title":
            self._in_title = True
        if tag == "a":
            href = attributes.get("href")
            if href:
                self.links.append(urllib.parse.urljoin(self.base_url, href))
        if tag == "meta":
            key = (attributes.get("property") or attributes.get("name") or "").lower()
            content = clean_text(attributes.get("content", ""))
            if key and content:
                self.meta[key] = content

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript", "svg", "nav", "header", "footer", "form"} and self._skip_depth:
            self._skip_depth -= 1
        if tag in {"main", "article"} and self._main_depth:
            self._main_depth -= 1
        if tag == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        cleaned = data.strip()
        if not cleaned:
            return
        if self._in_title:
            self.title += f" {cleaned}"
        self.text_parts.append(cleaned)
        if self._main_depth:
            self.main_text_parts.append(cleaned)


class _JsonLdParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.blocks: list[str] = []
        self._capturing = False
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {key.lower(): value or "" for key, value in attrs}
        if tag == "script" and "ld+json" in attributes.get("type", "").lower():
            self._capturing = True
            self._parts = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "script" and self._capturing:
            self.blocks.append("".join(self._parts).strip())
            self._capturing = False
            self._parts = []

    def handle_data(self, data: str) -> None:
        if self._capturing:
            self._parts.append(data)


class _FragmentTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"br", "li", "p", "div", "h1", "h2", "h3", "h4"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"li", "p", "div", "h1", "h2", "h3", "h4"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        cleaned = data.strip()
        if cleaned:
            self.parts.append(cleaned)
