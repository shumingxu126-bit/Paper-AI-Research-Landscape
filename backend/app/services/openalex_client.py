from __future__ import annotations

from datetime import date, datetime
import time
from typing import Dict, List

import requests

from app.core.settings import get_settings

BASE_URL = 'https://api.openalex.org/works'
MAX_RETRIES = 4
RETRY_STATUS_CODES = {429, 500, 502, 503, 504}


def _build_session() -> requests.Session:
    session = requests.Session()
    session.trust_env = False
    return session


def _request_openalex(params: dict) -> dict:
    settings = get_settings()
    headers = {'User-Agent': f'research-landscape/1.0 ({settings.openalex_email or "no-email"})'}
    last_error: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            resp = _build_session().get(BASE_URL, params=params, headers=headers, timeout=30)
            if resp.status_code in RETRY_STATUS_CODES:
                if attempt == MAX_RETRIES - 1:
                    resp.raise_for_status()
                retry_after = resp.headers.get('Retry-After')
                sleep_seconds = float(retry_after) if retry_after and retry_after.isdigit() else 2 ** attempt
                time.sleep(sleep_seconds)
                continue
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            last_error = exc
            if attempt == MAX_RETRIES - 1:
                raise
            time.sleep(2 ** attempt)
    if last_error:
        raise last_error
    raise RuntimeError('OpenAlex request failed without a response')


def _sanitize_date(value: str | None) -> str:
    if not value:
        return ""
    for fmt, width in (("%Y-%m-%d", 10), ("%Y-%m", 7), ("%Y", 4)):
        try:
            dt = datetime.strptime(value[:width], fmt)
            if dt > datetime.utcnow():
                return ""
            return value[:width]
        except ValueError:
            continue
    return ""


def fetch_openalex(
    query: str,
    per_page: int = 8,
    *,
    page: int = 1,
    from_date: date | None = None,
    to_date: date | None = None,
) -> List[Dict]:
    params = {
        'search': query,
        'per-page': per_page,
        'page': page,
        'sort': 'publication_date:desc',
    }
    filters = []
    if from_date:
        filters.append(f'from_publication_date:{from_date.isoformat()}')
    if to_date:
        filters.append(f'to_publication_date:{to_date.isoformat()}')
    if filters:
        params['filter'] = ",".join(filters)
    data = _request_openalex(params).get('results', [])
    out = []
    for item in data:
        authors = [
            (authorship.get("author") or {}).get("display_name")
            for authorship in item.get("authorships", [])
            if (authorship.get("author") or {}).get("display_name")
        ]
        primary_location = item.get("primary_location") or {}
        source = primary_location.get("source") or {}
        out.append({
            'title': item.get('display_name') or 'Untitled',
            'date': _sanitize_date(item.get('publication_date')),
            'venue': source.get('display_name') or 'OpenAlex',
            'abstract': '',
            'url': item.get('id') or '',
            'citation_count': item.get('cited_by_count', 0),
            'source': 'openalex',
            'source_paper_id': item.get('id') or '',
            'authors': authors,
        })
    return out


def count_openalex_works(
    query: str,
    *,
    from_date: date | None = None,
    to_date: date | None = None,
) -> int:
    params = {
        'search': query,
        'per-page': 1,
        'page': 1,
    }
    filters = []
    if from_date:
        filters.append(f'from_publication_date:{from_date.isoformat()}')
    if to_date:
        filters.append(f'to_publication_date:{to_date.isoformat()}')
    if filters:
        params['filter'] = ",".join(filters)
    payload = _request_openalex(params)
    return int(((payload.get('meta') or {}).get('count')) or 0)
