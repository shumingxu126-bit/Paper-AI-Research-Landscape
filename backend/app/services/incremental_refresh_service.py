from __future__ import annotations

import re
import time
from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.core.settings import get_settings
from app.models.route_refresh_state import RouteRefreshState
from app.repositories.paper_repository import attach_papers_to_route
from app.services.arxiv_client import fetch_arxiv
from app.services.openalex_client import fetch_openalex
from app.services.route_profiles import (
    matches_route_required_terms,
    route_query_terms,
    route_seed_terms,
    route_token_terms,
)
from app.services.snapshot_service import rebuild_route_snapshot
from app.services.taxonomy_loader import load_taxonomy


settings = get_settings()

QUERY_STOPWORDS = {
    "for", "and", "with", "the", "a", "an", "of", "to", "in", "on",
    "models", "model", "systems", "system",
}
GENERIC_MATCH_TERMS = {"ai", "ml", "llm", "agent", "agents", "learning"}
TOKEN_EXPANSIONS = {
    "embodied": ["robotics", "manipulation", "navigation"],
    "image": ["vision", "visual"],
    "video": ["temporal", "vision"],
    "audio": ["speech", "sound"],
    "music": ["audio", "generation"],
    "chat": ["dialogue", "assistant"],
    "agent": ["tool", "planner", "reasoning"],
    "recommendation": ["recommender", "ranking", "retrieval"],
    "ranking": ["ctr", "reranking", "relevance"],
    "retrieval": ["search", "matching", "indexing"],
    "conversational": ["dialogue", "interaction"],
    "sequential": ["sequence", "next-item", "session"],
    "causal": ["counterfactual", "de-bias"],
    "fairness": ["safety", "diversity"],
    "multimodal": ["vision-language", "cross-modal"],
    "generation": ["diffusion", "synthesis"],
    "editing": ["control", "instruction"],
    "document": ["ocr", "layout"],
    "spatial": ["3d", "geometry"],
}


def _tokenize_text(value: str) -> list[str]:
    tokens = re.findall(r"[a-z0-9][a-z0-9\-+/]*", value.lower())
    return [token for token in tokens if token and token not in QUERY_STOPWORDS]


def _query_terms(route_name: str, keywords: list[str]) -> list[str]:
    return route_query_terms(route_name, keywords, limit=8)


def _significant_terms(route_name: str, keywords: list[str]) -> list[str]:
    terms = []
    for term in route_seed_terms(route_name, keywords):
        token = term.lower().strip()
        if not token or token in QUERY_STOPWORDS or token in GENERIC_MATCH_TERMS:
            continue
        terms.append(token)
        for child in _tokenize_text(token):
            if child not in QUERY_STOPWORDS and child not in GENERIC_MATCH_TERMS:
                terms.append(child)
    for child in route_token_terms(route_name, keywords):
        if child not in QUERY_STOPWORDS and child not in GENERIC_MATCH_TERMS:
            terms.append(child)
    return list(dict.fromkeys(terms))


def _term_hits(route_name: str, keywords: list[str], paper: dict[str, Any]) -> int:
    haystack = " ".join(
        [
            paper.get("title") or "",
            paper.get("abstract") or "",
            paper.get("venue") or "",
        ]
    ).lower()
    hits = 0
    for term in _significant_terms(route_name, keywords):
        if term in haystack:
            hits += 1
    return hits


def _has_required_terms(route_name: str, paper: dict[str, Any]) -> bool:
    haystack = " ".join(
        [
            paper.get("title") or "",
            paper.get("abstract") or "",
            paper.get("venue") or "",
        ]
    )
    return matches_route_required_terms(route_name, haystack)


def build_query(route_name: str, keywords: list[str]) -> str:
    return " ".join(_query_terms(route_name, keywords))


def normalize_route(route_item: Any) -> dict[str, Any]:
    if isinstance(route_item, str):
        return {
            "name": route_item,
            "desc": "",
            "maturity": "增长期",
            "hot": True,
            "emerging": False,
            "keywords": [],
            "routeQuestion": f"{route_item} 的核心研究问题是什么？",
        }

    if isinstance(route_item, dict):
        route_name = route_item.get("name", "")
        return {
            "name": route_name,
            "desc": route_item.get("desc", ""),
            "maturity": route_item.get("maturity", "增长期"),
            "hot": bool(route_item.get("hot", True)),
            "emerging": bool(route_item.get("emerging", False)),
            "keywords": route_item.get("keywords", []),
            "routeQuestion": route_item.get("routeQuestion", f"{route_name} 的核心研究问题是什么？"),
        }

    return {
        "name": "",
        "desc": "",
        "maturity": "增长期",
        "hot": True,
        "emerging": False,
        "keywords": [],
        "routeQuestion": "该路线的核心研究问题是什么？",
    }


def route_slug(domain_name: str, section_name: str, route_name: str) -> str:
    return f"{domain_name}-{section_name}-{route_name}".replace(" ", "-").replace("/", "-")


