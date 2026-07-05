-- ============================================================
-- Gold layer: dimension tables (star schema)
-- ============================================================

CREATE OR REPLACE TABLE gold.dim_member AS
SELECT
    row_number() OVER (ORDER BY member_id)          AS member_key,
    member_id,
    first_name,
    last_name,
    date_of_birth,
    date_diff('year', date_of_birth, current_date)  AS age,
    CASE
        WHEN date_diff('year', date_of_birth, current_date) < 30 THEN '18-29'
        WHEN date_diff('year', date_of_birth, current_date) < 45 THEN '30-44'
        WHEN date_diff('year', date_of_birth, current_date) < 60 THEN '45-59'
        ELSE '60+'
    END                                             AS age_band,
    county,
    plan_type,
    enrolment_date,
    monthly_premium_eur
FROM silver.members;

CREATE OR REPLACE TABLE gold.dim_provider AS
SELECT
    row_number() OVER (ORDER BY provider_id)        AS provider_key,
    provider_id,
    provider_name,
    specialty,
    county,
    network_status
FROM silver.providers;

-- Conformed date dimension spanning the claims service window
CREATE OR REPLACE TABLE gold.dim_date AS
SELECT
    CAST(strftime(d, '%Y%m%d') AS INTEGER)          AS date_key,
    d                                               AS full_date,
    year(d)                                         AS year,
    quarter(d)                                      AS quarter,
    month(d)                                        AS month_num,
    strftime(d, '%Y-%m')                            AS year_month,
    dayofweek(d)                                    AS day_of_week,
    CASE WHEN dayofweek(d) IN (0, 6) THEN TRUE ELSE FALSE END AS is_weekend
FROM (
    SELECT unnest(generate_series(DATE '2024-01-01', DATE '2026-12-31', INTERVAL 1 DAY))::DATE AS d
);
