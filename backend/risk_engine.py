"""
risk_engine.py
--------------
STEP 3 of the SIH 2026 (PS 26103) MVP pipeline.

Reads the STEP 2 output:
    data/project_metrics.csv

For each project (using its most recent available report month),
computes four rule-based (non-ML) sub-risk scores plus a weighted
overall Risk Score (0-100):

    Progress Risk  : 35%
    Schedule Risk  : 30%
    Cost Risk      : 25%
    Trend Risk     : 10%

Risk levels:
    0-30  = LOW
    31-60 = MEDIUM
    61-100 = HIGH

A plain-language explanation is generated for every project, listing
only the reasons actually supported by that project's data (nothing is
invented; if a sub-risk cannot be computed because the underlying
field is missing, this is stated explicitly and that weight is left
out of the overall score, whose remaining weights are re-normalised).

Output:
    data/project_risk.csv

Usage:
    python3 risk_engine.py --data-dir <dir_with_project_metrics_csv> --out-dir <output_dir>
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

WEIGHTS = {
    "progress_risk": 0.35,
    "schedule_risk": 0.30,
    "cost_risk": 0.25,
    "trend_risk": 0.10,
}


# ---------------------------------------------------------------------------
# Sub-risk scoring (rule-based buckets, calibrated from the actual
# April-July metric distribution — no ML, no invented thresholds beyond
# simple, explainable cutoffs)
# ---------------------------------------------------------------------------

def score_progress_risk(gap):
    """Based on progress_gap = expected_progress_pct - physical_progress."""
    if pd.isna(gap):
        return np.nan
    if gap <= 0:
        return 0.0
    if gap <= 10:
        return 25.0
    if gap <= 25:
        return 50.0
    if gap <= 50:
        return 75.0
    return 100.0


def score_schedule_risk(delay_months):
    """
    Based on schedule_delay_months (revised - original completion date).
    NaN means no completion-date revision is recorded in the source data
    -> scored as 0 (no evidence of slippage), flagged separately in the
    explanation as "no revision recorded" rather than treated as a delay.
    """
    if pd.isna(delay_months):
        return 0.0
    if delay_months <= 0:
        return 0.0
    if delay_months <= 6:
        return 30.0
    if delay_months <= 12:
        return 50.0
    if delay_months <= 24:
        return 75.0
    return 100.0


def score_cost_risk(overrun_pct):
    """Based on cost_overrun_pct."""
    if pd.isna(overrun_pct):
        return np.nan
    if overrun_pct <= 0:
        return 0.0
    if overrun_pct <= 5:
        return 20.0
    if overrun_pct <= 15:
        return 40.0
    if overrun_pct <= 30:
        return 65.0
    if overrun_pct <= 60:
        return 85.0
    return 100.0


def score_trend_risk(velocity):
    """
    Based on monthly_progress_velocity (progress points gained per month).
    NaN when there's no prior-month snapshot to compare against.
    """
    if pd.isna(velocity):
        return np.nan
    if velocity >= 2:
        return 0.0
    if velocity >= 1:
        return 25.0
    if velocity > 0:
        return 50.0
    if velocity == 0:
        return 75.0
    return 100.0


def risk_level(score):
    if pd.isna(score):
        return "UNKNOWN"
    if score <= 30:
        return "LOW"
    if score <= 60:
        return "MEDIUM"
    return "HIGH"


def weighted_overall_score(row):
    """
    Weighted average of available sub-risks only; weights of any missing
    (NaN) sub-risk are dropped and the remaining weights re-normalised so
    the score always reflects only the data that actually exists.
    """
    total_weight = 0.0
    total_score = 0.0
    for col, w in WEIGHTS.items():
        val = row[col]
        if pd.notna(val):
            total_score += val * w
            total_weight += w
    if total_weight == 0:
        return np.nan
    return round(total_score / total_weight, 2)


# ---------------------------------------------------------------------------
# Explanation generation
# ---------------------------------------------------------------------------

def build_explanation(row):
    lines = []

    # Progress
    gap = row["progress_gap"]
    if pd.isna(gap):
        lines.append("Progress risk could not be assessed (missing start or completion date).")
    elif gap > 10:
        lines.append(
            f"Physical progress ({row['physical_progress']:.1f}%) is {gap:.1f} points "
            f"below expected progress ({row['expected_progress_pct']:.1f}%)."
        )
    elif gap <= 0:
        lines.append(
            f"Physical progress ({row['physical_progress']:.1f}%) is on track or ahead of "
            f"expected progress ({row['expected_progress_pct']:.1f}%)."
        )

    # Schedule
    delay = row["schedule_delay_months"]
    if pd.isna(delay):
        lines.append("No completion-date revision recorded (schedule risk based on original plan only).")
    elif delay > 0:
        lines.append(
            f"Completion date has been revised by {delay:.0f} month(s) "
            f"(from {row['original_completion_date']} to {row['revised_completion_date']})."
        )
    else:
        lines.append("Completion date has not slipped versus the original plan.")

    # Cost
    overrun = row["cost_overrun_pct"]
    if pd.isna(overrun):
        lines.append("Cost risk could not be assessed (missing original cost).")
    elif overrun > 5:
        lines.append(
            f"Cost overrun of {overrun:.1f}% "
            f"(original Rs. {row['original_cost']:.2f} Cr -> revised Rs. {row['revised_cost']:.2f} Cr)."
        )
    else:
        lines.append("Cost is within (or close to) the originally approved budget.")

    # Trend
    velocity = row["monthly_progress_velocity"]
    if pd.isna(velocity):
        lines.append("Recent progress trend could not be assessed (no prior month to compare).")
    elif velocity <= 0:
        lines.append("Recent progress growth is stalled or negative (no measurable gain last month).")
    elif velocity < 1:
        lines.append(f"Recent progress growth is low (~{velocity:.2f} points/month).")
    else:
        lines.append(f"Recent progress growth is healthy (~{velocity:.2f} points/month).")

    return " | ".join(lines)


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def compute_risk(metrics: pd.DataFrame) -> pd.DataFrame:
    # Use the most recent available report month per project as "current state"
    latest = (
        metrics.sort_values(["project_id", "report_month"])
        .groupby("project_id", as_index=False)
        .tail(1)
        .reset_index(drop=True)
    )

    latest["progress_risk"] = latest["progress_gap"].apply(score_progress_risk)
    latest["schedule_risk"] = latest["schedule_delay_months"].apply(score_schedule_risk)
    latest["cost_risk"] = latest["cost_overrun_pct"].apply(score_cost_risk)
    latest["trend_risk"] = latest["monthly_progress_velocity"].apply(score_trend_risk)

    latest["risk_score"] = latest.apply(weighted_overall_score, axis=1)
    latest["risk_level"] = latest["risk_score"].apply(risk_level)
    latest["risk_explanation"] = latest.apply(build_explanation, axis=1)

    output_cols = [
        "project_id", "project_name", "agency", "state", "report_month",
        "risk_score", "risk_level",
        "progress_risk", "schedule_risk", "cost_risk", "trend_risk",
        "risk_explanation",
    ]
    return latest[output_cols]


def main():
    parser = argparse.ArgumentParser(description="Compute PAIMANA project risk scores.")
    parser.add_argument("--data-dir", required=True, help="Directory containing project_metrics.csv")
    parser.add_argument("--out-dir", required=True, help="Directory to write project_risk.csv to")
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    metrics_path = data_dir / "project_metrics.csv"
    if not metrics_path.exists():
        print(f"Missing required file: {metrics_path}", file=sys.stderr)
        sys.exit(1)

    metrics = pd.read_csv(metrics_path, dtype={"report_month": str})
    risk_df = compute_risk(metrics)

    out_path = out_dir / "project_risk.csv"
    risk_df.to_csv(out_path, index=False)

    print("=== STEP 3 RISK ENGINE SUMMARY ===")
    print(f"Total projects scored: {len(risk_df)}")
    print("\nRisk level distribution:")
    print(risk_df["risk_level"].value_counts().to_string())
    print(f"\nWrote: {out_path}")

    print("\n=== 5 REAL PROJECTS - RISK SCORES & EXPLANATIONS ===")
    # Pick 5 projects spanning different risk levels for a meaningful demo
    sample = pd.concat([
        risk_df[risk_df["risk_level"] == "HIGH"].head(2),
        risk_df[risk_df["risk_level"] == "MEDIUM"].head(2),
        risk_df[risk_df["risk_level"] == "LOW"].head(1),
    ])
    if len(sample) < 5:
        sample = risk_df.head(5)

    for _, row in sample.iterrows():
        print(f"\nProject ID: {row['project_id']} - {row['project_name']}")
        print(f"  State/Agency : {row['state']} / {row['agency']}")
        print(f"  Report month : {row['report_month']}")
        print(f"  RISK SCORE   : {row['risk_score']}  -> {row['risk_level']}")
        print(f"  Sub-scores   : progress={row['progress_risk']}, schedule={row['schedule_risk']}, "
              f"cost={row['cost_risk']}, trend={row['trend_risk']}")
        print(f"  Explanation  :")
        for part in row["risk_explanation"].split(" | "):
            print(f"    - {part}")


if __name__ == "__main__":
    main()
