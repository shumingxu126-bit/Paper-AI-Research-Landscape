from collections import defaultdict
from datetime import datetime, timedelta
import json

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.settings import get_settings
from app.db.session import get_db
from app.models.paper import Paper
from app.models.route import RouteSnapshot
from app.models.route_paper import RoutePaper
from app.services.incremental_refresh_service import (
    bootstrap_refresh_state,
    get_refresh_status,
    refresh_some_routes,
)
from app.services.refresh_service import refresh_all
from app.services.snapshot_service import (
    derive_focus,
    derive_keywords,
    ensure_route_snapshots,
    filter_relevant_papers,
    make_estimated_trend,
    make_monthly_trend_from_dates,
    select_focus_papers,
    select_recent_recommended_papers,
)

router = APIRouter()
settings = get_settings()

GENERIC_LATEST_THEMES = ["效果更强", "推理/训练成本更低", "更贴近真实应用场景"]


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    for fmt, width in (("%Y-%m-%d", 10), ("%Y-%m", 7), ("%Y", 4)):
        try:
            dt = datetime.strptime(value[:width], fmt)
            if dt > datetime.utcnow():
                return None
            return dt
        except ValueError:
            continue
    return None


def _choose_recent_window(papers: list[dict]) -> int:
    now = datetime.utcnow()
    month_1 = now - timedelta(days=30)
    month_2 = now - timedelta(days=60)
    month_3 = now - timedelta(days=90)

    recent_1 = 0
    recent_2 = 0
    recent_3 = 0
    for paper in papers:
        dt = _parse_date(paper.get("date"))
        if not dt:
            continue
        if dt >= month_1:
            recent_1 += 1
        if dt >= month_2:
            recent_2 += 1
        if dt >= month_3:
            recent_3 += 1

    if recent_1 >= 3:
        return 30
    if recent_2 >= 3:
        return 60
    if recent_3 >= 2:
        return 90
    return 180


def _load_route_papers(db: Session, route_slug: str) -> list[dict]:
    rows = (
        db.query(RoutePaper, Paper)
        .join(Paper, RoutePaper.paper_id == Paper.id)
        .filter(RoutePaper.route_slug == route_slug)
        .order_by(Paper.published_date.desc().nullslast())
        .all()
    )
    papers: list[dict] = []
    for route_paper, paper in rows:
        try:
            authors = json.loads(paper.authors) if paper.authors else []
        except Exception:
            authors = []
        papers.append(
            {
                "title": paper.title,
                "abstract": paper.abstract,
                "url": paper.url,
                "date": paper.published_date,
                "venue": paper.venue,
                "authors": authors,
                "score": int(route_paper.score) if route_paper.score is not None else 80,
            }
        )
    return papers


def _recent_papers(papers: list[dict], days: int, limit: int = 6) -> list[dict]:
    cutoff = datetime.utcnow() - timedelta(days=days)
    recent = []
    for paper in papers:
        dt = _parse_date(paper.get("date"))
        if dt and dt >= cutoff:
            recent.append(paper)
    if not recent:
        recent = papers[:limit]
    return recent[:limit]


def _format_authors(authors: list[str], limit: int = 3) -> str:
    if not authors:
        return "作者未知"
    clipped = authors[:limit]
    suffix = " 等" if len(authors) > limit else ""
    return "、".join(clipped) + suffix


def _focus_copy(route_name: str, theme: str, paper: dict) -> str:
    abstract = (paper.get("abstract") or "").strip()
    if abstract:
        short = abstract[:120] + ("..." if len(abstract) > 120 else "")
        return f"Core focus in {route_name}: {theme}. Current papers are mainly tackling this through {short}"
    return f"Core focus in {route_name}: {theme}."


def _focus_items(route_name: str, latest_problem: str, themes: list[str], recent_papers: list[dict]) -> list[dict]:
    items = []
    for idx, theme in enumerate(themes[:3]):
        paper = recent_papers[idx] if idx < len(recent_papers) else {}
        items.append(
            {
                "title": theme,
                "value": _focus_copy(route_name, theme, paper),
                "paper": {
                    "name": paper.get("title") or "相关论文",
                    "url": paper.get("url") or "#",
                    "date": paper.get("date") or "",
                    "authors": _format_authors(paper.get("authors") or []),
                },
            }
        )
    if not items:
        items.append(
            {
                "title": "近期趋势",
                "value": latest_problem or f"{route_name} 近期研究仍在持续演进。",
                "paper": {"name": "相关论文", "url": "#", "date": "", "authors": "作者未知"},
            }
        )
    return items


def _generic_problem(text: str | None) -> bool:
    if not text:
        return True
    return "最近论文主要在提高效果" in text


def _generic_question(text: str | None) -> bool:
    if not text:
        return True
    return "核心研究问题是什么" in text


