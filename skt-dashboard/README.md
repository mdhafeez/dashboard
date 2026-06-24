# SKT Course Planning 2026 Dashboard

Web monitoring dashboard for SPLD course and workshop implementation.

## Setup

```powershell
cd C:\Users\mdhafeez\Documents\ACE\real_project\dashboard\skt-dashboard
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

Open `http://127.0.0.1:5000`.

## Data Flow

- The original uploaded workbook is copied to `data/PerancanganSKT2026.xlsx`.
- Section sheets are normalized into one `courses` table.
- Raw uploaded files are retained in `data/`.
- Processed dashboard data is stored in `database/skt_dashboard.db`.
- Upload history is tracked in `upload_history`.

## Main Features

- KPI overview for planned, completed, upcoming, delayed, dropped courses, participants, and budget.
- Section and monthly monitoring.
- Automatic status classification.
- Alert panel for missing data, date issues, overlaps, and below-target participation.
- Searchable/filterable course list with DataTables.
- Inline course status override and remarks.
- Excel and CSV export for the current filtered data.
"# dashboard" 
