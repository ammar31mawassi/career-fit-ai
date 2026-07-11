from __future__ import annotations

import re
from dataclasses import dataclass


ONTOLOGY_VERSION = "skills-v1.2.2"


@dataclass(frozen=True)
class SkillDefinition:
    canonical: str
    aliases: tuple[str, ...]
    domain: str
    related: tuple[str, ...] = ()


def _skill(
    canonical: str,
    domain: str,
    *aliases: str,
    related: tuple[str, ...] = (),
) -> SkillDefinition:
    return SkillDefinition(canonical, (canonical, *aliases), domain, related)


SKILLS: tuple[SkillDefinition, ...] = (
    _skill("python", "backend", "python3", related=("fastapi", "django", "flask")),
    _skill("java", "backend", related=("spring", "kotlin")),
    _skill("c", "embedded", "c language", related=("c++", "embedded systems", "firmware")),
    _skill("c++", "embedded", "cpp", "c plus plus", related=("c", "embedded systems", "firmware")),
    _skill("c#", "backend", "c sharp", related=(".net",)),
    _skill("go", "backend", "golang"),
    _skill("rust", "embedded", related=("c++", "embedded systems")),
    _skill("kotlin", "mobile", related=("java", "android")),
    _skill("swift", "mobile", related=("ios",)),
    _skill("javascript", "frontend", "js", related=("typescript", "node.js")),
    _skill("typescript", "frontend", "ts", related=("javascript",)),
    _skill("html", "frontend", "html5"),
    _skill("css", "frontend", "css3"),
    _skill("react", "frontend", "react.js", "reactjs", related=("next.js", "javascript", "typescript")),
    _skill("next.js", "frontend", "nextjs", "next js", related=("react",)),
    _skill("angular", "frontend", "angular.js", "angularjs"),
    _skill("vue", "frontend", "vue.js", "vuejs"),
    _skill("node.js", "backend", "node", "nodejs", related=("javascript", "typescript")),
    _skill("fastapi", "backend", "fast api", related=("python", "rest api")),
    _skill("django", "backend", related=("python",)),
    _skill("flask", "backend", related=("python",)),
    _skill("spring", "backend", "spring boot", related=("java",)),
    _skill(".net", "backend", "dotnet", "asp.net", related=("c#",)),
    _skill("rest api", "backend", "restful api", "restful services", "rest"),
    _skill("graphql", "backend"),
    _skill("microservices", "backend", "microservice architecture"),
    _skill("sql", "data", "structured query language", related=("postgresql", "mysql", "sqlite")),
    _skill("postgresql", "data", "postgres", "postgre sql", related=("sql",)),
    _skill("mysql", "data", related=("sql",)),
    _skill("sqlite", "data", related=("sql",)),
    _skill("mongodb", "data", "mongo"),
    _skill("redis", "data"),
    _skill("elasticsearch", "data", "elastic search"),
    _skill("pandas", "data", related=("python",)),
    _skill("numpy", "data", related=("python",)),
    _skill("spark", "data", "apache spark"),
    _skill("kafka", "data", "apache kafka"),
    _skill("airflow", "data", "apache airflow"),
    _skill("etl", "data", "extract transform load"),
    _skill("machine learning", "ml", "ml"),
    _skill("deep learning", "ml", "neural networks"),
    _skill("pytorch", "ml", "torch"),
    _skill("tensorflow", "ml", "tensor flow"),
    _skill("scikit-learn", "ml", "sklearn", "scikit learn"),
    _skill("nlp", "ml", "natural language processing"),
    _skill("computer vision", "ml", "opencv"),
    _skill("docker", "cloud"),
    _skill("kubernetes", "cloud", "k8s"),
    _skill("aws", "cloud", "amazon web services"),
    _skill("azure", "cloud", "microsoft azure"),
    _skill("gcp", "cloud", "google cloud", "google cloud platform"),
    _skill("terraform", "cloud"),
    _skill("ansible", "cloud"),
    _skill("ci/cd", "cloud", "continuous integration", "continuous delivery", "continuous deployment"),
    _skill("github actions", "cloud"),
    _skill("linux", "systems", "unix"),
    _skill("bash", "systems", "shell scripting"),
    _skill("git", "engineering", "version control"),
    _skill("github", "engineering"),
    _skill("unit testing", "qa", "unit tests", "pytest", "junit"),
    _skill("integration testing", "qa", "integration tests"),
    _skill("test automation", "qa", "automated testing"),
    _skill("manual testing", "qa", "manual qa", "manual tester", "manual software testing"),
    _skill("test planning", "qa", "test plan", "test plans"),
    _skill("verification and validation", "qa", "v&v", "verification & validation"),
    _skill("jira", "qa"),
    _skill("confluence", "engineering"),
    _skill("qa certification", "qa", "qa course"),
    _skill("artillery systems", "defense", "artillery", "artillery system"),
    _skill("selenium", "qa"),
    _skill("playwright", "qa"),
    _skill("embedded systems", "embedded", "embedded", "embedded software", "embedded development"),
    _skill("firmware", "embedded"),
    _skill("rtos", "embedded", "real time operating system", "real-time operating system"),
    _skill("microcontrollers", "embedded", "microcontroller", "mcu"),
    _skill("arm", "embedded", "arm cortex"),
    _skill("linux drivers", "embedded", "device drivers", "kernel drivers"),
    _skill("i2c", "embedded"),
    _skill("spi", "embedded"),
    _skill("uart", "embedded"),
    _skill("can bus", "embedded", "can protocol"),
    _skill("multithreading", "systems", "multi-threading", "concurrency"),
    _skill("networking", "systems", "tcp/ip", "network protocols"),
    _skill("android", "mobile", "android development"),
    _skill("ios", "mobile", "ios development"),
    _skill("react native", "mobile"),
    _skill("flutter", "mobile", "dart"),
    _skill("cybersecurity", "security", "information security", "application security"),
    _skill("penetration testing", "security", "pentesting"),
    _skill("cryptography", "security"),
    _skill("oauth", "security", "oauth2"),
    _skill("supabase", "backend"),
    _skill("firebase", "backend"),
    _skill("agile", "engineering", "scrum"),
    _skill("system design", "engineering", "software architecture"),
    _skill("data structures", "engineering", "data structures and algorithms", "dsa"),
    _skill("algorithms", "engineering", "algorithm design"),
    _skill("oop", "engineering", "object oriented programming", "object-oriented programming"),
    _skill("management", "professional", "management skills", "managerial skills"),
    _skill("project coordination", "professional", "project coordinator"),
    _skill("planning", "professional", "project planning"),
    _skill("organizational skills", "professional", "organizational management", "organisation skills"),
    _skill("problem solving", "professional", "problem-solving"),
    _skill("leadership", "professional", "proactive leadership"),
    _skill("teamwork", "professional", "team work", "collaboration"),
    _skill("communication", "professional", "communication skills"),
    _skill("decision making", "professional", "decision-making"),
)

