# GitHub History vs Releases and News

This repo contains a simple Python tool that compares:
- your GitHub public activity history
- product/repository release dates
- optional custom news or release CSV files

It generates:
- a timeline CSV summary
- an HTML report for review

## Quick start

1. Create a virtual environment (optional but recommended)

   python -m venv .venv
   . .venv/bin/activate   # Linux/macOS
   # or .venv\Scripts\activate   # Windows

2. Install dependencies

   pip install -r requirements.txt

3. Run the script

   python app.py --github-user your-github-username --track-repos "microsoft/vscode,facebook/react"

4. Optional custom CSV inputs

   python app.py \
     --github-user your-github-username \
     --track-repos "microsoft/vscode,facebook/react" \
     --release-csv data/release_dates.csv \
     --news-csv data/news_items.csv

## Output

Files are written to `output/`:
- `timeline_summary.csv`
- `timeline_report.html`

## Expected CSV layout

For custom files, use columns like:
- `date`
- `name`
- `source`
- `url`
- `notes`
- `type`

Example:

```csv
date,name,source,url,notes,type
2024-01-12,Product Launch,Acme Blog,https://example.com/launch,"Major new feature",news
```

## What it does

- fetches your public GitHub events
- fetches latest release dates for tracked repos
- merges with any CSV data you provide
- sorts the timeline by date
- exports a summary and HTML report

This is a simple way to compare your activity timeline with the products and releases you care about.
