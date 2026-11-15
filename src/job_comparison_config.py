"""Versioned configuration for the resume-to-job hiring-fit rubric."""

COMPARISON_PROMPT_VERSION = "0.3.0"

# Relative importance, deliberately separate from prompt/endpoint logic.
HIRING_FIT_WEIGHTS = {"skill_match_score": 50, "experience_match_score": 50}
MAX_RESUME_ADVICE_SENTENCES = 2
MAX_RESUME_ADVICE_CHARS = 400

HIRING_FIT_BANDS = [
    (90, 100, "exceptional fit: strong evidence across the core role, responsibilities and level"),
    (75, 89, "strong candidate: most core requirements met; remaining gaps are reasonably learnable"),
    (60, 74, "credible candidate: relevant background and meaningful overlap, with some material gaps"),
    (40, 59, "stretch candidate: useful transferable experience, but substantial gaps in role or scope"),
    (20, 39, "weak fit: limited evidence for the essential work or a major seniority mismatch"),
    (0, 19, "largely unrelated: little evidence for the role's essential work"),
]
