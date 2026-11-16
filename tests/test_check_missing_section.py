"""MISSING_SECTION raises one Issue per missing Experience, Education or Skills section."""
import pytest

from checks import check_missing_section
from conftest import document_from_text

FULL = "Jane Testperson\nSKILLS\nPython\nEXPERIENCE\nEngineer\nEDUCATION\nB.S. Computer Science\n"


def run(text):
    return check_missing_section(document_from_text(text))


def test_all_three_sections_present_passes():
    result = run(FULL)

    assert result.component == "missing_sections"
    assert result.value == 1
    assert result.issues == []


@pytest.mark.parametrize(
    "heading",
    [
        "experience",
        "Experience",
        "EXPERIENCE:",
        "Work Experience",
        "  Professional Experience  ",
        "Employment History",
        "— EXPERIENCE —",
    ],
)
def test_experience_heading_variants_are_recognised(heading):
    text = FULL.replace("EXPERIENCE", heading)

    assert run(text).value == 1


@pytest.mark.parametrize("skills", ["Technical Skills", "Skills & Tools", "Core Competencies", "Technologies"])
def test_skills_synonyms_are_recognised(skills):
    assert run(FULL.replace("SKILLS", skills)).value == 1


def test_education_synonym_is_recognised():
    assert run(FULL.replace("EDUCATION", "Education and Training")).value == 1


@pytest.mark.parametrize(
    "removed_heading, missing",
    [("SKILLS", "Skills"), ("EXPERIENCE", "Experience"), ("EDUCATION", "Education")],
)
def test_one_missing_section_raises_one_issue_naming_it(removed_heading, missing):
    result = run(FULL.replace(removed_heading, "Summary"))

    assert result.value == pytest.approx(2 / 3)
    assert len(result.issues) == 1
    issue = result.issues[0]
    assert issue.issue_type == "MISSING_SECTION"
    assert missing in issue.description
    assert issue.snippet is None and issue.line_id is None  # document-level


def test_two_missing_sections_score_one_third():
    result = run("Jane Testperson\nSKILLS\nPython\n")

    assert result.value == pytest.approx(1 / 3)
    assert len(result.issues) == 2


def test_three_missing_sections_score_zero():
    result = run("Jane Testperson\nSummary\nA person.\n")

    assert result.value == 0
    assert len(result.issues) == 3


def test_the_word_inside_a_sentence_is_not_a_heading():
    text = "Jane Testperson\n- Ten years of experience in skills training and education.\n"

    assert len(run(text).issues) == 3


def test_heading_with_extra_text_is_not_matched():
    assert len(run(FULL.replace("EXPERIENCE", "Experience (2019 - 2024)")).issues) == 1
