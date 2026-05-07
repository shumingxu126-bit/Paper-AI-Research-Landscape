from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db.session import SessionLocal, init_db
from app.services.refresh_service import refresh_all


def main():
    init_db()
    db = SessionLocal()
    try:
        result = refresh_all(db)
        print(result)
    finally:
        db.close()


if __name__ == '__main__':
    main()
