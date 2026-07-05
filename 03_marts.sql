-- ============================================================
-- Gold layer: analytics marts (BI-ready aggregates)
-- ============================================================

-- Monthly operational KPIs
CREATE OR REPLACE TABLE gold.mart_monthly_kpis AS
SELECT
    d.year_month                                                        AS month,
    count(*)                                                            AS total_claims,
    round(sum(f.billed_amount_eur), 2)                                  AS total_billed_eur,
    round(sum(f.approved_amount_eur), 2)                                AS total_approved_eur,
    round(100.0 * count(*) FILTER (WHERE f.claim_status = 'APPROVED')
        / count(*), 2)                                                  AS approval_rate_pct,
    round(avg(f.submission_lag_days), 1)                                AS avg_submission_lag_days,
    round(100.0 * sum(f.approved_amount_eur)
        / nullif(sum(f.billed_amount_eur), 0), 2)                       AS payout_ratio_pct
FROM gold.fact_claims f
JOIN gold.dim_date d ON f.service_date_key = d.date_key
GROUP BY d.year_month;

-- Claims cost by provider specialty (top cost drivers)
CREATE OR REPLACE TABLE gold.mart_specialty_costs AS
SELECT
    p.specialty,
    p.network_status,
    count(*)                                        AS claim_count,
    round(sum(f.approved_amount_eur), 2)            AS total_approved_eur,
    round(avg(f.approved_amount_eur), 2)            AS avg_claim_cost_eur
FROM gold.fact_claims f
JOIN gold.dim_provider p ON f.provider_key = p.provider_key
WHERE f.claim_status = 'APPROVED'
GROUP BY p.specialty, p.network_status;

-- Member-level utilisation vs premium (loss-ratio style view)
CREATE OR REPLACE TABLE gold.mart_member_utilisation AS
SELECT
    m.member_key,
    m.plan_type,
    m.age_band,
    m.county,
    count(f.claim_id)                                       AS claims_count,
    round(coalesce(sum(f.approved_amount_eur), 0), 2)       AS total_claimed_eur,
    round(m.monthly_premium_eur * 12, 2)                    AS annualised_premium_eur,
    round(coalesce(sum(f.approved_amount_eur), 0)
        / nullif(m.monthly_premium_eur * 12, 0), 2)         AS utilisation_ratio
FROM gold.dim_member m
LEFT JOIN gold.fact_claims f
    ON m.member_key = f.member_key AND f.claim_status = 'APPROVED'
GROUP BY m.member_key, m.plan_type, m.age_band, m.county, m.monthly_premium_eur;
