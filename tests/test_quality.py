"""Unit tests for the data quality framework."""

import pandas as pd
import pytest

from src.quality import QualityReport, apply_rules


@pytest.fixture
def report():
    return QualityReport()


def test_not_null_quarantines_missing_values(report):
    df = pd.DataFrame({"county": ["Dublin", None, "Cork"]})
    rules = [{"type": "not_null", "column": "county"}]
    clean, bad = apply_rules(df, "test", rules, report)
    assert len(clean) == 2
    assert len(bad) == 1
    assert "not_null:county" in bad["_dq_failures"].iloc[0]


def test_unique_keeps_first_occurrence(report):
    df = pd.DataFrame({"id": ["A", "B", "A"]})
    rules = [{"type": "unique", "column": "id"}]
    clean, bad = apply_rules(df, "test", rules, report)
    assert list(clean["id"]) == ["A", "B"]
    assert len(bad) == 1


def test_min_value_rejects_negatives(report):
    df = pd.DataFrame({"amount": [100.0, -50.0, 0.0]})
    rules = [{"type": "min_value", "column": "amount", "threshold": 0}]
    clean, bad = apply_rules(df, "test", rules, report)
    assert len(clean) == 2
    assert bad["amount"].iloc[0] == -50.0


def test_allowed_values(report):
    df = pd.DataFrame({"status": ["APPROVED", "APRVD", "PENDING"]})
    rules = [{"type": "allowed_values", "column": "status",
              "values": ["APPROVED", "PENDING"]}]
    clean, bad = apply_rules(df, "test", rules, report)
    assert len(bad) == 1
    assert bad["status"].iloc[0] == "APRVD"


def test_date_order_flags_impossible_sequence(report):
    df = pd.DataFrame({
        "service_date": ["2025-01-10", "2025-01-10"],
        "submitted_date": ["2025-01-05", "2025-01-20"],
    })
    rules = [{"type": "date_order", "column_a": "service_date",
              "column_b": "submitted_date"}]
    clean, bad = apply_rules(df, "test", rules, report)
    assert len(bad) == 1
    assert bad["submitted_date"].iloc[0] == "2025-01-05"


def test_referential_integrity(report):
    df = pd.DataFrame({"member_id": ["MBR000001", "MBR999999"]})
    rules = [{"type": "referential", "column": "member_id", "reference": "members"}]
    clean, bad = apply_rules(df, "test", rules, report,
                             reference_sets={"members": {"MBR000001"}})
    assert len(clean) == 1
    assert bad["member_id"].iloc[0] == "MBR999999"


def test_report_pass_rate(report):
    df = pd.DataFrame({"x": [1, None, None, 1]})
    apply_rules(df, "test", [{"type": "not_null", "column": "x"}], report)
    frame = report.to_frame()
    assert frame["rows_failed"].iloc[0] == 2
    assert frame["pass_rate_pct"].iloc[0] == 50.0
