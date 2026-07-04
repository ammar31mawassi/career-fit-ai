from app.services.job_research import classify_requirements
from app.services.ontology import canonical_skill, extract_skills, skill_match_strength


def test_aliases_and_boundaries_are_safe():
    assert canonical_skill("Postgres") == "postgresql"
    assert canonical_skill("CPP") == "c++"
    assert extract_skills("Built software in C and C++ with PostgreSQL.") == ["c", "c++", "postgresql"]
    assert "c" not in extract_skills("Created scalable applications.")


def test_transferable_skills_receive_partial_credit():
    assert skill_match_strength("c++", "firmware") == 0.55
    assert skill_match_strength("postgresql", "postgresql") == 1.0
    assert skill_match_strength("react", "firmware") == 0.0


def test_requirement_sections_are_classified_conservatively():
    requirements = classify_requirements(
        "Requirements: Python and PostgreSQL with 2+ years of professional experience. "
        "Preferred: Docker. Nice to have: Kubernetes. Responsibilities: Build REST APIs."
    )
    assert requirements.must_have_skills == ["python", "postgresql"]
    assert requirements.preferred_skills == ["docker", "rest api"]
    assert requirements.nice_to_have_skills == ["kubernetes"]
    assert requirements.min_years_experience == 2
    assert requirements.evidence_by_requirement["python"].startswith("Requirements")
