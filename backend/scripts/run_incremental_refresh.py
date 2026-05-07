from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db.session import SessionLocal, init_db
from app.services.incremental_refresh_service import refresh_some_routes


def main():
    print("start incremental refresh")
    init_db()
    db = SessionLocal()
    try:
        result = refresh_some_routes(db, limit=3, mode="incremental", use_claude=True)
        print("incremental refresh result:", result)
    finally:
        db.close()


if __name__ == "__main__":
    main()
