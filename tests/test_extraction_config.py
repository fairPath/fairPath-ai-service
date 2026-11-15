"""EXTRACTION_MIN_CHARS: blank means the default, and a bad value is a clear startup error."""
import os
import subprocess
import sys
from pathlib import Path

import pytest

from extraction import DEFAULT_EXTRACTION_MIN_CHARS, read_min_chars

SRC = Path(__file__).resolve().parent.parent / "src"


@pytest.mark.parametrize("raw", [None, "", "   ", "\t"])
def test_unset_or_blank_uses_the_default(raw):
    assert read_min_chars(raw) == DEFAULT_EXTRACTION_MIN_CHARS == 200


@pytest.mark.parametrize("raw, expected", [("1", 1), ("150", 150), (" 300 ", 300)])
def test_a_positive_whole_number_is_used(raw, expected):
    assert read_min_chars(raw) == expected


@pytest.mark.parametrize("raw", ["0", "-5", "abc", "12.5", "200 chars"])
def test_anything_else_is_rejected_by_name(raw):
    with pytest.raises(ValueError, match="EXTRACTION_MIN_CHARS"):
        read_min_chars(raw)


def import_extraction(value: str | None) -> subprocess.CompletedProcess:
    """A fresh interpreter, so the module-level read really runs (monkeypatching the parsed constant would not)."""
    env = {k: v for k, v in os.environ.items() if k != "EXTRACTION_MIN_CHARS"}
    if value is not None:
        env["EXTRACTION_MIN_CHARS"] = value
    env["PYTHONPATH"] = str(SRC)
    return subprocess.run(
        [sys.executable, "-c", "import extraction; print(extraction.EXTRACTION_MIN_CHARS)"],
        env=env,
        capture_output=True,
        text=True,
    )


def test_the_app_module_imports_when_the_example_value_is_left_blank():
    # `cp .env.example .env` leaves `EXTRACTION_MIN_CHARS=` blank.
    result = import_extraction("")

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "200"


def test_a_bad_value_stops_startup_with_the_variable_name():
    result = import_extraction("abc")

    assert result.returncode != 0
    assert "EXTRACTION_MIN_CHARS" in result.stderr
