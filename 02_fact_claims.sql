-- ============================================================
-- Gold layer: claims fact table
-- Grain: one row per adjudicated claim
-- ============================================================

CREATE OR REPLACE TABLE gold.fact_claims AS
SELECT
    c.claim_id,
    m.member_key,
    p.provider_key,
    CAST(strftime(c.service_date,   '%Y%m%d') AS INTEGER)  AS service_date_key,
    CAST(strftime(c.submitted_date, '%Y%m%d') AS INTEGER)  AS submitted_date_key,
    c.procedure_code,
    c.claim_status,
    c.billed_amount_eur,
    c.approved_amount_eur,
    c.billed_amount_eur - c.approved_amount_eur            AS disallowed_amount_eur,
    date_diff('day', c.service_date, c.submitted_date)     AS submission_lag_days
FROM silver.claims c
JOIN gold.dim_member   m ON c.member_id   = m.member_id
JOIN gold.dim_provider p ON c.provider_id = p.provider_id;
