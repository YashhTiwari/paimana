"""
process_reports.py
-------------------
STEP 1 of the SIH 2026 (PS 26103) MVP pipeline.

Extracts and cleans the "All Ongoing Projects" table from the PAIMANA
Flash Report PDFs (April, May, June, July 2026) and produces:

    data/project_snapshots.csv   -> one row per project per report month
    data/projects_latest.csv     -> one row per project (latest month only)

Usage:
    python3 process_reports.py --pdf-dir <dir_with_pdfs> --out-dir <output_dir>

No values are invented. Any field not present in the source PDF is left
blank (NaN) in the output.
"""

import argparse
import re
import sys
from pathlib import Path

import pandas as pd
import pdfplumber

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

REQUIRED_COLUMNS = [
    "project_id",
    "project_name",
    "agency",
    "state",
    "start_date",
    "original_completion_date",
    "revised_completion_date",
    "original_cost",
    "revised_cost",
    "expenditure",
    "physical_progress",
    "report_month",
]

# Map filename fragments -> canonical report_month (YYYY-MM)
FILENAME_MONTH_HINTS = {
    "april": "2026-04",
    "may": "2026-05",
    "june": "2026-06",
    "july": "2026-07",
}

MONTH_NAME_TO_NUM = {
    "january": "01", "february": "02", "march": "03", "april": "04",
    "may": "05", "june": "06", "july": "07", "august": "08",
    "september": "09", "october": "10", "november": "11", "december": "12",
}

PAREN_ONLY_RE = re.compile(r"^(\(.*?\)\s*)+$")
PAREN_GROUP_RE = re.compile(r"\(([^)]*)\)")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def infer_report_month(pdf_path: Path, first_page_text: str) -> str:
    """Infer YYYY-MM report month from filename, falling back to page text."""
    name = pdf_path.stem.lower()
    for key, val in FILENAME_MONTH_HINTS.items():
        if key in name:
            return val

    # Fallback: look for "<MONTH> 2026" in the page text (e.g. "APRIL 2026")
    m = re.search(r"(january|february|march|april|may|june|july|august|"
                  r"september|october|november|december)\s+(\d{4})",
                  first_page_text, re.IGNORECASE)
    if m:
        month_name = m.group(1).lower()
        year = m.group(2)
        return f"{year}-{MONTH_NAME_TO_NUM[month_name]}"
    return None


def clean(value):
    """Normalize a raw pdfplumber cell string; return None for blanks/dashes."""
    if value is None:
        return None
    value = value.strip()
    if value in ("", "-", "--", "NA", "N/A"):
        return None
    return value


def strip_outer_parens(value):
    if value is None:
        return None
    value = value.strip()
    if value.startswith("(") and value.endswith(")"):
        value = value[1:-1]
    return clean(value)


def split_two_line_field(raw):
    """
    Split a cell like '265.91\\n(265.91)' or '01/2026\\n(07/2026)' into
    (original_value, revised_value). Handles missing revised value ('-')
    and cells with only one line (no revised value present).
    """
    if raw is None:
        return None, None
    lines = [l.strip() for l in raw.split("\n") if l.strip() != ""]
    if not lines:
        return None, None
    original = clean(lines[0])
    revised = None
    if len(lines) > 1:
        revised = strip_outer_parens(lines[1])
    return original, revised


def parse_project_name_cell(raw):
    """
    Parse the combined "Project Name / (Agency) / (Project Code)
    (Legacy OCMS Code) (PMGID)" cell into its components.

    The cell is structured as free-text description line(s), followed by
    trailing line(s) that are wholly parenthesised:
        (Agency)
        (Project Code)
        (Legacy OCMS Code) (PMGID)
    """
    if raw is None:
        return None, None, None

    lines = [l for l in raw.split("\n")]
    # strip trailing/leading blank lines
    while lines and lines[-1].strip() == "":
        lines.pop()
    while lines and lines[0].strip() == "":
        lines.pop(0)

    trailing = []
    while lines and PAREN_ONLY_RE.match(lines[-1].strip()):
        trailing.insert(0, lines.pop().strip())

    n = len(trailing)
    legacy_pmgid_line = trailing[n - 1] if n >= 1 else None
    project_code_line = trailing[n - 2] if n >= 2 else None
    agency_line = trailing[n - 3] if n >= 3 else None

    agency = strip_outer_parens(agency_line)
    project_code = strip_outer_parens(project_code_line)
    # legacy_pmgid_line may hold 1 or 2 paren groups; we only need to make
    # sure we don't misread it as the project_id.
    _ = legacy_pmgid_line  # not part of required columns; kept for clarity

    project_name = " ".join(l.strip() for l in lines if l.strip() != "")
    project_name = re.sub(r"\s+", " ", project_name).strip()
    project_name = clean(project_name)

    return project_name, agency, project_code


def is_data_row(row):
    """A genuine project row has a numeric Sl.No in the first cell."""
    if not row:
        return False
    sl_no = row[0]
    if sl_no is None:
        return False
    return sl_no.strip().isdigit()


