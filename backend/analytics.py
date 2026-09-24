"""
analytics.py
------------
STEP 2 of the SIH 2026 (PS 26103) MVP pipeline.

Reads the cleaned STEP 1 outputs:
    data/project_snapshots.csv   (one row per project per report month)
    data/projects_latest.csv     (one row per project, latest month only)

Computes, per project (and per project-month where applicable):
    - cost overrun %
    - schedule delay (months)
    - expected progress %
    - progress gap
    - monthly progress velocity

Also runs data-quality validation (numeric columns, dates, missing
values, duplicates, and month-to-month history continuity April-July)
and writes a processed dataset:
    data/project_metrics.csv

No values are invented — metrics that cannot be computed because a
required source field is missing are left blank (NaN), not filled.

Usage:
    python3 analytics.py --data-dir <dir_with_snapshots_csvs> --out-dir <output_dir>
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

EXPECTED_MONTHS = ["2026-04", "2026-05", "2026-06", "2026-07"]

DATE_COLS = ["start_date", "original_completion_date", "revised_completion_date"]
NUMERIC_COLS = ["original_cost", "revised_cost", "expenditure", "physical_progress"]


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def parse_mm_yyyy(series: pd.Series) -> pd.Series:
    """
    Parse 'MM/YYYY' strings into Timestamps (first day of month).
    Invalid / missing values become NaT - never invented.
    """
    return pd.to_datetime(series, format="%m/%Y", errors="coerce")


def month_diff(later: pd.Series, earlier: pd.Series) -> pd.Series:
    """Whole-month difference between two Timestamp series (later - earlier)."""
    return (
        (later.dt.year - earlier.dt.year) * 12
        + (later.dt.month - earlier.dt.month)
    ).astype("float")


# ---------------------------------------------------------------------------
# Metric calculations
# ---------------------------------------------------------------------------

def compute_cost_overrun_pct(df: pd.DataFrame) -> pd.Series:
    """(revised_cost - original_cost) / original_cost * 100."""
    with np.errstate(divide="ignore", invalid="ignore"):
        pct = (df["revised_cost"] - df["original_cost"]) / df["original_cost"] * 100
    pct = pct.where(df["original_cost"].notna() & (df["original_cost"] != 0))
    return pct.round(2)


def compute_schedule_delay_months(df: pd.DataFrame) -> pd.Series:
    """
    Months of slippage = revised_completion_date - original_completion_date.
    NaN when either date is missing (e.g. no revision recorded).
    """
    delay = month_diff(df["_revised_completion_dt"], df["_original_completion_dt"])
    return delay


def compute_expected_progress_pct(df: pd.DataFrame, as_of: pd.Series) -> pd.Series:
    """
    Linear expected progress based on elapsed time vs planned duration:
        elapsed_months   = as_of - start_date
        planned_duration = original_completion_date - start_date
        expected_progress = elapsed_months / planned_duration * 100
    Clipped to [0, 100]. NaN when start_date or original_completion_date
    is missing, or planned_duration <= 0.
    """
    planned_duration = month_diff(df["_original_completion_dt"], df["_start_dt"])
    elapsed = month_diff(as_of, df["_start_dt"])

    expected = elapsed / planned_duration * 100
    expected = expected.where(planned_duration.notna() & (planned_duration > 0))
    expected = expected.clip(lower=0, upper=100)
    return expected.round(2)


def compute_progress_gap(df: pd.DataFrame) -> pd.Series:
    """expected_progress - actual physical_progress. Positive => behind schedule."""
    return (df["expected_progress_pct"] - df["physical_progress"]).round(2)


def compute_monthly_velocity(snapshots: pd.DataFrame) -> pd.DataFrame:
    """
    For each project, compute month-over-month change in physical_progress
    between consecutive available report_months (velocity = progress points
    gained per month). First available month per project has no prior
    month to compare to, so velocity is NaN there.
    """
    snapshots = snapshots.sort_values(["project_id", "_report_month_dt"]).copy()
    grouped = snapshots.groupby("project_id")

    prev_progress = grouped["physical_progress"].shift(1)
    prev_month_dt = grouped["_report_month_dt"].shift(1)

    months_gap = (
        (snapshots["_report_month_dt"].dt.year - prev_month_dt.dt.year) * 12
        + (snapshots["_report_month_dt"].dt.month - prev_month_dt.dt.month)
    ).astype("float")

    progress_delta = snapshots["physical_progress"] - prev_progress
    velocity = (progress_delta / months_gap).round(2)
    # velocity undefined if there's no previous month, or months_gap is 0
    velocity = velocity.where(months_gap.notna() & (months_gap > 0))

    snapshots["monthly_progress_velocity"] = velocity
    return snapshots


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate(snapshots: pd.DataFrame) -> None:
    print("=== STEP 2 DATA VALIDATION ===")

    # 1. Numeric columns
    print("\n-- Numeric column check --")
    for col in NUMERIC_COLS:
        non_numeric = pd.to_numeric(snapshots[col], errors="coerce").isna() & snapshots[col].notna()
        print(f"{col}: dtype={snapshots[col].dtype}, non-numeric-but-present={non_numeric.sum()}")

    # 2. Dates
    print("\n-- Date parse check (MM/YYYY) --")
    for col in DATE_COLS:
        parsed = parse_mm_yyyy(snapshots[col])
        unparseable = parsed.isna() & snapshots[col].notna()
        print(f"{col}: unparseable-but-present={unparseable.sum()}, missing={snapshots[col].isna().sum()}")

    # 3. Missing values
    print("\n-- Missing values per column --")
    print(snapshots.isna().sum().to_string())

    # 4. Duplicate project_id + report_month
    dup_mask = snapshots.duplicated(subset=["project_id", "report_month"], keep=False)
    print(f"\n-- Duplicate (project_id, report_month) rows: {dup_mask.sum()} --")

    # 5. April-July project history continuity
    print("\n-- April-July history continuity --")
    months_present = snapshots.groupby("project_id")["report_month"].apply(lambda s: set(s))
    full_history = months_present.apply(lambda s: set(EXPECTED_MONTHS).issubset(s))
    print(f"Projects present in all 4 months (Apr-Jul): {full_history.sum()} / {len(full_history)}")
    counts = months_present.apply(len).value_counts().sort_index()
    print("Distribution of #months-present per project:")
    print(counts.to_string())


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def build_metrics(snapshots: pd.DataFrame) -> pd.DataFrame:
    df = snapshots.copy()

    # Parsed helper columns (internal use, prefixed with _)
    df["_start_dt"] = parse_mm_yyyy(df["start_date"])
    df["_original_completion_dt"] = parse_mm_yyyy(df["original_completion_date"])
    df["_revised_completion_dt"] = parse_mm_yyyy(df["revised_completion_date"])
    df["_report_month_dt"] = pd.to_datetime(df["report_month"], format="%Y-%m", errors="coerce")

    # "As of" date for expected-progress calc = the report month itself
    # (i.e. how much progress SHOULD have happened by that snapshot's month).
    df["cost_overrun_pct"] = compute_cost_overrun_pct(df)
    df["schedule_delay_months"] = compute_schedule_delay_months(df)
    df["expected_progress_pct"] = compute_expected_progress_pct(df, as_of=df["_report_month_dt"])
    df["progress_gap"] = compute_progress_gap(df)

    df = compute_monthly_velocity(df)

    # Drop internal helper columns from the final output
    df = df.drop(columns=[c for c in df.columns if c.startswith("_")])
    return df


def main():
    parser = argparse.ArgumentParser(description="Compute PAIMANA project analytics metrics.")
    parser.add_argument("--data-dir", required=True, help="Directory containing project_snapshots.csv")
    parser.add_argument("--out-dir", required=True, help="Directory to write processed CSV output to")
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    snapshots_path = data_dir / "project_snapshots.csv"
    if not snapshots_path.exists():
        print(f"Missing required file: {snapshots_path}", file=sys.stderr)
        sys.exit(1)

    snapshots = pd.read_csv(snapshots_path, dtype={"report_month": str})

    validate(snapshots)

    metrics = build_metrics(snapshots)

    out_path = out_dir / "project_metrics.csv"
    metrics.to_csv(out_path, index=False)

    print(f"\nWrote: {out_path}")

    # ---------------- 5 sample projects with calculated metrics ----------------
    print("\n=== 5 SAMPLE PROJECTS WITH CALCULATED METRICS (latest month each) ===")
    latest_metrics = (
        metrics.sort_values(["project_id", "report_month"])
        .groupby("project_id", as_index=False)
        .tail(1)
    )
    # pick 5 projects that have full April-July history so velocity is meaningful
    months_present = metrics.groupby("project_id")["report_month"].apply(lambda s: set(s))
    full_history_ids = months_present[months_present.apply(lambda s: set(EXPECTED_MONTHS).issubset(s))].index
    sample_ids = list(full_history_ids[:5]) if len(full_history_ids) >= 5 else list(latest_metrics["project_id"].head(5))

    show_cols = [
        "project_id", "project_name", "report_month", "physical_progress",
        "expected_progress_pct", "progress_gap", "cost_overrun_pct",
        "schedule_delay_months", "monthly_progress_velocity",
    ]
    for pid in sample_ids:
        row = latest_metrics[latest_metrics["project_id"] == pid][show_cols]
        print("\n" + row.to_string(index=False))


if __name__ == "__main__":
    main()
