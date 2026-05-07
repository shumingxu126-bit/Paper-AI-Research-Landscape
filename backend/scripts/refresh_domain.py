from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db.session import SessionLocal, init_db
from app.repositories.paper_repository import attach_papers_to_route
from app.services.incremental_refresh_service import _fetch_route_papers, iter_routes
from app.services.snapshot_service import rebuild_route_snapshot


class _BootstrapState:
    last_paper_fetch_at = None


def main():
    if len(sys.argv) < 2:
        print('usage: python scripts/refresh_domain.py "Domain Name"')
        raise SystemExit(1)

    target_domain = sys.argv[1].strip().lower()
    init_db()
    db = SessionLocal()
    try:
        matched = [item for item in iter_routes() if item["domain"].lower() == target_domain]
        if not matched:
            print({"ok": False, "error": "domain_not_found", "domain": sys.argv[1]})
            raise SystemExit(1)

        results = []
        for item in matched:
            route = item["route"]
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
            db.commit()
            results.append({"route": route["name"], "fetched": len(papers)})
            time.sleep(0.5)

        print({"ok": True, "domain": matched[0]["domain"], "routes": results})
    finally:
        db.close()


if __name__ == "__main__":
    main()
