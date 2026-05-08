from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.settings import get_settings
from app.db.session import SessionLocal, init_db
from app.models.route_refresh_state import RouteRefreshState
from app.repositories.paper_repository import attach_papers_to_route
from app.services.incremental_refresh_service import _fetch_route_papers, get_refresh_status, iter_routes
from app.services.snapshot_service import ensure_route_snapshots, rebuild_route_snapshot


class _BootstrapState:
    last_paper_fetch_at = None


def main():
    settings = get_settings()
    settings.bootstrap_lookback_days = 365
    settings.bootstrap_openalex_per_page = 25
    settings.bootstrap_openalex_max_pages = 8
    settings.bootstrap_arxiv_page_size = 25
    settings.bootstrap_arxiv_max_pages = 5
    settings.request_sleep_seconds = 0.8

    init_db()
    try:
        db = SessionLocal()
        ensure_route_snapshots(db, use_claude=False)
        db.close()
        success = 0
        failed = 0
        for idx, item in enumerate(iter_routes(), start=1):
            route = item["route"]
            print({"index": idx, "route": route["name"], "status": "start"})
            db = SessionLocal()
            try:
                papers = _fetch_route_papers(
                    route["name"],
                    route.get("keywords", []),
                    mode="bootstrap",
                    state=_BootstrapState(),
                )
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
                state = (
                    db.query(RouteRefreshState)
                    .filter(RouteRefreshState.route_slug == item["route_slug"])
                    .first()
                )
                if state:
                    state.status = "success"
                    state.error_message = None
                db.commit()
                success += 1
                print({"index": idx, "route": route["name"], "status": "success", "papers": len(papers)})
            except Exception as exc:
                try:
                    db.rollback()
                except Exception:
                    pass
                try:
                    db.close()
                except Exception:
                    pass
                db = SessionLocal()
                state = (
                    db.query(RouteRefreshState)
                    .filter(RouteRefreshState.route_slug == item["route_slug"])
                    .first()
                )
                if state:
                    state.status = "error"
                    state.error_message = str(exc)
                    db.commit()
                failed += 1
                print({"index": idx, "route": route["name"], "status": "error", "error": str(exc)})
            finally:
                db.close()
            time.sleep(1.0)

        db = SessionLocal()
        print({"ok": True, "success": success, "failed": failed, "final_status": get_refresh_status(db)})
        db.close()
    finally:
        pass


if __name__ == "__main__":
    main()
