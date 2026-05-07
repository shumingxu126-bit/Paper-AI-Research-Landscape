from pydantic import BaseModel
from typing import List, Any


class RouteSnapshotOut(BaseModel):
    domain: str
    section_name: str
    route_name: str
    route_slug: str
    route_desc: str
    maturity: str
    hot: bool
    emerging: bool
    route_question: str
    summary: str
    monthly_trend: List[int]
    keywords: List[str]
    latest_problem: str
    latest_themes: List[str]
    papers: List[Any]


class DomainResponse(BaseModel):
    domain: str
    sections: list
