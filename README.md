# PAIMANA Infrastructure Monitoring - SIH 2026 (PS 26103) MVP

An AI-powered infrastructure project monitoring and early-warning platform,
built on real PAIMANA Flash Report data (April-July 2026).

## Pipeline

```
PAIMANA PDFs  ->  process_reports.py  ->  analytics.py  ->  risk_engine.py  ->  alerts.py  ->  FastAPI  ->  React
   (input)          (STEP 1)              (STEP 2)          (STEP 3)          (STEP 4)      (STEP 5)   (STEP 6)
```

All intermediate CSVs are already included under `data/`, so you can run the
backend and frontend immediately without re-processing the PDFs. To
regenerate them from scratch, see "Re-running the pipeline" below.

## Folder structure

```
backend/
  scripts/process_reports.py   STEP 1 - extract "All Ongoing Projects" tables from the PDFs
  analytics.py                 STEP 2 - cost overrun, schedule delay, expected progress, velocity
  risk_engine.py                STEP 3 - rule-based 0-100 risk score + explanation
  alerts.py                    STEP 4 - early-warning alerts (5 types)
  app/main.py                  STEP 5 - FastAPI backend serving the processed CSVs
  requirements.txt
data/
  project_snapshots.csv        every project x every report month
  projects_latest.csv          latest snapshot per project
  project_metrics.csv          STEP 2 output
  project_risk.csv             STEP 3 output
  project_alerts.csv           STEP 4 output
frontend/
  src/                         React app (STEP 6) - Dashboard, Projects, Project Detail, Alerts
```

## Running the backend

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
Swagger docs: http://localhost:8000/docs

## Running the frontend

```bash
cd frontend
npm install
npm run dev
```
Open http://localhost:5173 (make sure the backend is running first;
`frontend/.env` points to `http://localhost:8000` by default).

## Re-running the pipeline from scratch (optional)

Requires the original PAIMANA Flash Report PDFs (April/May/June/July 2026),
placed in a folder of your choice.

```bash
cd backend
python3 scripts/process_reports.py --pdf-dir <path_to_pdfs> --out-dir ../data
python3 analytics.py     --data-dir ../data --out-dir ../data
python3 risk_engine.py   --data-dir ../data --out-dir ../data
python3 alerts.py        --data-dir ../data --out-dir ../data
```

## Known limitations (by design, not oversights)

- No explicit "sector/ministry" field exists in the source PDFs - the
  `agency` field is used as a stand-in wherever "sector" is shown.
- No forecasting/prediction model - risk scoring is rule-based only (no ML),
  per the project scope.
- No authentication, database, or Docker - CSVs are the source of truth and
  everything runs locally, per the project scope.
