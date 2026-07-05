"""
Synthetic source data generator for the claims data platform.

Simulates three upstream systems landing files in a raw zone:
  - Membership system   -> members.csv
  - Provider registry   -> providers.csv
  - Claims admin system -> claims.csv

Deliberately injects realistic data quality issues (duplicates, nulls,
bad codes, negative amounts, orphan foreign keys, inconsistent casing)
so the downstream quality framework has real work to do.
"""

from __future__ import annotations

import argparse
import random
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

SEED = 42

FIRST_NAMES = ["Aoife", "Liam", "Saoirse", "Conor", "Niamh", "Sean", "Emma",
               "Jack", "Grace", "Cian", "Maria", "David", "Priya", "Tomasz",
               "Fatima", "Igor", "Chen", "Amara", "Lucas", "Sofia"]
LAST_NAMES = ["Murphy", "Kelly", "O'Brien", "Walsh", "Ryan", "Byrne",
              "McCarthy", "Doyle", "Kennedy", "Lynch", "Nowak", "Sharma",
              "Ivanov", "Garcia", "Okafor", "Wang", "Ali", "Silva"]
COUNTIES = ["Dublin", "Cork", "Galway", "Limerick", "Waterford", "Kildare",
            "Meath", "Wicklow", "Louth", "Kerry"]
PLAN_TYPES = ["Essential", "Standard", "Premium", "Corporate"]
SPECIALTIES = ["General Practice", "Cardiology", "Orthopaedics", "Dermatology",
               "Physiotherapy", "Radiology", "Oncology", "Maternity",
               "Ophthalmology", "ENT"]
CLAIM_STATUSES = ["APPROVED", "REJECTED", "PENDING", "UNDER_REVIEW"]
PROCEDURE_CODES = [f"PRC{str(i).zfill(4)}" for i in range(1, 121)]


def _random_date(start: date, end: date, rng: random.Random) -> date:
    return start + timedelta(days=rng.randint(0, (end - start).days))


def generate_members(n: int, rng: random.Random) -> pd.DataFrame:
    rows = []
    for i in range(1, n + 1):
        rows.append({
            "member_id": f"MBR{str(i).zfill(6)}",
            "first_name": rng.choice(FIRST_NAMES),
            "last_name": rng.choice(LAST_NAMES),
            "date_of_birth": _random_date(date(1945, 1, 1), date(2005, 12, 31), rng).isoformat(),
            "county": rng.choice(COUNTIES),
            "plan_type": rng.choice(PLAN_TYPES),
            "enrolment_date": _random_date(date(2018, 1, 1), date(2025, 6, 30), rng).isoformat(),
            "monthly_premium_eur": round(rng.uniform(45, 320), 2),
        })
    df = pd.DataFrame(rows)

    # --- inject quality issues ---
    # duplicates
    df = pd.concat([df, df.sample(frac=0.02, random_state=SEED)], ignore_index=True)
    # missing counties
    df.loc[df.sample(frac=0.015, random_state=SEED).index, "county"] = None
    # inconsistent casing in plan_type
    idx = df.sample(frac=0.05, random_state=SEED + 1).index
    df.loc[idx, "plan_type"] = df.loc[idx, "plan_type"].str.lower()
    return df


def generate_providers(n: int, rng: random.Random) -> pd.DataFrame:
    rows = []
    for i in range(1, n + 1):
        rows.append({
            "provider_id": f"PRV{str(i).zfill(4)}",
            "provider_name": f"{rng.choice(LAST_NAMES)} {rng.choice(['Clinic', 'Medical Centre', 'Hospital', 'Practice'])}",
            "specialty": rng.choice(SPECIALTIES),
            "county": rng.choice(COUNTIES),
            "network_status": rng.choices(["IN_NETWORK", "OUT_OF_NETWORK"], weights=[0.8, 0.2])[0],
        })
    df = pd.DataFrame(rows)
    # missing specialty on a few rows
    df.loc[df.sample(frac=0.03, random_state=SEED).index, "specialty"] = None
    return df


def generate_claims(n: int, members: pd.DataFrame, providers: pd.DataFrame,
                    rng: random.Random) -> pd.DataFrame:
    member_ids = members["member_id"].unique().tolist()
    provider_ids = providers["provider_id"].tolist()
    rows = []
    for i in range(1, n + 1):
        service = _random_date(date(2024, 1, 1), date(2026, 6, 30), rng)
        submitted = service + timedelta(days=rng.randint(0, 45))
        billed = round(rng.uniform(40, 8500), 2)
        status = rng.choices(CLAIM_STATUSES, weights=[0.68, 0.14, 0.10, 0.08])[0]
        approved = round(billed * rng.uniform(0.5, 1.0), 2) if status == "APPROVED" else 0.0
        rows.append({
            "claim_id": f"CLM{str(i).zfill(8)}",
            "member_id": rng.choice(member_ids),
            "provider_id": rng.choice(provider_ids),
            "procedure_code": rng.choice(PROCEDURE_CODES),
            "service_date": service.isoformat(),
            "submitted_date": submitted.isoformat(),
            "billed_amount_eur": billed,
            "approved_amount_eur": approved,
            "claim_status": status,
        })
    df = pd.DataFrame(rows)

    # --- inject quality issues ---
    # duplicate claim submissions
    df = pd.concat([df, df.sample(frac=0.01, random_state=SEED)], ignore_index=True)
    # negative billed amounts (system reversal artefacts)
    idx = df.sample(frac=0.004, random_state=SEED).index
    df.loc[idx, "billed_amount_eur"] = -df.loc[idx, "billed_amount_eur"]
    # orphan member references (member not in membership extract)
    idx = df.sample(frac=0.006, random_state=SEED + 2).index
    df.loc[idx, "member_id"] = "MBR999999"
    # service date after submitted date (impossible sequence)
    idx = df.sample(frac=0.003, random_state=SEED + 3).index
    df.loc[idx, "submitted_date"] = (
        pd.to_datetime(df.loc[idx, "service_date"]) - pd.Timedelta(days=10)
    ).dt.date.astype(str)
    # invalid status codes
    idx = df.sample(frac=0.002, random_state=SEED + 4).index
    df.loc[idx, "claim_status"] = "APRVD"
    return df


def main(output_dir: str, n_members: int, n_providers: int, n_claims: int) -> None:
    rng = random.Random(SEED)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    members = generate_members(n_members, rng)
    providers = generate_providers(n_providers, rng)
    claims = generate_claims(n_claims, members, providers, rng)

    members.to_csv(out / "members.csv", index=False)
    providers.to_csv(out / "providers.csv", index=False)
    claims.to_csv(out / "claims.csv", index=False)

    print(f"Generated {len(members):,} members, {len(providers):,} providers, "
          f"{len(claims):,} claims -> {out}/")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate synthetic source data")
    parser.add_argument("--output-dir", default="data/raw")
    parser.add_argument("--members", type=int, default=5000)
    parser.add_argument("--providers", type=int, default=300)
    parser.add_argument("--claims", type=int, default=50000)
    args = parser.parse_args()
    main(args.output_dir, args.members, args.providers, args.claims)
