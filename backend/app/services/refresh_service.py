from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.core.settings import get_settings
from app.services.incremental_refresh_service import get_refresh_status, refresh_some_routes


settings = get_settings()


def refresh_all(
    db: Session,
    *,
    batch_size: int | None = None,
    max_batches: int | None = None,
    use_claude: bool = True,
) -> dict[str, Any]:
    effective_batch_size = batch_size or settings.refresh_batch_size
    effective_max_batches = max_batches or 1

    total_processed = 0
    total_failed = 0

    for _ in range(effective_max_batches):
        result = refresh_some_routes(
            db,
            limit=effective_batch_size,
            mode="bootstrap",
            use_claude=use_claude,
        )
        total_processed += result["processed"]
        total_failed += result["failed"]
        if result["processed"] == 0:
            break

    return {
        "ok": True,
        "mode": "bootstrap",
        "batch_size": effective_batch_size,
        "max_batches": effective_max_batches,
        "processed": total_processed,
        "failed": total_failed,
        "status": get_refresh_status(db),
    }
