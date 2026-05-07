## Deploy On Windows With Git + GitHub + Render

### 1. Initialize git locally

```powershell
cd C:\Users\29444\Desktop\paepr_ai
git init
git add .
git commit -m "Prepare public deployment"
```

### 2. Create a GitHub repository

On GitHub, create a new public or private repository, then run:

```powershell
git branch -M main
git remote add origin https://github.com/<your-name>/<your-repo>.git
git push -u origin main
```

If Git asks for authentication on Windows, use your GitHub account and a Personal Access Token.

### 3. Deploy on Render

1. Open https://render.com
2. Click `New` -> `Blueprint`
3. Connect your GitHub repository
4. Render will detect `render.yaml`
5. Confirm creation of:
   - one web service
   - one cron job
   - one PostgreSQL database

### 4. Set required environment variables

In Render, fill:

- `ANTHROPIC_API_KEY` or your active provider key
- `OPENALEX_EMAIL`

`DATABASE_URL` will be injected automatically by Render.

### 5. Open the public site

After the web service finishes building, open the Render web URL.

The frontend is served from the same FastAPI app, so you only need that single public URL.

### 6. Future updates

After you change code locally:

```powershell
git add .
git commit -m "Update site"
git push
```

Render will redeploy automatically.
