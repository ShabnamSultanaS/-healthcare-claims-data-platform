"""
Pipeline orchestrator: Bronze -> Silver -> Gold (medallion architecture).

  Bronze : raw CSVs ingested as-is into DuckDB with load metadata
  Silver : quality rules applied, failing rows quarantined, data conformed
  Gold   : dimensional star schema + analytics marts built in SQL

Run:  python -m src.run_pipeline --config config/pipeline.yaml
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import pandas as pd
import yaml

from src.quality import QualityReport, apply_rules

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("pipeline")

SQL_DIR = Path(__file__).resolve().parent.parent / "sql"


def load_config(path: str) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


# ---------------------------------------------------------------- bronze
def run_bronze(con: duckdb.DuckDBPyConnection, cfg: dict) -> dict[str, pd.DataFrame]:
    """Ingest raw CSVs untouched, stamped with load metadata."""
    con.execute("CREATE SCHEMA IF NOT EXISTS bronze")
    raw_zone = Path(cfg["paths"]["raw_zone"])
    frames: dict[str, pd.DataFrame] = {}
    batch_ts = datetime.now(timezone.utc).isoformat()

    for name, ds in cfg["datasets"].items():
        df = pd.read_csv(raw_zone / ds["file"])
        df["_loaded_at"] = batch_ts
        df["_source_file"] = ds["file"]
        con.execute(f"CREATE OR REPLACE TABLE bronze.{name} AS SELECT * FROM df")
        frames[name] = df
        log.info("bronze.%-9s ingested %6d rows from %s", name, len(df), ds["file"])
    return frames


# ---------------------------------------------------------------- silver
def run_silver(con: duckdb.DuckDBPyConnection, cfg: dict,
               frames: dict[str, pd.DataFrame]) -> QualityReport:
    """Apply DQ rules, quarantine failures, conform clean data."""
    con.execute("CREATE SCHEMA IF NOT EXISTS silver")
    quarantine_zone = Path(cfg["paths"]["quarantine_zone"])
    quarantine_zone.mkdir(parents=True, exist_ok=True)
    report = QualityReport()
    clean: dict[str, pd.DataFrame] = {}

    # Order matters: members/providers first so claims can reference them.
    for name in ["members", "providers", "claims"]:
        refs = {k: set(v[k[:-1] + "_id"]) for k, v in clean.items()}  # members -> member_id
        df_clean, df_bad = apply_rules(
            frames[name], name, cfg["datasets"][name]["rules"], report,
            reference_sets=refs,
        )
        if len(df_bad):
            df_bad.to_csv(quarantine_zone / f"{name}_quarantine.csv", index=False)
        clean[name] = df_clean
        log.info("silver.%-9s %6d clean | %5d quarantined", name, len(df_clean), len(df_bad))

    # Conform: normalise casing, cast dates
    clean["members"]["plan_type"] = clean["members"]["plan_type"].str.title()
    for col in ("service_date", "submitted_date"):
        clean["claims"][col] = pd.to_datetime(clean["claims"][col])
    clean["members"]["date_of_birth"] = pd.to_datetime(clean["members"]["date_of_birth"])
    clean["members"]["enrolment_date"] = pd.to_datetime(clean["members"]["enrolment_date"])

    for name, df in clean.items():
        con.execute(f"CREATE OR REPLACE TABLE silver.{name} AS SELECT * FROM df")

    # Persist DQ report for audit
    reports_dir = Path(cfg["paths"]["reports"])
    reports_dir.mkdir(parents=True, exist_ok=True)
    dq = report.to_frame()
    dq.to_csv(reports_dir / "dq_report.csv", index=False)
    con.execute("CREATE SCHEMA IF NOT EXISTS audit")
    con.execute("CREATE OR REPLACE TABLE audit.dq_report AS SELECT * FROM dq")
    return report


# ---------------------------------------------------------------- gold
def run_gold(con: duckdb.DuckDBPyConnection) -> None:
    """Build the star schema and marts from versioned SQL files."""
    con.execute("CREATE SCHEMA IF NOT EXISTS gold")
    for sql_file in sorted((SQL_DIR / "gold").glob("*.sql")):
        con.execute(sql_file.read_text())
        log.info("gold: executed %s", sql_file.name)


def print_kpis(con: duckdb.DuckDBPyConnection) -> None:
    kpis = con.execute("SELECT * FROM gold.mart_monthly_kpis ORDER BY month DESC LIMIT 6").df()
    log.info("Latest monthly KPIs:\n%s", kpis.to_string(index=False))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config/pipeline.yaml")
    args = parser.parse_args()

    start = time.perf_counter()
    cfg = load_config(args.config)

    warehouse = Path(cfg["paths"]["warehouse"])
    warehouse.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(warehouse))

    frames = run_bronze(con, cfg)
    report = run_silver(con, cfg, frames)
    run_gold(con)
    print_kpis(con)

    elapsed = time.perf_counter() - start
    log.info("Pipeline complete in %.1fs | %d DQ rule failures quarantined",
             elapsed, report.total_failures)
    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
