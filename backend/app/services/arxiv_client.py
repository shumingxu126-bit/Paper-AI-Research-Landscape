from __future__ import annotations

from datetime import date, datetime
import time
from typing import Dict, List
import xml.etree.ElementTree as ET

import requests

ARXIV_URL = 'http://export.arxiv.org/api/query'
NS = {'atom': 'http://www.w3.org/2005/Atom'}
REQUEST_TIMEOUT = 30
MAX_RETRIES = 3
RETRY_STATUS_CODES = {429, 500, 502, 503, 504}


def _build_session() -> requests.Session:
    session = requests.Session()
    session.trust_env = False
    session.headers.update({'User-Agent': 'research-landscape/1.0'})
    return session


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


def _arxiv_date(value: date) -> str:
    return value.strftime("%Y%m%d")


def _request_with_retry(params: dict) -> requests.Response:
    last_error: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            resp = _build_session().get(ARXIV_URL, params=params, timeout=REQUEST_TIMEOUT)
            if resp.status_code in RETRY_STATUS_CODES:
                retry_after = resp.headers.get('Retry-After')
                if attempt == MAX_RETRIES - 1:
                    resp.raise_for_status()
                sleep_seconds = float(retry_after) if retry_after and retry_after.isdigit() else 2 ** attempt
                time.sleep(sleep_seconds)
                continue
            resp.raise_for_status()
            return resp
        except requests.RequestException as exc:
            last_error = exc
            if attempt == MAX_RETRIES - 1:
                raise
            time.sleep(2 ** attempt)

    if last_error:
        raise last_error
    raise RuntimeError('arXiv request failed without a response')


def fetch_arxiv(
    query: str,
    max_results: int = 6,
    *,
    start: int = 0,
    from_date: date | None = None,
    to_date: date | None = None,
) -> List[Dict]:
    search_query = f'all:{query}'
    if from_date or to_date:
        start_date = from_date or date(1991, 1, 1)
        end_date = to_date or datetime.utcnow().date()
        search_query = f'({search_query}) AND submittedDate:[{_arxiv_date(start_date)}0000 TO {_arxiv_date(end_date)}2359]'

    params = {
        'search_query': search_query,
        'start': start,
        'max_results': max_results,
        'sortBy': 'submittedDate',
        'sortOrder': 'descending',
    }
    resp = _request_with_retry(params)
    root = ET.fromstring(resp.text)
    out: List[Dict] = []
    for entry in root.findall('atom:entry', NS):
        title = (entry.findtext('atom:title', default='', namespaces=NS) or '').replace('\n', ' ').strip()
        summary = (entry.findtext('atom:summary', default='', namespaces=NS) or '').replace('\n', ' ').strip()
        published = entry.findtext('atom:published', default='', namespaces=NS)
        entry_id = entry.findtext('atom:id', default='', namespaces=NS)
        authors = [
            (author.findtext('atom:name', default='', namespaces=NS) or '').strip()
            for author in entry.findall('atom:author', NS)
            if (author.findtext('atom:name', default='', namespaces=NS) or '').strip()
        ]
        link = ''
        for link_el in entry.findall('atom:link', NS):
            href = link_el.attrib.get('href')
            if href:
                link = href
                break
        out.append({
            'title': title or 'Untitled',
            'date': _sanitize_date(published[:10] if published else ''),
            'venue': 'arXiv',
            'abstract': summary,
            'url': link,
            'citation_count': 0,
            'source': 'arxiv',
            'source_paper_id': entry_id or link,
            'authors': authors,
        })
    if from_date or to_date:
        filtered = []
        for item in out:
            item_date = item.get('date')
            if not item_date:
                continue
            if from_date and item_date < from_date.isoformat():
                continue
            if to_date and item_date > to_date.isoformat():
                continue
            filtered.append(item)
        return filtered
    return out
