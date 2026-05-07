from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db.session import SessionLocal, init_db
from app.services.incremental_refresh_service import get_refresh_status, refresh_some_routes


def main():
    init_db()
    db = SessionLocal()
    try:
        rounds = []
        for _ in range(5):
            result = refresh_some_routes(db, mode="bootstrap", limit=3, use_claude=False)
            rounds.append(result)
            if result["processed"] == 0:
                break
        print({"ok": True, "rounds": rounds, "final_status": get_refresh_status(db)})
    finally:
        db.close()


if __name__ == "__main__":
    main()