_BY_CANONICAL = {skill.canonical: skill for skill in SKILLS}
_ALIASES = sorted(
    ((alias.lower(), skill.canonical) for skill in SKILLS for alias in skill.aliases),
    key=lambda item: len(item[0]),
    reverse=True,
)


def canonical_skill(value: str) -> str | None:
    normalized = _normalize(value)
    for alias, canonical in _ALIASES:
        if normalized == _normalize(alias):
            return canonical
    return None


def extract_skills(text: str) -> list[str]:
    hits: list[tuple[int, str]] = []
    occupied: list[tuple[int, int]] = []
    for alias, canonical in _ALIASES:
        pattern = _term_pattern(alias)
        flags = 0 if alias in {"c", "r", "go", "rest"} else re.IGNORECASE
        for match in re.finditer(pattern, text, flags=flags):
            span = match.span()
            if any(span[0] < end and span[1] > start for start, end in occupied):
                continue
            hits.append((span[0], canonical))
            occupied.append(span)
    hits.sort(key=lambda item: item[0])
    return _dedupe([canonical for _, canonical in hits])


def skill_domain(skill: str) -> str:
    canonical = canonical_skill(skill) or skill.lower().strip()
    definition = _BY_CANONICAL.get(canonical)
    return definition.domain if definition else "software"


def infer_domain(skills: list[str] | set[str]) -> str:
    counts: dict[str, int] = {}
    for skill in skills:
        domain = skill_domain(skill)
        if domain == "professional":
            continue
        counts[domain] = counts.get(domain, 0) + 1
    if not counts:
        return "software"
    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))[0][0]


def skill_match_strength(candidate_skill: str, requirement: str) -> float:
    candidate = canonical_skill(candidate_skill) or candidate_skill.lower().strip()
    required = canonical_skill(requirement) or requirement.lower().strip()
    if candidate == required:
        return 1.0
    definition = _BY_CANONICAL.get(required)
    candidate_definition = _BY_CANONICAL.get(candidate)
    if definition and candidate in definition.related:
        return 0.55
    if candidate_definition and required in candidate_definition.related:
        return 0.55
    if definition and candidate_definition and definition.domain == candidate_definition.domain:
        return 0.2
    return 0.0


def _term_pattern(term: str) -> str:
    # Single-letter programming languages cannot be matched case-insensitively:
    # doing so turns every `.com` address into evidence for C.
    if term == "c":
        return r"(?<![A-Za-z0-9])C(?![A-Za-z0-9+#])"
    if term == "go":
        # Go is also a common English verb. Only count the language when it is
        # written as the proper noun "Go"; "Golang" remains case-insensitive.
        return r"(?<![A-Za-z0-9])Go(?![A-Za-z0-9+#])"
    if term == "rest":
        # REST as an API style is conventionally uppercase; lowercase "rest"
        # is ordinary English and caused false positives in legal/job boilerplate.
        return r"(?<![A-Za-z0-9])REST(?![A-Za-z0-9+#])"
    escaped = re.escape(term.lower()).replace(r"\ ", r"\s+")
    return rf"(?<![a-z0-9]){escaped}(?![a-z0-9])"


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def _dedupe(values: list[str]) -> list[str]:
    output: list[str] = []
    for value in values:
        if value and value not in output:
            output.append(value)
    return output
