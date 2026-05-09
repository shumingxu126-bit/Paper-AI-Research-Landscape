# Frontend

The frontend is a single `index.html` file.

## Local development

When you open the page from:

- `file://...`
- `http://127.0.0.1:8080`
- `http://localhost:8080`

it requests the backend from:

- `http://127.0.0.1:8000`

## Production

In production, the frontend uses the same origin as the FastAPI app and calls:

- `/api/landscape`
- `/api/refresh`

This means you only need one public web service URL.