@router.get("/health")
def health():
    return {"status": "ok"}


@router.post("/refresh")
def refresh(
    mode: str = Query(default="incremental", pattern="^(incremental|bootstrap|full)$"),
    limit: int = Query(default=3, ge=1, le=50),
    max_batches: int = Query(default=1, ge=1, le=100),
    use_claude: bool = Query(default=True),
    db: Session = Depends(get_db),
):
    if mode == "full":
        return refresh_all(db, batch_size=limit, max_batches=max_batches, use_claude=use_claude)
    return refresh_some_routes(db, limit=limit, mode=mode, use_claude=use_claude)


@router.post("/refresh/bootstrap")
def refresh_bootstrap(
    limit: int = Query(default=3, ge=1, le=50),
    use_claude: bool = Query(default=True),
    db: Session = Depends(get_db),
):
    created = bootstrap_refresh_state(db)
    result = refresh_some_routes(db, limit=limit, mode="bootstrap", use_claude=use_claude)
    result["bootstrapped"] = created
    return result


@router.post("/refresh/bootstrap-year")
def refresh_bootstrap_year(
    limit: int = Query(default=3, ge=1, le=50),
    use_claude: bool = Query(default=True),
    db: Session = Depends(get_db),
):
    created = bootstrap_refresh_state(db)
    result = refresh_some_routes(db, limit=limit, mode="bootstrap", use_claude=use_claude)
    result["bootstrapped"] = created
    result["lookback_days"] = settings.bootstrap_lookback_days
    result["description"] = f"bootstrap recent {settings.bootstrap_lookback_days} days of historical papers"
    return result


@router.get("/refresh/status")
def refresh_status(db: Session = Depends(get_db)):
    bootstrap_refresh_state(db)
    return get_refresh_status(db)


@router.get("/landscape")
def get_landscape(db: Session = Depends(get_db)):
    bootstrap_refresh_state(db)
    ensure_route_snapshots(db, use_claude=False)

    rows = (
        db.execute(
            select(RouteSnapshot).order_by(
                RouteSnapshot.domain,
                RouteSnapshot.section_name,
                RouteSnapshot.route_name,
            )
        )
        .scalars()
        .all()
    )
    section_map = defaultdict(lambda: defaultdict(list))

    for row in rows:
        snapshot_papers = row.papers or []
        all_papers = _load_route_papers(db, row.route_slug)
        source_papers = all_papers or snapshot_papers
        effective_keywords = row.keywords or derive_keywords(
            row.route_name,
            row.route_desc,
            row.keywords or [],
            source_papers,
        )
        relevant_papers = filter_relevant_papers(
            row.route_name,
            row.route_desc,
            effective_keywords,
            source_papers,
        )
        recommended_papers, _ = select_recent_recommended_papers(
            row.route_name,
            row.route_desc,
            effective_keywords,
            relevant_papers,
            target_count=6,
            minimum_count=4,
        )
        focus_papers, _ = select_focus_papers(
            row.route_name,
            row.route_desc,
            effective_keywords,
            relevant_papers,
            target_count=5,
        )
        derived = derive_focus(
            row.route_name,
            row.route_desc,
            effective_keywords,
            relevant_papers,
            row.route_question,
        )

        route_question = derived["route_question"]
        latest_problem = derived["latest_problem"]
        latest_themes = derived["latest_themes"] or row.latest_themes or []

        recent_window_days = _choose_recent_window(focus_papers or recommended_papers)
        recent_papers = recommended_papers or _recent_papers(relevant_papers, days=recent_window_days, limit=6)
        monthly_trend = row.monthly_trend or make_monthly_trend_from_dates([paper.get("date") for paper in relevant_papers])
        if not any(monthly_trend):
            monthly_trend = make_estimated_trend(max(len(relevant_papers), 6), row.route_name)

        latest_focus = {
            "problem": latest_problem,
            "themes": latest_themes,
            "items": _focus_items(row.route_name, latest_problem, latest_themes, focus_papers or recent_papers),
            "links": [
                {
                    "name": paper.get("title") or "相关论文",
                    "url": paper.get("url") or "#",
                }
                for paper in (focus_papers or recent_papers)[:3]
            ],
        }

        section_map[row.domain][row.section_name].append(
            {
                "name": row.route_name,
                "desc": row.route_desc,
                "maturity": row.maturity,
                "hot": row.hot,
                "emerging": row.emerging,
                "routeQuestion": route_question,
                "summary": row.summary or derived["summary"],
                "monthlyTrend": monthly_trend,
                "keywords": effective_keywords,
                "papers": recent_papers,
                "latestFocus": latest_focus,
            }
        )

    payload = {}
    for domain, sections in section_map.items():
        payload[domain] = {
            "sections": [{"name": section_name, "routes": routes} for section_name, routes in sections.items()]
        }
    return payload