def iter_routes() -> list[dict[str, Any]]:
    taxonomy = load_taxonomy()
    domains = taxonomy.get("domains", [])
    routes: list[dict[str, Any]] = []

    for domain in domains:
        domain_name = domain.get("name", "")
        for section in domain.get("sections", []):
            section_name = section.get("name", "")
            for route_item in section.get("routes", []):
                route = normalize_route(route_item)
                if not route["name"]:
                    continue
                routes.append(
                    {
                        "domain": domain_name,
                        "section_name": section_name,
                        "route_slug": route_slug(domain_name, section_name, route["name"]),
                        "route": route,
                    }
                )
    return routes


def bootstrap_refresh_state(db: Session) -> int:
    created = 0
    for item in iter_routes():
        existing = (
            db.query(RouteRefreshState)
            .filter(RouteRefreshState.route_slug == item["route_slug"])
            .first()
        )
        if existing:
            continue

        db.add(
            RouteRefreshState(
                route_slug=item["route_slug"],
                domain=item["domain"],
                section_name=item["section_name"],
                route_name=item["route"]["name"],
                status="pending",
            )
        )
        created += 1

    db.commit()
    return created


def get_refresh_status(db: Session) -> dict[str, int]:
    states = db.query(RouteRefreshState).all()
    total = len(states)
    success = sum(1 for item in states if item.status == "success")
    pending = sum(1 for item in states if item.status in (None, "", "pending"))
    error = sum(1 for item in states if item.status == "error")
    return {
        "total_routes": total,
        "success_routes": success,
        "pending_routes": pending,
        "error_routes": error,
    }


def _select_states(db: Session, mode: str, limit: int) -> list[RouteRefreshState]:
    query = db.query(RouteRefreshState)

    if mode == "bootstrap":
        return (
            query.order_by(
                RouteRefreshState.last_success_at.asc().nullsfirst(),
                RouteRefreshState.updated_at.asc().nullsfirst(),
            )
            .limit(limit)
            .all()
        )

    due_before = datetime.now(timezone.utc) - timedelta(hours=settings.refresh_interval_hours)
    return (
        query.filter(
            (RouteRefreshState.last_paper_fetch_at.is_(None))
            | (RouteRefreshState.last_paper_fetch_at <= due_before)
        )
        .order_by(
            RouteRefreshState.last_paper_fetch_at.asc().nullsfirst(),
            RouteRefreshState.updated_at.asc().nullsfirst(),
        )
        .limit(limit)
        .all()
    )


def _find_route_meta(state: RouteRefreshState) -> dict[str, Any] | None:
    for item in iter_routes():
        if item["route_slug"] == state.route_slug:
            return {
                "domain": item["domain"],
                "section_name": item["section_name"],
                **item["route"],
            }
    return None


def _dedupe_papers(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str]] = set()
    output: list[dict[str, Any]] = []
    for item in items:
        key = (
            item.get("source") or "unknown",
            item.get("source_paper_id") or (item.get("title") or "").strip().lower(),
        )
        if not key[1] or key in seen:
            continue
        seen.add(key)
        output.append(item)
    return output


