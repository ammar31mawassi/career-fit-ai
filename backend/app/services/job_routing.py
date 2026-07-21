from __future__ import annotations

from .career_interests import CAREER_INTEREST_SET
from .job_research import JobRequirements


DOMAIN_FIELDS: dict[str, tuple[str, ...]] = {
    "backend": ("Software Engineering",),
    "full-stack": ("Software Engineering", "Frontend Development"),
    "frontend": ("Frontend Development", "Software Engineering"),
    "mobile": ("Mobile Development", "Software Engineering"),
    "cloud": ("DevOps", "Software Engineering"),
    "qa": ("QA",),
    "embedded/systems": ("Embedded, Low-Level & Firmware", "Systems Engineering"),
    "security": ("Cybersecurity",),
    "ai/data": ("AI, Data Science, ML & Algorithms", "Data Analytics"),
    "data": ("Data Analytics", "AI, Data Science, ML & Algorithms"),
}

ROLE_FIELD_HINTS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("hardware", "fpga", "asic", "vlsi", "verification engineer"), "Hardware Engineering"),
    (("mechanical", "mechatronics"), "Mechanical Engineering"),
    (("process engineer",), "Mechanical Engineering"),
    (("systems engineer", "system engineer"), "Systems Engineering"),
    (("product manager", "product owner"), "Product Management"),
    (("ui/ux", "ux designer", "product designer", "content designer"), "UI/UX & Content Design"),
    (("customer success", "solutions engineer", "support engineer"), "Customer Success"),
    (("sales", "account executive"), "Sales"),
    (("marketing", "growth"), "Marketing"),
    (("recruit", "human resources", "talent acquisition", " hr "), "HR & Recruitment"),
    (("project manager", "program manager"), "Project Management"),
    (("finance", "accountant", "controller"), "Finance & Accounting"),
    (("legal", "compliance", "policy"), "Legal, Compliance & Policy"),
    (("business development", "partnerships"), "Business Development"),
    (("operations", "office manager"), "Operations"),
    (("system administrator", "it support", "network administrator"), "IT & System Administration"),
)


def route_job_fields(
    role: str,
    requirements: JobRequirements,
    declared_field: str = "",
) -> list[str]:
    role_text = f" {role.lower()} "
    explicit_fields: list[str] = []
    for hints, field in ROLE_FIELD_HINTS:
        if any(hint in role_text for hint in hints):
            explicit_fields.append(field)
    # An explicit job function is authoritative. A Product Manager who works on
    # APIs is still a Product Management role, not a Software Engineering role.
    if explicit_fields:
        return [
            field
            for field in dict.fromkeys(explicit_fields)
            if field in CAREER_INTEREST_SET
        ][:3]
    fields: list[str] = []
    if declared_field in CAREER_INTEREST_SET:
        fields.append(declared_field)
    fields.extend(DOMAIN_FIELDS.get(requirements.domain, ()))
    if not fields and any(term in role_text for term in ("engineer", "developer", "architect")):
        fields.append("Software Engineering")
    return [field for field in dict.fromkeys(fields) if field in CAREER_INTEREST_SET][:3]
