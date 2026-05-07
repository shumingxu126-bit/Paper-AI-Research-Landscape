from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime
from sqlalchemy.sql import func
from app.db.base import Base


class RoutePaper(Base):
    __tablename__ = "route_papers"

    id = Column(Integer, primary_key=True, index=True)
    route_slug = Column(String(255), nullable=False, index=True)
    paper_id = Column(Integer, ForeignKey("papers.id"), nullable=False, index=True)
    score = Column(Float, nullable=True)
    reason = Column(String(255), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())