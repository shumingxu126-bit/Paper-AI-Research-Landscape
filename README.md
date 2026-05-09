# Paper AI Research Landscape

This repository contains:

- a FastAPI backend
- a single-page frontend
- OpenAlex + arXiv paper collection
- route snapshots, trends, and recommended papers

## Project structure

- `backend/`: API, database models, refresh logic, scripts
- `frontend/`: single HTML frontend
- `config/taxonomy_full.yaml`: route taxonomy
- `render.yaml`: minimal Render web-service configuration

## Local run

### Backend

```powershell
cd backend
uvicorn app.main:app --reload
```

### Frontend

Open:

- `frontend/index.html`

or serve it locally and open:

- `http://127.0.0.1:8080`

## Useful scripts

- `python backend\scripts\manual_refresh.py`
- `python backend\scripts\run_refresh.py`
- `python backend\scripts\backfill_year.py`
- `python backend\scripts\rebuild_snapshots.py`
- `python backend\scripts\refresh_route.py "Route Name"`
- `python backend\scripts\refresh_domain.py "Domain Name"`
- `python backend\scripts\retry_failed_backfill.py`

## Deployment

See:

- `DEPLOY_WINDOWS_RENDER.md`
