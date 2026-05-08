from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.settings import get_settings
from app.db.base import Base

settings = get_settings()

engine_kwargs = {
    "future": True,
    "pool_pre_ping": True,
    "pool_recycle": 300,
}

if settings.database_url.startswith("postgresql://") or settings.database_url.startswith("postgres://"):
    engine_kwargs["connect_args"] = {"sslmode": "require"}

engine = create_engine(settings.database_url, **engine_kwargs)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def init_db():
    from app.models.paper import Paper
    from app.models.route import RouteSnapshot
    from app.models.route_paper import RoutePaper
    from app.models.route_refresh_state import RouteRefreshState

    Base.metadata.create_all(bind=engine)


def get_db():
    init_db()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