def _paper_match_score(route_name: str, keywords: list[str], paper: dict[str, Any]) -> float:
    haystack = " ".join(
        [
            paper.get("title") or "",
            paper.get("abstract") or "",
            paper.get("venue") or "",
        ]
    ).lower()
    title = (paper.get("title") or "").lower()

    score = 0.0
    route_phrase = route_name.lower()
    if route_phrase and route_phrase in title:
        score += 10.0
    if route_phrase and route_phrase in haystack:
        score += 6.0

    for term in _query_terms(route_name, keywords):
        token = term.lower()
        if token in title:
            score += 3.0
        elif token in haystack:
            score += 1.0

    published = paper.get("date") or ""
    if isinstance(published, str):
        if published[:7] == datetime.now(timezone.utc).strftime("%Y-%m"):
            score += 1.5
        elif published[:7] == (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m"):
            score += 0.8

    return score


def _rank_papers(route_name: str, keywords: list[str], papers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ranked = sorted(
        papers,
        key=lambda paper: (
            _paper_match_score(route_name, keywords, paper),
            paper.get("date") or "",
            paper.get("citation_count") or 0,
        ),
        reverse=True,
    )
    route_phrase = route_name.lower()
    filtered = [
        paper
        for paper in ranked
        if (
            _has_required_terms(route_name, paper)
            and
            (
            route_phrase in ((paper.get("title") or "").lower())
            or _term_hits(route_name, keywords, paper) >= 2
            or (
                len(_significant_terms(route_name, keywords)) <= 1
                and _term_hits(route_name, keywords, paper) >= 1
            )
            )
        )
    ]
    filtered = [paper for paper in filtered if _paper_match_score(route_name, keywords, paper) >= 3.0]
    return filtered


def _resolve_from_date(mode: str, state: RouteRefreshState) -> date:
    today = datetime.now(timezone.utc).date()
    if mode == "bootstrap":
        return today - timedelta(days=settings.bootstrap_lookback_days)

    if state.last_paper_fetch_at:
        return (state.last_paper_fetch_at - timedelta(days=1)).date()

    return today - timedelta(days=settings.incremental_lookback_days)


def _bootstrap_windows(from_date: date, to_date: date, window_days: int = 60) -> list[tuple[date, date]]:
    windows: list[tuple[date, date]] = []
    cursor = from_date
    while cursor <= to_date:
        end = min(cursor + timedelta(days=window_days - 1), to_date)
        windows.append((cursor, end))
        cursor = end + timedelta(days=1)
    return windows


def _fetch_route_papers(
    route_name: str,
    keywords: list[str],
    *,
    mode: str,
    state: RouteRefreshState,
) -> list[dict[str, Any]]:
    query = build_query(route_name, keywords)
    papers: list[dict[str, Any]] = []
    errors: list[str] = []
    from_date = _resolve_from_date(mode, state)

    try:
        if mode == "bootstrap":
            windows = _bootstrap_windows(from_date, datetime.now(timezone.utc).date(), window_days=60)
            pages_per_window = max(1, settings.bootstrap_openalex_max_pages // max(len(windows), 1))
            for window_from, window_to in windows:
                for page in range(1, pages_per_window + 1):
                    page_items = fetch_openalex(
                        query,
                        per_page=settings.bootstrap_openalex_per_page,
                        page=page,
                        from_date=window_from,
                        to_date=window_to,
                    )
                    if not page_items:
                        break
                    papers.extend(page_items)
                    time.sleep(settings.request_sleep_seconds)
        else:
            papers.extend(
                fetch_openalex(
                    query,
                    per_page=settings.openalex_per_route,
                    from_date=from_date,
                )
            )
    except Exception as exc:
        errors.append(f"openalex: {exc}")

    time.sleep(settings.request_sleep_seconds)

    try:
        if mode == "bootstrap":
            windows = _bootstrap_windows(from_date, datetime.now(timezone.utc).date(), window_days=60)
            pages_per_window = max(1, settings.bootstrap_arxiv_max_pages // max(len(windows), 1))
            for window_from, window_to in windows:
                for page in range(pages_per_window):
                    start = page * settings.bootstrap_arxiv_page_size
                    page_items = fetch_arxiv(
                        query,
                        max_results=settings.bootstrap_arxiv_page_size,
                        start=start,
                        from_date=window_from,
                        to_date=window_to,
                    )
                    if not page_items:
                        break
                    papers.extend(page_items)
                    time.sleep(settings.request_sleep_seconds)
        else:
            papers.extend(
                fetch_arxiv(
                    query,
                    max_results=settings.arxiv_per_route,
                    from_date=from_date,
                )
            )
    except Exception as exc:
        errors.append(f"arxiv: {exc}")

    if not papers and errors:
        raise RuntimeError("; ".join(errors))

    deduped = _dedupe_papers(papers)
    ranked = _rank_papers(route_name, keywords, deduped)
    return ranked[:24]


def refresh_some_routes(
    db: Session,
    *,
    limit: int | None = None,
    mode: str = "incremental",
    use_claude: bool = True,
) -> dict[str, Any]:
    bootstrap_refresh_state(db)

    effective_limit = limit or settings.refresh_batch_size
    states = _select_states(db, mode=mode, limit=effective_limit)
    processed = 0
    failed = 0

    for state in states:
        route_meta = _find_route_meta(state)
        if route_meta is None:
            state.status = "error"
            state.error_message = "route not found in taxonomy"
            state.last_error_at = datetime.now(timezone.utc)
            db.commit()
            failed += 1
            continue

        try:
            papers = _fetch_route_papers(
                route_meta["name"],
                route_meta["keywords"],
                mode=mode,
                state=state,
            )
            attach_papers_to_route(db, state.route_slug, papers)

            rebuild_route_snapshot(
                db,
                domain=route_meta["domain"],
                section_name=route_meta["section_name"],
                route_name=route_meta["name"],
                route_slug=state.route_slug,
                route_desc=route_meta["desc"],
                maturity=route_meta["maturity"],
                hot=route_meta["hot"],
                emerging=route_meta["emerging"],
                keywords=route_meta["keywords"],
                fallback_question=route_meta["routeQuestion"],
                use_claude=use_claude,
            )

            now = datetime.now(timezone.utc)
            state.status = "success"
            state.error_message = None
            state.last_paper_fetch_at = now
            state.last_summary_refresh_at = now
            state.last_success_at = now
            db.commit()
            processed += 1
        except Exception as exc:
            state.status = "error"
            state.error_message = str(exc)
            state.last_error_at = datetime.now(timezone.utc)
            db.commit()
            failed += 1

    return {
        "ok": True,
        "mode": mode,
        "processed": processed,
        "failed": failed,
        "limit": effective_limit,
        "status": get_refresh_status(db),
    }