def extract_table_rows(pdf_path: Path):
    """Yield raw pdfplumber table rows for every 'All Ongoing Projects' page."""
    rows = []
    report_month = None
    with pdfplumber.open(pdf_path) as pdf:
        first_page_text = pdf.pages[0].extract_text() or ""
        report_month = infer_report_month(pdf_path, first_page_text)

        for page in pdf.pages:
            text = page.extract_text() or ""
            if "All Ongoing Projects" not in text or "Sl.No" not in text:
                continue
            for table in page.find_tables():
                extracted = table.extract()
                for row in extracted:
                    rows.append(row)
    return rows, report_month


def rows_to_dataframe(rows, report_month):
    records = []
    for row in rows:
        # pad/truncate defensively - expected 8 columns
        if len(row) < 8:
            row = row + [None] * (8 - len(row))

        (sl_no, name_cell, state_cell, approval_start_cell,
         doc_cell, cost_cell, expenditure_cell, progress_cell) = row[:8]

        if not is_data_row(row):
            continue  # skip ministry/section header rows, repeated headers

        project_name, agency, project_code = parse_project_name_cell(name_cell)

        state = clean(state_cell)
        if state:
            state = re.sub(r"\s+", " ", state).strip()

        _approval, start_date = split_two_line_field(approval_start_cell)
        original_completion_date, revised_completion_date = split_two_line_field(doc_cell)
        original_cost, revised_cost = split_two_line_field(cost_cell)

        expenditure = clean(expenditure_cell)
        physical_progress = clean(progress_cell)

        records.append({
            "project_id": project_code,
            "project_name": project_name,
            "agency": agency,
            "state": state,
            "start_date": start_date,
            "original_completion_date": original_completion_date,
            "revised_completion_date": revised_completion_date,
            "original_cost": original_cost,
            "revised_cost": revised_cost,
            "expenditure": expenditure,
            "physical_progress": physical_progress,
            "report_month": report_month,
        })

    df = pd.DataFrame(records, columns=REQUIRED_COLUMNS)

    # Convert numeric-looking columns to numeric dtypes where possible,
    # WITHOUT inventing values (non-numeric / missing stay as NaN).
    numeric_cols = ["original_cost", "revised_cost", "expenditure", "physical_progress"]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    return df


def process_pdf(pdf_path: Path) -> pd.DataFrame:
    rows, report_month = extract_table_rows(pdf_path)
    df = rows_to_dataframe(rows, report_month)
    return df


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Extract PAIMANA 'All Ongoing Projects' tables.")
    parser.add_argument("--pdf-dir", required=True, help="Directory containing the Flash Report PDFs")
    parser.add_argument("--out-dir", required=True, help="Directory to write CSV outputs to")
    args = parser.parse_args()

    pdf_dir = Path(args.pdf_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    pdf_paths = sorted(pdf_dir.glob("*.pdf"))
    if not pdf_paths:
        print(f"No PDFs found in {pdf_dir}", file=sys.stderr)
        sys.exit(1)

    all_dfs = []
    for pdf_path in pdf_paths:
        print(f"Processing {pdf_path.name} ...")
        df = process_pdf(pdf_path)
        print(f"  -> {len(df)} project rows, report_month={df['report_month'].iloc[0] if len(df) else 'UNKNOWN'}")
        all_dfs.append(df)

    combined = pd.concat(all_dfs, ignore_index=True)

    # Drop exact duplicate (project_id, report_month) rows, keep first occurrence
    dup_mask = combined.duplicated(subset=["project_id", "report_month"], keep=False)
    n_duplicates = int(dup_mask.sum())

    combined_sorted = combined.sort_values(["project_id", "report_month"])
    snapshots_path = out_dir / "project_snapshots.csv"
    combined_sorted.to_csv(snapshots_path, index=False)

    # "Latest" snapshot per project = last report_month available for that project_id
    latest = (
        combined_sorted.dropna(subset=["project_id"])
        .sort_values(["project_id", "report_month"])
        .groupby("project_id", as_index=False)
        .tail(1)
        .sort_values("project_id")
    )
    latest_path = out_dir / "projects_latest.csv"
    latest.to_csv(latest_path, index=False)

    # ---------------- Report ----------------
    print("\n=== STEP 1 EXTRACTION REPORT ===")
    print(f"Total rows (all months): {len(combined)}")
    print(f"Unique project_id values: {combined['project_id'].nunique(dropna=True)}")
    print("\nRows per month:")
    print(combined.groupby("report_month").size().to_string())
    print(f"\nDuplicate (project_id, report_month) records: {n_duplicates}")

    print("\nMissing values per column:")
    print(combined.isna().sum().to_string())

    print("\n=== 5 SAMPLE PROJECTS WITH MONTHLY HISTORY ===")
    sample_ids = (
        combined.dropna(subset=["project_id"])["project_id"]
        .value_counts()
        .head(5)
        .index
        .tolist()
    )
    for pid in sample_ids:
        sub = combined[combined["project_id"] == pid].sort_values("report_month")
        name = sub["project_name"].iloc[0]
        print(f"\nProject ID: {pid} - {name}")
        cols_to_show = ["report_month", "physical_progress", "revised_cost", "expenditure",
                         "revised_completion_date"]
        print(sub[cols_to_show].to_string(index=False))

    print(f"\nWrote: {snapshots_path}")
    print(f"Wrote: {latest_path}")


if __name__ == "__main__":
    main()
