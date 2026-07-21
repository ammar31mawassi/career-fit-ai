from __future__ import annotations

import gzip
import json
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable
from uuid import uuid4


SOURCE_NAME = "goozali"
MAX_BOOTSTRAP_BYTES = 512_000
MAX_COMPRESSED_BYTES = 12_000_000
MAX_JSON_BYTES = 64_000_000
NETWORK_TIMEOUT_SECONDS = 45
USER_AGENT = "CareerFit-JobDiscovery/1.0 (+https://career-fit-ai-sigma.vercel.app)"
EMAIL_PATTERN = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
ISRAEL_PHONE_PATTERN = re.compile(r"(?<!\d)(?:\+?972|0)(?:[\s().-]*\d){7,10}(?!\d)")


class GoozaliSourceError(RuntimeError):
    pass


@dataclass(frozen=True)
class GoozaliJob:
    external_id: str
    role: str
    company: str
    career_field: str
    location: str
    description_text: str
    source_url: str
    application_link: str
    source_published_at: datetime | None
    discovered_at: datetime
    source_confidence: float


@dataclass(frozen=True)
class GoozaliFetchResult:
    jobs: list[GoozaliJob]
    records_seen: int
    records_valid: int


@dataclass(frozen=True)
class _Bootstrap:
    application_id: str
    share_id: str
    table_id: str
    view_id: str
    access_policy: str
    page_load_id: str


UrlOpen = Callable[..., object]


def fetch_goozali_jobs(embed_url: str, *, urlopen: UrlOpen = urllib.request.urlopen) -> GoozaliFetchResult:
    bootstrap_html = _request_bytes(
        embed_url,
        headers={"User-Agent": USER_AGENT},
        limit=MAX_BOOTSTRAP_BYTES,
        urlopen=urlopen,
    ).decode("utf-8", errors="replace")
    bootstrap = _parse_bootstrap(bootstrap_html)
    params = urllib.parse.urlencode(
        {
            "stringifiedObjectParams": json.dumps(
                {"shouldUseNestedResponseFormat": True}, separators=(",", ":")
            ),
            "requestId": f"req{uuid4().hex[:14]}",
            "accessPolicy": bootstrap.access_policy,
        }
    )
    endpoint = (
        f"https://airtable.com/v0.3/view/{urllib.parse.quote(bootstrap.view_id)}/"
        f"readSharedViewData?{params}"
    )
    payload_bytes = _request_bytes(
        endpoint,
        headers={
            "Accept-Encoding": "gzip",
            "Origin": "https://airtable.com",
            "User-Agent": USER_AGENT,
            "x-airtable-application-id": bootstrap.application_id,
            "x-airtable-inter-service-client": "webClient",
            "x-airtable-page-load-id": bootstrap.page_load_id,
            "x-early-prefetch": "true",
            "x-requested-with": "XMLHttpRequest",
            "x-time-zone": "Asia/Jerusalem",
            "x-user-locale": "en",
        },
        limit=MAX_COMPRESSED_BYTES,
        urlopen=urlopen,
        decompress_gzip=True,
    )
    if len(payload_bytes) > MAX_JSON_BYTES:
        raise GoozaliSourceError("Goozali shared-view payload is too large.")
    try:
        payload = json.loads(payload_bytes)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise GoozaliSourceError("Goozali shared-view response is not valid JSON.") from exc
    return parse_shared_view(payload, bootstrap)


