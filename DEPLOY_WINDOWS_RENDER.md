## Deploy On Windows With GitHub + Render

This project is deployed as a single Render web service.
The FastAPI app serves both the API and the frontend page.

### 1. Push the repo to GitHub

```powershell
cd C:\Users\29444\Desktop\paepr_ai
git add .
git commit -m "Update deployment"
git push
```

### 2. Create a Render web service

1. Open https://render.com
2. Click `New` -> `Web Service`
3. Connect your GitHub repository

Use these fields:

- `Root Directory`: leave empty
- `Build Command`: `pip install -r backend/requirements.txt`
- `Start Command`: `uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port $PORT`

### 3. Set environment variables

In the Render web service, set:

- `DATABASE_URL`
- `OPENALEX_EMAIL`
- `LLM_PROVIDER`
- `MINIMAX_API_KEY` or `ANTHROPIC_API_KEY`
- `CORS_ORIGINS` if you want to override the default

### 4. Optional scheduled refresh

If you do not use a paid Render cron service, use GitHub Actions instead.
The workflow file is:

- `.github/workflows/daily_refresh.yml`

Set these GitHub repository secrets if you want scheduled refresh:

- `DATABASE_URL`
- `OPENALEX_EMAIL`
- `ANTHROPIC_API_KEY`

Add `MINIMAX_API_KEY` and `LLM_PROVIDER` if you switch the workflow to MiniMax.

### 5. Backfill historical data

Render free instances do not provide an interactive shell.
To backfill the production database from your Windows machine, point your local shell at the Render database:

```powershell
$env:DATABASE_URL="your-render-postgres-url"
$env:OPENALEX_EMAIL="your-email"
$env:LLM_PROVIDER="minimax"
$env:MINIMAX_API_KEY="your-key"

python backend\scripts\backfill_year.py
python backend\scripts\rebuild_snapshots.py
```
