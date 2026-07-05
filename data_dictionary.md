# Data Dictionary

## Gold Layer — Star Schema

### gold.fact_claims (grain: one row per adjudicated claim)
| Column | Type | Description |
|---|---|---|
| claim_id | VARCHAR | Business key from claims admin system (CLM########) |
| member_key | BIGINT | FK → dim_member |
| provider_key | BIGINT | FK → dim_provider |
| service_date_key | INTEGER | FK → dim_date (yyyymmdd) |
| submitted_date_key | INTEGER | FK → dim_date (yyyymmdd) |
| procedure_code | VARCHAR | Clinical procedure code (PRC####) |
| claim_status | VARCHAR | APPROVED / REJECTED / PENDING / UNDER_REVIEW |
| billed_amount_eur | DOUBLE | Amount billed by provider |
| approved_amount_eur | DOUBLE | Amount approved for payment |
| disallowed_amount_eur | DOUBLE | Billed minus approved |
| submission_lag_days | INTEGER | Days between service and submission |

### gold.dim_member
| Column | Type | Description |
|---|---|---|
| member_key | BIGINT | Surrogate key |
| member_id | VARCHAR | Business key (MBR######) |
| age / age_band | INT / VARCHAR | Derived from date_of_birth |
| county | VARCHAR | Irish county of residence |
| plan_type | VARCHAR | Essential / Standard / Premium / Corporate |
| monthly_premium_eur | DOUBLE | Current monthly premium |

### gold.dim_provider
| Column | Type | Description |
|---|---|---|
| provider_key | BIGINT | Surrogate key |
| provider_id | VARCHAR | Business key (PRV####) |
| specialty | VARCHAR | Clinical specialty |
| network_status | VARCHAR | IN_NETWORK / OUT_OF_NETWORK |

### gold.dim_date
Standard conformed date dimension, 2024-01-01 → 2026-12-31, with year/quarter/month, year_month, and weekend flag.

## Marts
- **mart_monthly_kpis** — claims volume, billed/approved totals, approval rate, avg submission lag, payout ratio by month
- **mart_specialty_costs** — approved claim counts and costs by specialty × network status
- **mart_member_utilisation** — per-member approved spend vs annualised premium (utilisation ratio)

## Audit
- **audit.dq_report** — one row per rule per run: rows checked, rows failed, pass rate %
- **Quarantine zone** — CSVs per dataset with `_dq_failures` reason codes
