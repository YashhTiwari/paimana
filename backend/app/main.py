"""
backend/app/main.py
--------------------
STEP 5 of the SIH 2026 (PS 26103) MVP pipeline.

A simple FastAPI backend that reads the CSVs produced by STEPs 1-4
(no database, no auth) and exposes them as JSON for a future React
frontend.

Data sources (read at startup and cached in memory as pandas
DataFrames; nothing here is hardcoded - every statistic is computed
from these files):
    data/projects_latest.csv     - latest snapshot per project (STEP 1)
    data/project_snapshots.csv   - full April-July history (STEP 1)
    data/project_risk.csv        - risk scores & explanations (STEP 3)
    data/project_alerts.csv      - early-warning alerts (STEP 4)

NOTE ON "sector": the source PAIMANA tables do not carry an explicit
per-project "sector" column (only the executing Agency, e.g. "Airport
Authority of India [AAI]", "NHAI", "Central Railway"). Since no sector
field exists in the extracted data, /api/sectors and the `sector`
filter in /api/projects use the `agency` column as the closest real
grouping dimension available - values are the actual agency strings
from the PDFs, nothing invented.

Run:
    uvicorn app.main:app --reload --port 8000
    (run from the backend/ directory, see STEP 5 report for the exact command)
"""

from pathlib import Path
from typing import Optional

import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

# ---------------------------------------------------------------------------
# Paths & data loading
# ---------------------------------------------------------------------------

# backend/app/main.py -> parents[0]=app, parents[1]=backend, parents[2]=project root
DATA_DIR = Path(__file__).resolve().parents[2] / "data"

REQUIRED_FILES = [
    "projects_latest.csv",
    "project_snapshots.csv",
    "project_risk.csv",
    "project_alerts.csv",
]


def _read_csv(name: str) -> pd.DataFrame:
    path = DATA_DIR / name
    if not path.exists():
        raise FileNotFoundError(f"Required data file not found: {path}")
    return pd.read_csv(path, dtype={"report_month": str})


class DataStore:
    """Holds the in-memory dataframes. load() can be re-called to refresh."""

    def __init__(self):
        self.latest: pd.DataFrame = pd.DataFrame()
        self.snapshots: pd.DataFrame = pd.DataFrame()
        self.risk: pd.DataFrame = pd.DataFrame()
        self.alerts: pd.DataFrame = pd.DataFrame()
        self.projects: pd.DataFrame = pd.DataFrame()  # latest + risk merged
        self.loaded = False
        self.load_error: Optional[str] = None

    def load(self):
        try:
            self.latest = _read_csv("projects_latest.csv")
            self.snapshots = _read_csv("project_snapshots.csv")
            self.risk = _read_csv("project_risk.csv")
            self.alerts = _read_csv("project_alerts.csv")

            risk_cols = [
                "project_id", "risk_score", "risk_level",
                "progress_risk", "schedule_risk", "cost_risk", "trend_risk",
                "risk_explanation",
            ]
            self.projects = self.latest.merge(
                self.risk[risk_cols], on="project_id", how="left"
            )
            self.loaded = True
            self.load_error = None
        except Exception as exc:  # noqa: BLE001 - surfaced via /api/health
            self.loaded = False
            self.load_error = str(exc)

    def alert_counts_by_project(self) -> pd.DataFrame:
        if self.alerts.empty:
            return pd.DataFrame(columns=["project_id", "alert_count"])
        return (
            self.alerts.groupby("project_id")
            .size()
            .reset_index(name="alert_count")
        )


