from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db.session import SessionLocal, init_db
from app.repositories.paper_repository import attach_papers_to_route
from app.services.incremental_refresh_service import _fetch_route_papers, iter_routes
from app.services.snapshot_service import rebuild_route_snapshot


def main():
    if len(sys.argv) < 2:
        print("usage: python scripts/refresh_route.py \"Route Name\"")
        raise SystemExit(1)

    target_route = sys.argv[1].strip().lower()
    init_db()
    db = SessionLocal()
    try:
        matched = [item for item in iter_routes() if item["route"]["name"].lower() == target_route]
        if not matched:
            print({"ok": False, "error": "route_not_found", "route": sys.argv[1]})
            raise SystemExit(1)

        item = matched[0]
        route = item["route"]
        papers = _fetch_route_papers(route["name"], route.get("keywords", []), mode="bootstrap", state=type("S", (), {"last_paper_fetch_at": None})())
        attach_papers_to_route(db, item["route_slug"], papers)
        rebuild_route_snapshot(
            db,
            domain=item["domain"],
            section_name=item["section_name"],
            route_name=route["name"],
            route_slug=item["route_slug"],
            route_desc=route["desc"],
            maturity=route["maturity"],
            hot=route["hot"],
            emerging=route["emerging"],
            keywords=route.get("keywords", []),
            fallback_question=route["routeQuestion"],
            use_claude=False,
        )
        db.commit()
        print({"ok": True, "route": route["name"], "fetched": len(papers)})
    finally:
        db.close()


if __name__ == "__main__":
    main()
