"""
Config-driven data quality framework.

Rules are declared in config/pipeline.yaml per dataset. Each rule is
evaluated against a DataFrame; failing rows are quarantined rather than
silently dropped, and every run produces an auditable DQ report.

Supported rule types:
  - not_null          : column must not be null
  - unique            : column values must be unique (dupes quarantined)
  - allowed_values    : column value must be in a whitelist
  - min_value         : numeric column must be >= threshold
  - regex_match       : column must match a pattern
  - date_order        : column_a must be <= column_b
  - referential       : column values must exist in a reference set
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import pandas as pd


@dataclass
class RuleResult:
    dataset: str
    rule_type: str
    column: str
    description: str
    rows_checked: int
    rows_failed: int

    @property
    def pass_rate(self) -> float:
        if self.rows_checked == 0:
            return 1.0
        return 1 - (self.rows_failed / self.rows_checked)


@dataclass
class QualityReport:
    results: list[RuleResult] = field(default_factory=list)

    def add(self, result: RuleResult) -> None:
        self.results.append(result)

    def to_frame(self) -> pd.DataFrame:
        return pd.DataFrame([{
            "dataset": r.dataset,
            "rule_type": r.rule_type,
            "column": r.column,
            "description": r.description,
            "rows_checked": r.rows_checked,
            "rows_failed": r.rows_failed,
            "pass_rate_pct": round(r.pass_rate * 100, 2),
        } for r in self.results])

    @property
    def total_failures(self) -> int:
        return sum(r.rows_failed for r in self.results)


def _failing_mask(df: pd.DataFrame, rule: dict,
                  reference_sets: dict[str, set] | None) -> pd.Series:
    """Return a boolean mask of rows that FAIL the rule."""
    rtype = rule["type"]
    col = rule.get("column", "")

    if rtype == "not_null":
        return df[col].isna()

    if rtype == "unique":
        return df.duplicated(subset=[col], keep="first")

    if rtype == "allowed_values":
        allowed = set(rule["values"])
        return ~df[col].isin(allowed)

    if rtype == "min_value":
        return pd.to_numeric(df[col], errors="coerce") < rule["threshold"]

    if rtype == "regex_match":
        pattern = re.compile(rule["pattern"])
        return ~df[col].astype(str).str.match(pattern)

    if rtype == "date_order":
        a = pd.to_datetime(df[rule["column_a"]], errors="coerce")
        b = pd.to_datetime(df[rule["column_b"]], errors="coerce")
        return a > b

    if rtype == "referential":
        ref = reference_sets[rule["reference"]] if reference_sets else set()
        return ~df[col].isin(ref)

    raise ValueError(f"Unknown rule type: {rtype}")


def apply_rules(df: pd.DataFrame, dataset: str, rules: list[dict],
                report: QualityReport,
                reference_sets: dict[str, set] | None = None,
                ) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Evaluate all rules for a dataset.

    Returns (clean_df, quarantined_df). A row failing any rule is
    quarantined with the reasons recorded in `_dq_failures`.
    """
    failure_reasons = pd.Series([""] * len(df), index=df.index)

    for rule in rules:
        mask = _failing_mask(df, rule, reference_sets)
        col = rule.get("column") or f"{rule.get('column_a')}->{rule.get('column_b')}"
        report.add(RuleResult(
            dataset=dataset,
            rule_type=rule["type"],
            column=col,
            description=rule.get("description", ""),
            rows_checked=len(df),
            rows_failed=int(mask.sum()),
        ))
        failure_reasons[mask] += f"{rule['type']}:{col};"

    failed_mask = failure_reasons != ""
    quarantined = df[failed_mask].copy()
    quarantined["_dq_failures"] = failure_reasons[failed_mask]
    clean = df[~failed_mask].copy()
    return clean, quarantined
