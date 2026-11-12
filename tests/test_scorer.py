"""The Scorer: Category Score = round(100 × Σ weight·value / Σ weight).

Expected values are worked by hand from the spec's starting weights:
Parseability: multi_column 3, unreadable_characters 3, missing_sections 2, table_content 2
Formatting:   missing_contact 5, too_long 3, inconsistent_dates 2
Writing:      impact 3, clarity 3, spelling 2, grammar 2
"""
import pytest

from scorer import score


def test_category_with_no_components_scores_100():
    scores = score({})

    assert scores.model_dump() == {
        "formatting": 100,
        "parseability": 100,
        "writing": 100,
        "overall": 100,
    }


def test_failed_presence_check_zeroes_its_category_when_it_is_the_only_component():
    scores = score({"missing_contact": 0})

    assert scores.formatting == 0
    assert scores.parseability == 100
    assert scores.writing == 100
    # (0 + 100 + 100) / 3 = 66.67
    assert scores.overall == 67


def test_weights_are_relative_within_a_category():
    # 100 × (5·1 + 3·0) / (5 + 3) = 62.5, rounded half up
    scores = score({"missing_contact": 1, "too_long": 0})

    assert scores.formatting == 63


def test_not_applicable_components_drop_out_of_both_sums():
    # clarity is not applicable: 100 × (3·0.5 + 2·1 + 2·0) / (3 + 2 + 2) = 50
    scores = score({"impact": 0.5, "clarity": None, "spelling": 1, "grammar": 0})

    assert scores.writing == 50


def test_category_whose_components_are_all_not_applicable_scores_100():
    scores = score({"impact": None, "clarity": None})

    assert scores.writing == 100


def test_unknown_component_is_a_config_error():
    with pytest.raises(KeyError):
        score({"not_a_component": 1})
