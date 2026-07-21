from datetime import date

from app.services.cv_sections import section_heading, section_lines
from app.services.experience_normalization import professional_experience
from app.services.job_research import classify_requirements
from app.services.ontology import canonical_skill, extract_skills


def test_section_aliases_are_canonical_and_inline_content_is_retained():
    assert section_heading("EDUCATIONAL QUALIFICATIONS") == ("education", "")
    assert section_heading("Key Skills: Python, SQL") == ("skills", "Python, SQL")
    assert section_heading("Work History - Software Engineer") == ("experience", "Software Engineer")
    assert section_heading("Professional experience with Python") == (
        None,
        "Professional experience with Python",
    )

    lines = section_lines("CAREER OBJECTIVE\nBuild useful systems\nEMPLOYMENT HISTORY\nDeveloper\n2019-2021")
    assert [line.section for line in lines] == ["objective", "objective", "experience", "experience", "experience"]


def test_professional_timeline_unions_overlapping_roles_and_excludes_education():
    estimate = professional_experience(
        """
        EDUCATION
        B.Sc. Computer Science | 2016-2020
        PROFESSIONAL EXPERIENCE
        Software Engineer | Jan 2020 - Dec 2021
        Backend Engineer | Jul 2021 - Jun 2023
        """,
        reference_date=date(2024, 1, 1),
    )

    assert estimate.years == 3.5
    assert estimate.source == "timeline"
    assert estimate.intervals == 2


def test_explicit_months_and_number_words_are_normalized():
    assert professional_experience("18 months of professional experience").years == 1.5
    assert professional_experience("Over five years of software experience").years == 5.0


def test_job_month_requirement_is_converted_to_years():
    requirements = classify_requirements(
        "Minimum qualifications: At least 18 months of professional software experience.",
        "Software Engineer",
    )
    assert requirements.min_years_experience == 1.5
    assert requirements.experience_requirement_known is True


def test_training_driven_ontology_aliases_cover_major_job_families():
    assert canonical_skill("QA Automation") == "test automation"
    assert canonical_skill("Sysadmin") == "system administration"
    assert extract_skills("PHP, Laravel, Ruby on Rails, Salesforce, Unity3D") == [
        "php",
        "laravel",
        "ruby on rails",
        "salesforce",
        "unity",
    ]


def test_role_category_aliases_do_not_create_prose_false_positives():
    assert canonical_skill("Data Analyst") == "data analysis"
    assert canonical_skill("HR") == "human resources"
    assert canonical_skill("Support") == "technical support"
    assert "technical support" not in extract_skills("We support teams across the company.")
    assert "human resources" not in extract_skills("Ask your HR representative.")


def test_art_and_qa_skills_are_recognized_conservatively():
    skills = extract_skills("2D Animator using Blender, Photoshop, After Effects and Spine. QA testing.")
    assert {"2d animation", "3d art", "image editing", "motion graphics", "quality assurance", "software testing"} <= set(skills)
    assert "quality assurance" not in extract_skills("qa testing")
