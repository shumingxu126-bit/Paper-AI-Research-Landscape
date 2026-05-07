from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.sql import func
from app.db.base import Base


class RouteRefreshState(Base):
    __tablename__ = "route_refresh_state"

    id = Column(Integer, primary_key=True, index=True)
    route_slug = Column(String(255), nullable=False, unique=True, index=True)
    domain = Column(String(255), nullable=False)
    section_name = Column(String(255), nullable=False)
    route_name = Column(String(255), nullable=False)

    last_paper_fetch_at = Column(DateTime(timezone=True), nullable=True)
    last_summary_refresh_at = Column(DateTime(timezone=True), nullable=True)
    last_success_at = Column(DateTime(timezone=True), nullable=True)
    last_error_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(50), nullable=True, default="pending")
    error_message = Column(Text, nullable=True)

    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())