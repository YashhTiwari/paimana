"""
alerts.py
---------
STEP 4 of the SIH 2026 (PS 26103) MVP pipeline.

Reads:
    data/project_snapshots.csv   (all months, all projects)
    data/projects_latest.csv     (latest available month per project)
    data/project_risk.csv        (STEP 3 risk scores per project)

Generates rule-based early-warning alerts (no ML). A project can
receive zero, one, or several alerts depending on which conditions its
actual data satisfies. Every number quoted in an alert message comes
directly from the source CSVs / values derived from them with a fixed,
documented formula — nothing is invented, and an alert is only raised
when the underlying fields needed for it are actually present.

Alert types:
    1. HIGH RISK            - risk_level == 'HIGH' (from STEP 3)
    2. COST OVERRUN          - revised_cost > original_cost
    3. SCHEDULE DELAY         - revised_completion_date later than original_completion_date
    4. LOW PROGRESS           - physical_progress significantly below expected_progress
    5. PROGRESS STAGNATION    - recent monthly progress growth is very low / zero

Output:
    data/project_alerts.csv
    columns: project_id, project_name, alert_type, severity, message, reason

Usage:
    python3 alerts.py --data-dir <dir_with_csvs> --out-dir <output_dir>
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

LOW_PROGRESS_MIN_GAP = 20.0  # points; below this, gap is not considered "significant"


# ---------------------------------------------------------------------------
# Helpers (self-contained - does not depend on STEP 2's analytics.py output)
# ---------------------------------------------------------------------------

def parse_mm_yyyy(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, format="%m/%Y", errors="coerce")


def month_diff(later: pd.Series, earlier: pd.Series) -> pd.Series:
    return (
        (later.dt.year - earlier.dt.year) * 12
        + (later.dt.month - earlier.dt.month)
    ).astype("float")


def compute_expected_progress(latest: pd.DataFrame) -> pd.Series:
    """
    Same formula as STEP 2: elapsed months since start / planned duration
    (start -> original completion), as of the project's own report_month.
    NaN when start_date or original_completion_date is missing, or the
    planned duration is not positive.
    """
    start_dt = parse_mm_yyyy(latest["start_date"])
    orig_dt = parse_mm_yyyy(latest["original_completion_date"])
    as_of_dt = pd.to_datetime(latest["report_month"], format="%Y-%m", errors="coerce")

    planned_duration = month_diff(orig_dt, start_dt)
    elapsed = month_diff(as_of_dt, start_dt)

    expected = elapsed / planned_duration * 100
    expected = expected.where(planned_duration.notna() & (planned_duration > 0))
    return expected.clip(lower=0, upper=100).round(2)


def compute_latest_velocity(snapshots: pd.DataFrame) -> pd.DataFrame:
    """
    For each project, the progress-points-per-month change between its
    two most recent available report months. Returns one row per project
    with columns: project_id, latest_velocity, prev_month, latest_month.
    Projects with fewer than 2 snapshot months get NaN (not invented).
    """
    snap = snapshots.copy()
    snap["_month_dt"] = pd.to_datetime(snap["report_month"], format="%Y-%m", errors="coerce")
    snap = snap.sort_values(["project_id", "_month_dt"])

    def last_two_velocity(g):
        g = g.dropna(subset=["_month_dt"])
        if len(g) < 2:
            return pd.Series({"latest_velocity": np.nan, "prev_month": None, "latest_month": None})
        g = g.tail(2)
        prev, curr = g.iloc[0], g.iloc[1]
        months_gap = (
            (curr["_month_dt"].year - prev["_month_dt"].year) * 12
            + (curr["_month_dt"].month - prev["_month_dt"].month)
        )
        if months_gap <= 0 or pd.isna(curr["physical_progress"]) or pd.isna(prev["physical_progress"]):
            return pd.Series({"latest_velocity": np.nan, "prev_month": prev["report_month"], "latest_month": curr["report_month"]})
        velocity = (curr["physical_progress"] - prev["physical_progress"]) / months_gap
        return pd.Series({
            "latest_velocity": round(velocity, 2),
            "prev_month": prev["report_month"],
            "latest_month": curr["report_month"],
        })

    result = snap.groupby("project_id").apply(last_two_velocity, include_groups=False).reset_index()
    return result


def severity_from_thresholds(value, thresholds):
    """thresholds: list of (max_value, severity_label), ascending; last entry catches the rest."""
    for max_val, label in thresholds:
        if value <= max_val:
            return label
    return thresholds[-1][1]


# ---------------------------------------------------------------------------
# Alert generators
# ---------------------------------------------------------------------------

def alerts_high_risk(risk: pd.DataFrame) -> list:
    out = []
    high = risk[risk["risk_level"] == "HIGH"]
    for _, row in high.iterrows():
        out.append({
            "project_id": row["project_id"],
            "project_name": row["project_name"],
            "alert_type": "HIGH RISK",
            "severity": "HIGH",
            "message": f"Project flagged as overall HIGH risk (risk score {row['risk_score']}/100).",
            "reason": (
                f"progress_risk={row['progress_risk']}, schedule_risk={row['schedule_risk']}, "
                f"cost_risk={row['cost_risk']}, trend_risk={row['trend_risk']} "
                f"(weighted: progress 35%, schedule 30%, cost 25%, trend 10%)."
            ),
        })
    return out


def alerts_cost_overrun(latest: pd.DataFrame) -> list:
    out = []
    df = latest.dropna(subset=["original_cost", "revised_cost"])
    df = df[df["revised_cost"] > df["original_cost"]]
    for _, row in df.iterrows():
        overrun_pct = (row["revised_cost"] - row["original_cost"]) / row["original_cost"] * 100
        severity = severity_from_thresholds(overrun_pct, [(15, "LOW"), (60, "MEDIUM"), (float("inf"), "HIGH")])
        out.append({
            "project_id": row["project_id"],
            "project_name": row["project_name"],
            "alert_type": "COST OVERRUN",
            "severity": severity,
            "message": (
                f"Revised cost (Rs. {row['revised_cost']:.2f} Cr) exceeds original approved cost "
                f"(Rs. {row['original_cost']:.2f} Cr) by {overrun_pct:.1f}%."
            ),
            "reason": f"original_cost={row['original_cost']:.2f} Cr, revised_cost={row['revised_cost']:.2f} Cr.",
        })
    return out


def alerts_schedule_delay(latest: pd.DataFrame) -> list:
    out = []
    df = latest.copy()
    df["_orig_dt"] = parse_mm_yyyy(df["original_completion_date"])
    df["_rev_dt"] = parse_mm_yyyy(df["revised_completion_date"])
    df = df.dropna(subset=["_orig_dt", "_rev_dt"])
    df = df[df["_rev_dt"] > df["_orig_dt"]]
    df["_delay_months"] = month_diff(df["_rev_dt"], df["_orig_dt"])

    for _, row in df.iterrows():
        delay = row["_delay_months"]
        severity = severity_from_thresholds(delay, [(6, "LOW"), (24, "MEDIUM"), (float("inf"), "HIGH")])
        out.append({
            "project_id": row["project_id"],
            "project_name": row["project_name"],
            "alert_type": "SCHEDULE DELAY",
            "severity": severity,
            "message": (
                f"Completion date pushed from {row['original_completion_date']} to "
                f"{row['revised_completion_date']} ({delay:.0f} month(s) delay)."
            ),
            "reason": (
                f"original_completion_date={row['original_completion_date']}, "
                f"revised_completion_date={row['revised_completion_date']}."
            ),
        })
    return out


def alerts_low_progress(latest: pd.DataFrame) -> list:
    out = []
    df = latest.copy()
    df["expected_progress_pct"] = compute_expected_progress(df)
    df = df.dropna(subset=["expected_progress_pct", "physical_progress"])
    df["_gap"] = df["expected_progress_pct"] - df["physical_progress"]
    df = df[df["_gap"] >= LOW_PROGRESS_MIN_GAP]

    for _, row in df.iterrows():
        gap = row["_gap"]
        severity = severity_from_thresholds(gap, [(35, "LOW"), (55, "MEDIUM"), (float("inf"), "HIGH")])
        out.append({
            "project_id": row["project_id"],
            "project_name": row["project_name"],
            "alert_type": "LOW PROGRESS",
            "severity": severity,
            "message": (
                f"Physical progress ({row['physical_progress']:.1f}%) is significantly below "
                f"time-based expected progress ({row['expected_progress_pct']:.1f}%) - "
                f"gap of {gap:.1f} points."
            ),
            "reason": (
                f"physical_progress={row['physical_progress']:.1f}%, "
                f"expected_progress={row['expected_progress_pct']:.1f}% "
                f"(based on start_date={row['start_date']}, "
                f"original_completion_date={row['original_completion_date']}, "
                f"as of report_month={row['report_month']})."
            ),
        })
    return out


def alerts_progress_stagnation(snapshots: pd.DataFrame, latest: pd.DataFrame) -> list:
    out = []
    vel = compute_latest_velocity(snapshots)
    vel = vel.dropna(subset=["latest_velocity"])
    vel = vel[vel["latest_velocity"] <= 1.0]  # "very low or zero" growth

    name_lookup = latest.set_index("project_id")["project_name"].to_dict()

    for _, row in vel.iterrows():
        v = row["latest_velocity"]
        severity = "HIGH" if v <= 0 else "MEDIUM"
        pid = row["project_id"]
        out.append({
            "project_id": pid,
            "project_name": name_lookup.get(pid, None),
            "alert_type": "PROGRESS STAGNATION",
            "severity": severity,
            "message": (
                f"Physical progress grew by only {v:.2f} points/month between "
                f"{row['prev_month']} and {row['latest_month']}."
            ),
            "reason": (
                f"monthly_progress_velocity={v:.2f} (computed from consecutive snapshots "
                f"{row['prev_month']} -> {row['latest_month']})."
            ),
        })
    return out


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Generate PAIMANA early-warning alerts.")
    parser.add_argument("--data-dir", required=True)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    required = ["project_snapshots.csv", "projects_latest.csv", "project_risk.csv"]
    for fname in required:
        if not (data_dir / fname).exists():
            print(f"Missing required file: {data_dir / fname}", file=sys.stderr)
            sys.exit(1)

    snapshots = pd.read_csv(data_dir / "project_snapshots.csv", dtype={"report_month": str})
    latest = pd.read_csv(data_dir / "projects_latest.csv", dtype={"report_month": str})
    risk = pd.read_csv(data_dir / "project_risk.csv", dtype={"report_month": str})

    all_alerts = []
    all_alerts += alerts_high_risk(risk)
    all_alerts += alerts_cost_overrun(latest)
    all_alerts += alerts_schedule_delay(latest)
    all_alerts += alerts_low_progress(latest)
    all_alerts += alerts_progress_stagnation(snapshots, latest)

    alerts_df = pd.DataFrame(
        all_alerts,
        columns=["project_id", "project_name", "alert_type", "severity", "message", "reason"],
    )
    alerts_df = alerts_df.sort_values(
        ["project_id", "alert_type"]
    ).reset_index(drop=True)

    out_path = out_dir / "project_alerts.csv"
    alerts_df.to_csv(out_path, index=False)

    # ---------------- Summary ----------------
    print("=== STEP 4 EARLY WARNING ALERTS SUMMARY ===")
    print(f"Total alerts generated: {len(alerts_df)}")
    print(f"Projects with at least one alert: {alerts_df['project_id'].nunique()} / {latest['project_id'].nunique()}")

    print("\nAlerts by type:")
    print(alerts_df["alert_type"].value_counts().to_string())

    print("\nAlerts by severity:")
    print(alerts_df["severity"].value_counts().to_string())

    print("\nAlerts by type x severity:")
    print(pd.crosstab(alerts_df["alert_type"], alerts_df["severity"]).to_string())

    print(f"\nWrote: {out_path}")

    # ---------------- 10 sample alerts ----------------
    print("\n=== 10 SAMPLE ALERTS FROM REAL PROJECTS ===")
    sample_parts = []
    for atype in ["HIGH RISK", "COST OVERRUN", "SCHEDULE DELAY", "LOW PROGRESS", "PROGRESS STAGNATION"]:
        sub = alerts_df[alerts_df["alert_type"] == atype].head(2)
        sample_parts.append(sub)
    sample = pd.concat(sample_parts).head(10)

    for i, (_, row) in enumerate(sample.iterrows(), 1):
        print(f"\n{i}. [{row['alert_type']}] Severity: {row['severity']}")
        print(f"   Project: {row['project_id']} - {row['project_name']}")
        print(f"   Message: {row['message']}")
        print(f"   Reason : {row['reason']}")


if __name__ == "__main__":
    main()
