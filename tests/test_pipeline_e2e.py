"""End-to-end integration test: generate data, run pipeline, validate warehouse."""

import subprocess
import sys
from pathlib import Path

import duckdb
import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def warehouse(tmp_path_factory):
    """Run the full pipeline against a small dataset in a temp workspace."""
    ws = tmp_path_factory.mktemp("e2e")
    raw = ws / "data" / "raw"

    subprocess.run(
        [sys.executable, "-m", "src.generate_source_data",
         "--output-dir", str(raw),
         "--members", "500", "--providers", "50", "--claims", "5000"],
        cwd=ROOT, check=True,
    )

    # Rewrite config paths to the temp workspace
    cfg = (ROOT / "config" / "pipeline.yaml").read_text()
    cfg = cfg.replace("data/raw", str(raw))
    cfg = cfg.replace("data/quarantine", str(ws / "quarantine"))
    cfg = cfg.replace("data/reports", str(ws / "reports"))
    cfg = cfg.replace("warehouse/claims.duckdb", str(ws / "claims.duckdb"))
    cfg_path = ws / "pipeline.yaml"
    cfg_path.write_text(cfg)

    subprocess.run(
        [sys.executable, "-m", "src.run_pipeline", "--config", str(cfg_path)],
        cwd=ROOT, check=True,
    )
    con = duckdb.connect(str(ws / "claims.duckdb"), read_only=True)
    yield con
    con.close()


def test_all_layers_exist(warehouse):
    tables = {r[0] + "." + r[1] for r in warehouse.execute(
        "SELECT table_schema, table_name FROM information_schema.tables").fetchall()}
    expected = {"bronze.claims", "silver.claims", "gold.fact_claims",
                "gold.dim_member", "gold.dim_provider", "gold.dim_date",
                "gold.mart_monthly_kpis", "audit.dq_report"}
    assert expected.issubset(tables)


def test_silver_has_no_duplicate_claims(warehouse):
    dupes = warehouse.execute(
        "SELECT count(*) FROM (SELECT claim_id FROM silver.claims "
        "GROUP BY claim_id HAVING count(*) > 1)").fetchone()[0]
    assert dupes == 0


def test_silver_has_no_negative_amounts(warehouse):
    n = warehouse.execute(
        "SELECT count(*) FROM silver.claims WHERE billed_amount_eur < 0").fetchone()[0]
    assert n == 0


def test_fact_has_full_referential_integrity(warehouse):
    orphans = warehouse.execute("""
        SELECT count(*) FROM gold.fact_claims f
        LEFT JOIN gold.dim_member m USING (member_key)
        WHERE m.member_key IS NULL""").fetchone()[0]
    assert orphans == 0


def test_dq_report_recorded_failures(warehouse):
    total = warehouse.execute(
        "SELECT sum(rows_failed) FROM audit.dq_report").fetchone()[0]
    assert total > 0  # generator injects known issues


def test_monthly_kpis_are_sane(warehouse):
    row = warehouse.execute(
        "SELECT min(approval_rate_pct), max(approval_rate_pct) "
        "FROM gold.mart_monthly_kpis").fetchone()
    assert 0 <= row[0] <= 100 and 0 <= row[1] <= 100
