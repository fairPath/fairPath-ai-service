import re

from presidio_analyzer import AnalyzerEngine, Pattern, PatternRecognizer, RecognizerResult
from presidio_analyzer.nlp_engine import NlpEngineProvider
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig

# Load the NLP model once per service process, not once per resume request.
nlp_engine = NlpEngineProvider(
    nlp_configuration={
        "nlp_engine_name": "spacy",
        "models": [{"lang_code": "en", "model_name": "en_core_web_sm"}],
    }
).create_engine()
pii_analyzer = AnalyzerEngine(nlp_engine=nlp_engine, supported_languages=["en"])
pii_anonymizer = AnonymizerEngine()
address_recognizer = PatternRecognizer(
    supported_entity="ADDRESS",
    patterns=[
        Pattern(
            name="us_street_address",
            regex=(
                r"(?i)\b\d{1,6}\s+(?:[NSEW]\.?,?\s+)?"
                r"(?:[A-Z0-9.'#-]+\s+){1,5}"
                r"(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Lane|Ln|"
                r"Drive|Dr|Court|Ct|Way|Place|Pl|Parkway|Pkwy)\b"
                r"(?:,?\s*(?:Apt|Unit|Suite|Ste|#)\s*[\w-]+)?"
            ),
            score=0.75,
        )
    ],
)
pii_analyzer.registry.add_recognizer(address_recognizer)
PII_ENTITIES = ["PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER", "URL", "ADDRESS"]
NAME_TOKEN = r"(?:[A-Z][A-Za-z]*|[A-Z]{2,})(?:[-'][A-Z]?[A-Za-z]+|[-'][A-Z]+)?"
NAME_LINE_PATTERN = re.compile(
    rf"(?P<name>{NAME_TOKEN}(?:\s+{NAME_TOKEN}){{1,5}})(?:\s*\(({NAME_TOKEN})\))?"
)
RESUME_ROLE_WORDS = {
    "engineer", "developer", "designer", "manager", "analyst", "architect",
    "consultant", "scientist", "intern", "student", "resume", "curriculum",
}
PII_OPERATORS = {
    "DEFAULT": OperatorConfig("replace"),
    "PERSON": OperatorConfig("replace", {"new_value": "[PERSON]"}),
    "EMAIL_ADDRESS": OperatorConfig("replace", {"new_value": "[EMAIL]"}),
    "PHONE_NUMBER": OperatorConfig("replace", {"new_value": "[PHONE]"}),
    "URL": OperatorConfig("replace", {"new_value": "[URL]"}),
    "ADDRESS": OperatorConfig("replace", {"new_value": "[ADDRESS]"}),
}


def redact_pii(resume_text: str) -> str:
    findings = pii_analyzer.analyze(
        text=resume_text,
        entities=PII_ENTITIES,
        language="en",
    )
    # Redact person names only when they appear as standalone lines near the
    # beginning or end of the resume. This avoids person-like terms in prose.
    findings = [
        finding
        for finding in findings
        if finding.entity_type != "PERSON"
        and not (
            finding.entity_type == "URL"
            and resume_text[finding.start:finding.end].casefold() == "java.net"
            and resume_text[max(0, finding.start - 5):finding.start].casefold().endswith("java ")
        )
    ]

    lines = resume_text.splitlines(keepends=True)
    nonempty_line_indexes = [index for index, line in enumerate(lines) if line.strip()]
    edge_line_indexes = set(nonempty_line_indexes[:5] + nonempty_line_indexes[-5:])
    offset = 0
    for index, raw_line in enumerate(lines):
        line = raw_line.rstrip("\r\n").lstrip(" \t•·-*—–")
        if index in edge_line_indexes:
            name_match = NAME_LINE_PATTERN.fullmatch(line)
            if name_match:
                candidate = name_match.group(0)
                words = set(re.findall(r"[A-Za-z]+", candidate.casefold()))
                if not (words & RESUME_ROLE_WORDS):
                    start = offset + raw_line.find(candidate)
                    findings.append(
                        RecognizerResult(
                            entity_type="PERSON",
                            start=start,
                            end=start + len(candidate),
                            score=0.95,
                        )
                    )
        offset += len(raw_line)

    return pii_anonymizer.anonymize(
        text=resume_text,
        analyzer_results=findings,
        operators=PII_OPERATORS,
    ).text