store = DataStore()

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = FastAPI(
    title="PAIMANA Infrastructure Monitoring API",
    description="Read-only API over the STEP 1-4 processed PAIMANA project data.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # simple/open for the React frontend during development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup():
    store.load()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def df_to_records(df: pd.DataFrame) -> list:
    """Convert a DataFrame to JSON-safe records (NaN -> None)."""
    df = df.astype(object)
    df = df.where(pd.notnull(df), None)
    return df.to_dict(orient="records")


def get_project_row(project_id: int) -> pd.Series:
    match = store.projects[store.projects["project_id"] == project_id]
    if match.empty:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found.")
    return match.iloc[0]


def ensure_loaded():
    if not store.loaded:
        raise HTTPException(
            status_code=503,
            detail=f"Data not loaded: {store.load_error or 'unknown error'}",
        )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/health")
def health():
    return {
        "status": "ok" if store.loaded else "error",
        "data_loaded": store.loaded,
        "load_error": store.load_error,
        "row_counts": {
            "projects_latest": len(store.latest),
            "project_snapshots": len(store.snapshots),
            "project_risk": len(store.risk),
            "project_alerts": len(store.alerts),
        } if store.loaded else None,
    }


@app.get("/api/dashboard/summary")
def dashboard_summary():
    ensure_loaded()
    projects = store.projects
    alerts = store.alerts

    total_projects = int(projects["project_id"].nunique())

    risk_level_counts = (
        projects["risk_level"].value_counts(dropna=False).to_dict()
    )

    alert_type_counts = alerts["alert_type"].value_counts().to_dict()
    alert_severity_counts = alerts["severity"].value_counts().to_dict()

    cost_summary = {
        "total_original_cost_cr": round(float(projects["original_cost"].sum(skipna=True)), 2),
        "total_revised_cost_cr": round(float(projects["revised_cost"].sum(skipna=True)), 2),
        "total_expenditure_cr": round(float(projects["expenditure"].sum(skipna=True)), 2),
    }

    avg_physical_progress = round(float(projects["physical_progress"].mean(skipna=True)), 2)
    avg_risk_score = round(float(projects["risk_score"].mean(skipna=True)), 2)

    latest_month = projects["report_month"].max()

    return {
        "as_of_latest_report_month_available_per_project": latest_month,
        "total_projects": total_projects,
        "risk_level_distribution": risk_level_counts,
        "alerts": {
            "total_alerts": int(len(alerts)),
            "by_type": alert_type_counts,
            "by_severity": alert_severity_counts,
            "projects_with_alerts": int(alerts["project_id"].nunique()),
        },
        "cost_summary": cost_summary,
        "average_physical_progress_pct": avg_physical_progress,
        "average_risk_score": avg_risk_score,
        "states_covered": int(projects["state"].nunique()),
        "agencies_covered": int(projects["agency"].nunique()),
    }


@app.get("/api/projects")
def list_projects(
    search: Optional[str] = Query(None, description="Case-insensitive substring match on project name"),
    state: Optional[str] = Query(None, description="Case-insensitive substring match on state"),
    sector: Optional[str] = Query(None, description="Case-insensitive substring match on agency (used as sector)"),
    risk_level: Optional[str] = Query(None, description="Exact match: LOW / MEDIUM / HIGH"),
    limit: int = Query(100, ge=1, le=5000),
    offset: int = Query(0, ge=0),
):
    ensure_loaded()
    df = store.projects.copy()

    if search:
        df = df[df["project_name"].str.contains(search, case=False, na=False)]
    if state:
        df = df[df["state"].str.contains(state, case=False, na=False)]
    if sector:
        df = df[df["agency"].str.contains(sector, case=False, na=False)]
    if risk_level:
        df = df[df["risk_level"].str.upper() == risk_level.upper()]

    total_matching = len(df)
    df = df.sort_values("project_id").iloc[offset: offset + limit]

    return {
        "total_matching": total_matching,
        "limit": limit,
        "offset": offset,
        "results": df_to_records(df),
    }


@app.get("/api/projects/{project_id}")
def get_project(project_id: int):
    ensure_loaded()
    row = get_project_row(project_id)
    return df_to_records(pd.DataFrame([row]))[0]


@app.get("/api/projects/{project_id}/history")
def get_project_history(project_id: int):
    ensure_loaded()
    hist = store.snapshots[store.snapshots["project_id"] == project_id]
    if hist.empty:
        raise HTTPException(status_code=404, detail=f"No history found for project '{project_id}'.")
    hist = hist.sort_values("report_month")
    return {
        "project_id": project_id,
        "months_available": hist["report_month"].tolist(),
        "history": df_to_records(hist),
    }


@app.get("/api/projects/{project_id}/risk")
def get_project_risk(project_id: int):
    ensure_loaded()
    row = store.risk[store.risk["project_id"] == project_id]
    if row.empty:
        raise HTTPException(status_code=404, detail=f"No risk record found for project '{project_id}'.")
    return df_to_records(row)[0]


@app.get("/api/alerts")
def list_alerts(
    project_id: Optional[int] = Query(None),
    alert_type: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    limit: int = Query(200, ge=1, le=5000),
    offset: int = Query(0, ge=0),
):
    ensure_loaded()
    df = store.alerts.copy()

    if project_id is not None:
        df = df[df["project_id"] == project_id]
    if alert_type:
        df = df[df["alert_type"].str.upper() == alert_type.upper()]
    if severity:
        df = df[df["severity"].str.upper() == severity.upper()]

    total_matching = len(df)
    df = df.iloc[offset: offset + limit]

    return {
        "total_matching": total_matching,
        "limit": limit,
        "offset": offset,
        "results": df_to_records(df),
    }


@app.get("/api/top-risk-projects")
def top_risk_projects(limit: int = Query(10, ge=1, le=500)):
    ensure_loaded()
    df = store.projects.dropna(subset=["risk_score"]).sort_values(
        "risk_score", ascending=False
    ).head(limit)
    return {"limit": limit, "results": df_to_records(df)}


@app.get("/api/states")
def list_states():
    ensure_loaded()
    states = sorted(s for s in store.projects["state"].dropna().unique().tolist())
    return {"count": len(states), "states": states}


@app.get("/api/sectors")
def list_sectors():
    """
    See module docstring: the source data has no explicit 'sector' field,
    so this returns the distinct executing Agencies as the sector proxy.
    """
    ensure_loaded()
    sectors = sorted(a for a in store.projects["agency"].dropna().unique().tolist())
    return {"count": len(sectors), "sectors": sectors, "note": "Derived from the 'agency' field; no explicit sector field exists in source data."}
