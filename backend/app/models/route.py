from sqlalchemy import String, Text, DateTime, Integer, Boolean, JSON
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from app.db.base import Base


class RouteSnapshot(Base):
    __tablename__ = 'route_snapshots'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    domain: Mapped[str] = mapped_column(String(100), index=True)
    section_name: Mapped[str] = mapped_column(String(255), index=True)
    route_name: Mapped[str] = mapped_column(String(255), index=True)
    route_slug: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    route_desc: Mapped[str] = mapped_column(Text)
    maturity: Mapped[str] = mapped_column(String(50))
    hot: Mapped[bool] = mapped_column(Boolean, default=False)
    emerging: Mapped[bool] = mapped_column(Boolean, default=False)
    route_question: Mapped[str] = mapped_column(Text)
    summary: Mapped[str] = mapped_column(Text)
    monthly_trend: Mapped[list] = mapped_column(JSON)
    keywords: Mapped[list] = mapped_column(JSON)
    latest_problem: Mapped[str] = mapped_column(Text)
    latest_themes: Mapped[list] = mapped_column(JSON)
    papers: Mapped[list] = mapped_column(JSON)
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
