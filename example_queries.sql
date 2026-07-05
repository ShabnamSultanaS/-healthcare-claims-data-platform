-- ============================================================
-- Example analytics queries against the gold layer
-- Run inside DuckDB:  duckdb warehouse/claims.duckdb
-- ============================================================

-- 1. Monthly claims trend with month-over-month growth (window function)
SELECT
    month,
    total_claims,
    total_approved_eur,
    round(100.0 * (total_approved_eur - lag(total_approved_eur) OVER (ORDER BY month))
        / nullif(lag(total_approved_eur) OVER (ORDER BY month), 0), 1) AS mom_growth_pct
FROM gold.mart_monthly_kpis
ORDER BY month;

-- 2. Top 10 most expensive procedures by average approved cost
SELECT
    procedure_code,
    count(*)                                AS claim_count,
    round(avg(approved_amount_eur), 2)      AS avg_cost_eur,
    round(sum(approved_amount_eur), 2)      AS total_cost_eur
FROM gold.fact_claims
WHERE claim_status = 'APPROVED'
GROUP BY procedure_code
HAVING count(*) >= 50
ORDER BY avg_cost_eur DESC
LIMIT 10;

-- 3. High-utilisation members: claims exceeding 3x annual premium
SELECT plan_type, age_band, count(*) AS members_over_3x
FROM gold.mart_member_utilisation
WHERE utilisation_ratio > 3
GROUP BY plan_type, age_band
ORDER BY members_over_3x DESC;

-- 4. Out-of-network cost premium by specialty
SELECT
    specialty,
    round(avg(avg_claim_cost_eur) FILTER (WHERE network_status = 'OUT_OF_NETWORK')
        - avg(avg_claim_cost_eur) FILTER (WHERE network_status = 'IN_NETWORK'), 2)
        AS oon_cost_premium_eur
FROM gold.mart_specialty_costs
GROUP BY specialty
ORDER BY oon_cost_premium_eur DESC NULLS LAST;

-- 5. Submission lag SLA breach rate by month (claims submitted > 30 days after service)
SELECT
    d.year_month AS month,
    round(100.0 * count(*) FILTER (WHERE f.submission_lag_days > 30) / count(*), 2)
        AS sla_breach_pct
FROM gold.fact_claims f
JOIN gold.dim_date d ON f.service_date_key = d.date_key
GROUP BY d.year_month
ORDER BY month;