def parse_shared_view(payload: object, bootstrap: _Bootstrap | None = None) -> GoozaliFetchResult:
    if not isinstance(payload, dict):
        raise GoozaliSourceError("Goozali shared-view contract is missing its data object.")
    data = payload.get("data")
    table = data.get("table") if isinstance(data, dict) else None
    if not isinstance(table, dict):
        raise GoozaliSourceError("Goozali shared-view contract is missing its table.")
    columns = table.get("columns")
    rows = table.get("rows")
    views = table.get("views")
    if not isinstance(columns, list) or not isinstance(rows, list) or not isinstance(views, list) or not views:
        raise GoozaliSourceError("Goozali shared-view contract is incomplete.")

    columns_by_name = {
        str(column.get("name")): column
        for column in columns
        if isinstance(column, dict) and column.get("id") and column.get("name")
    }
    required = {"Job Title", "Company", "Job Description", "Requirements"}
    if not required.issubset(columns_by_name):
        raise GoozaliSourceError("Goozali job columns changed.")

    visible_ids = _visible_row_ids(views[0])
    jobs: list[GoozaliJob] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        row_id = _text(row.get("id"))
        if not row_id or (visible_ids is not None and row_id not in visible_ids):
            continue
        cells = row.get("cellValuesByColumnId")
        if not isinstance(cells, dict):
            continue
        role = _cell_text(cells, columns_by_name.get("Job Title"))
        company = _cell_text(cells, columns_by_name.get("Company"))
        description = _cell_text(cells, columns_by_name.get("Job Description"))
        requirements = _cell_text(cells, columns_by_name.get("Requirements"))
        scope = _choice_text(cells, columns_by_name.get("Scope"))
        locations = _choice_text(cells, columns_by_name.get("Location"))
        languages = _choice_text(cells, columns_by_name.get("Language requirement"))
        education = _cell_text(cells, columns_by_name.get("Education requirements"))
        min_experience = _cell_text(cells, columns_by_name.get("Min Experience (Y)"))
        combined = _remove_contact_details(_job_text(
            description=description,
            requirements=requirements,
            scope=scope,
            locations=locations,
            languages=languages,
            education=education,
            min_experience=min_experience,
        ))
        if not role or not company or len(combined) < 120:
            continue
        discovered_at = _datetime(row.get("createdTime"))
        if discovered_at is None:
            continue
        published_at = _datetime(_cell_value(cells, columns_by_name.get("Posted")))
        career_field = _choice_text(cells, columns_by_name.get("Field"))
        application_link = _safe_public_url(
            _cell_text(cells, columns_by_name.get("Position Link"))
        )
        source_url = _record_url(bootstrap, row_id)
        jobs.append(
            GoozaliJob(
                external_id=row_id,
                role=role[:300],
                company=company[:300],
                career_field=_career_interest(career_field),
                location=locations[:500],
                description_text=combined,
                source_url=source_url,
                application_link=application_link,
                source_published_at=published_at,
                discovered_at=discovered_at,
                source_confidence=0.92 if requirements else 0.82,
            )
        )
    jobs.sort(key=lambda item: item.discovered_at, reverse=True)
    return GoozaliFetchResult(jobs=jobs, records_seen=len(rows), records_valid=len(jobs))


def _parse_bootstrap(html: str) -> _Bootstrap:
    access_match = re.search(r'"accessPolicy":"((?:\\.|[^"\\])*)"', html)
    if access_match is None:
        raise GoozaliSourceError("Goozali shared-view access policy was not found.")
    try:
        access_policy = json.loads(f'"{access_match.group(1)}"')
    except json.JSONDecodeError as exc:
        raise GoozaliSourceError("Goozali shared-view access policy is invalid.") from exc
    return _Bootstrap(
        application_id=_bootstrap_value(html, "sharedModelParentApplicationId"),
        share_id=_bootstrap_value(html, "shareId"),
        table_id=_bootstrap_value(html, "sharedViewTableId"),
        view_id=_bootstrap_value(html, "sharedViewId"),
        access_policy=access_policy,
        page_load_id=_bootstrap_value(html, "pageLoadId"),
    )


def _bootstrap_value(html: str, key: str) -> str:
    match = re.search(rf'"{re.escape(key)}":"([^"]+)"', html)
    if match is None or not match.group(1):
        raise GoozaliSourceError(f"Goozali shared-view bootstrap is missing {key}.")
    return match.group(1)


def _request_bytes(
    url: str,
    *,
    headers: dict[str, str],
    limit: int,
    urlopen: UrlOpen,
    decompress_gzip: bool = False,
) -> bytes:
    request = urllib.request.Request(url, headers=headers)
    try:
        response = urlopen(request, timeout=NETWORK_TIMEOUT_SECONDS)
        with response:  # type: ignore[attr-defined]
            declared = _content_length(response)
            if declared is not None and declared > limit:
                raise GoozaliSourceError("Goozali response exceeded the configured size limit.")
            data = response.read(limit + 1)  # type: ignore[attr-defined]
            encoding = str(response.headers.get("Content-Encoding", "")).lower()  # type: ignore[attr-defined]
    except GoozaliSourceError:
        raise
    except Exception as exc:
        raise GoozaliSourceError("Goozali public table could not be reached.") from exc
    if len(data) > limit:
        raise GoozaliSourceError("Goozali response exceeded the configured size limit.")
    if decompress_gzip and encoding == "gzip":
        try:
            data = gzip.decompress(data)
        except OSError as exc:
            raise GoozaliSourceError("Goozali response compression was invalid.") from exc
    return data


