from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.sql import func

from app.db.base import Base


class Paper(Base):
    __tablename__ = "papers"

    id = Column(Integer, primary_key=True, index=True)
    source = Column(String(50), nullable=False)
    source_paper_id = Column(String(255), nullable=True, index=True)
    title = Column(Text, nullable=False)
    abstract = Column(Text, nullable=True)
    url = Column(Text, nullable=True)
    published_date = Column(String(50), nullable=True)
    authors = Column(Text, nullable=True)
    venue = Column(String(255), nullable=True)
    raw_json = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
