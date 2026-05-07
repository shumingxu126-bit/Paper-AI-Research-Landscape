from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db.session import SessionLocal, init_db
from app.core.settings import get_settings
from app.services.incremental_refresh_service import iter_routes
from app.services.snapshot_service import ensure_route_snapshots, rebuild_route_snapshot


def main():
    init_db()
    settings = get_settings()
    provider = (settings.llm_provider or "").strip().lower()
    use_llm = (provider == "minimax" and bool(settings.minimax_api_key)) or (
        provider == "anthropic" and bool(settings.anthropic_api_key)
    )
    db = SessionLocal()
    try:
        ensure_route_snapshots(db, use_claude=use_llm)
        for item in iter_routes():
            route = item["route"]
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
                use_claude=use_llm,
            )
        db.commit()
        print({"ok": True, "rebuilt_routes": len(iter_routes()), "llm_provider": provider, "use_llm": use_llm})
    finally:
        db.close()


if __name__ == "__main__":
    main()