def _content_length(response: object) -> int | None:
    try:
        value = response.headers.get("Content-Length")  # type: ignore[attr-defined]
        return int(value) if value else None
    except (AttributeError, TypeError, ValueError):
        return None


def _visible_row_ids(view: object) -> set[str] | None:
    if not isinstance(view, dict) or not isinstance(view.get("rowOrder"), list):
        return None
    result: set[str] = set()
    for item in view["rowOrder"]:
        if isinstance(item, str):
            result.add(item)
        elif isinstance(item, dict) and item.get("visibility", True) is not False:
            row_id = _text(item.get("rowId") or item.get("id"))
            if row_id:
                result.add(row_id)
    return result


def _cell_value(cells: dict[str, object], column: object) -> object:
    if not isinstance(column, dict):
        return None
    return cells.get(str(column.get("id") or ""))


def _cell_text(cells: dict[str, object], column: object) -> str:
    return _text(_cell_value(cells, column))


def _choice_text(cells: dict[str, object], column: object) -> str:
    if not isinstance(column, dict):
        return ""
    raw = _cell_value(cells, column)
    values = raw if isinstance(raw, list) else [raw]
    type_options = column.get("typeOptions")
    choices = type_options.get("choices") if isinstance(type_options, dict) else None
    rendered: list[str] = []
    for value in values:
        choice = choices.get(str(value)) if isinstance(choices, dict) else None
        name = choice.get("name") if isinstance(choice, dict) else value
        text = _text(name)
        if text and text not in rendered:
            rendered.append(text)
    return ", ".join(rendered)


def _text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return " ".join(value.split())
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, dict):
        return _text(value.get("text") or value.get("name") or value.get("value"))
    return ""


def _datetime(value: object) -> datetime | None:
    text = _text(value)
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _job_text(
    *,
    description: str,
    requirements: str,
    scope: str,
    locations: str,
    languages: str,
    education: str,
    min_experience: str,
) -> str:
    sections: list[str] = []
    if description:
        sections.append(description)
    if requirements:
        sections.append(f"Requirements:\n{requirements}")
    details = [
        ("Employment scope", scope),
        ("Location", locations),
        ("Minimum experience", f"{min_experience} years" if min_experience else ""),
        ("Language requirements", languages),
        ("Education requirements", education),
    ]
    rendered_details = [f"{label}: {value}" for label, value in details if value]
    if rendered_details:
        sections.append("\n".join(rendered_details))
    return "\n\n".join(sections).strip()


def _safe_public_url(value: str) -> str:
    if not value:
        return ""
    parsed = urllib.parse.urlparse(value)
    return value[:2000] if parsed.scheme in {"http", "https"} and parsed.netloc else ""


def _remove_contact_details(value: str) -> str:
    without_email = EMAIL_PATTERN.sub("[contact email removed]", value)
    return ISRAEL_PHONE_PATTERN.sub("[contact phone removed]", without_email)


def _record_url(bootstrap: _Bootstrap | None, record_id: str) -> str:
    if bootstrap is None:
        return "https://goozali.com/#jobopenings"
    return (
        f"https://airtable.com/embed/{bootstrap.application_id}/{bootstrap.share_id}/"
        f"{bootstrap.table_id}/{bootstrap.view_id}/{record_id}"
    )


def _career_interest(value: str) -> str:
    mapping = {
        "Data Science, ML & Algorithms": "AI, Data Science, ML & Algorithms",
        "Data Analyst": "Data Analytics",
        "Data Analytics & BI": "Data Analytics",
        "Embedded, Low Level & Firmware Engineering": "Embedded, Low-Level & Firmware",
        "IT and System Administration": "IT & System Administration",
        "UI/UX, Design & Content": "UI/UX & Content Design",
        "Finance": "Finance & Accounting",
        "C-Level": "Executive / C-Level",
        "Compliance, Legal & Policy": "Legal, Compliance & Policy",
    }
    return mapping.get(value, value)
