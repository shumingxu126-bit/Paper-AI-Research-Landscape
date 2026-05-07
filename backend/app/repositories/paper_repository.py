from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app.models.paper import Paper
from app.models.route_paper import RoutePaper


def upsert_paper(db: Session, paper: dict[str, Any]) -> int:
    source = paper.get("source", "unknown")
    source_paper_id = paper.get("source_paper_id")
    title = (paper.get("title") or "").strip()

    existing = None
    if source_paper_id:
        existing = (
            db.query(Paper)
            .filter(Paper.source == source, Paper.source_paper_id == source_paper_id)
            .first()
        )

    if existing is None and title:
        existing = db.query(Paper).filter(Paper.title == title).first()

    authors = json.dumps(paper.get("authors", []), ensure_ascii=False)
    raw_json = json.dumps(paper, ensure_ascii=False)

    if existing:
        existing.abstract = paper.get("abstract")
        existing.url = paper.get("url")
        existing.published_date = paper.get("date")
        existing.authors = authors
        existing.venue = paper.get("venue")
        existing.raw_json = raw_json
        db.flush()
        return existing.id

    obj = Paper(
        source=source,
        source_paper_id=source_paper_id,
        title=title,
        abstract=paper.get("abstract"),
        url=paper.get("url"),
        published_date=paper.get("date"),
        authors=authors,
        venue=paper.get("venue"),
        raw_json=raw_json,
    )
    db.add(obj)
    db.flush()
    return obj.id


def attach_papers_to_route(db: Session, route_slug: str, papers: list[dict[str, Any]]) -> None:
    for idx, paper in enumerate(papers):
        paper_id = upsert_paper(db, paper)
        existing = (
            db.query(RoutePaper)
            .filter(RoutePaper.route_slug == route_slug, RoutePaper.paper_id == paper_id)
            .first()
        )
        if existing:
            existing.score = max(100 - idx * 5, 60)
            continue

        db.add(
            RoutePaper(
                route_slug=route_slug,
                paper_id=paper_id,
                score=max(100 - idx * 5, 60),
                reason="fetched_by_refresh_worker",
            )
        )

    db.flush()
