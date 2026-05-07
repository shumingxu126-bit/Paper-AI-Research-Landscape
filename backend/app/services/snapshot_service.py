from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timedelta
import json
import re
from typing import List

from sqlalchemy.orm import Session

from app.models.paper import Paper
from app.models.route import RouteSnapshot
from app.models.route_paper import RoutePaper
from app.services.claude_client import summarize_route
from app.services.openalex_client import count_openalex_works
from app.services.route_profiles import (
    matches_route_required_terms,
    preset_keywords_for_route,
    route_query_terms,
    route_seed_terms,
    route_token_terms,
)
from app.services.taxonomy_loader import load_taxonomy

TEXT_STOPWORDS = {
    "and", "for", "with", "from", "into", "using", "based", "toward", "towards",
    "the", "a", "an", "of", "in", "on", "to", "by", "via", "over", "under",
    "study", "analysis", "system", "systems", "model", "models", "learning",
    "approach", "method", "methods", "framework", "survey", "benchmark",
    "understanding", "generation", "recommendation", "multimodal", "video",
    "audio", "visual", "embodied", "interactive", "retrieval", "agent", "agents",
}


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    for fmt, width in (("%Y-%m-%d", 10), ("%Y-%m", 7), ("%Y", 4)):
        try:
            dt = datetime.strptime(value[:width], fmt)
            if dt > datetime.utcnow():
                return None
            return dt
        except ValueError:
            continue
    return None


def _tokenize(value: str) -> list[str]:
    return re.findall(r"[a-z0-9][a-z0-9\-+/]*", (value or "").lower())


def _safe_date_key(value: str | None) -> str:
    dt = _parse_date(value)
    return dt.strftime("%Y-%m-%d") if dt else ""


def _representative_title(title: str) -> str:
    title = (title or "").strip()
    if len(title) <= 72:
        return title
    return title[:69] + "..."


def _extract_title_focus_phrases(route_name: str, keywords: list[str], papers: list[dict], limit: int = 4) -> list[str]:
    blocked = set(_significant_terms(route_name, keywords))
    blocked.update(TEXT_STOPWORDS)
    phrases: Counter[str] = Counter()

    for paper in papers[:10]:
        title = paper.get("title") or ""
        segments = [segment.strip() for segment in re.split(r"[:;,.()]+", title) if segment.strip()]
        candidates = segments if segments else [title]
        for segment in candidates:
            tokens = [token for token in _tokenize(segment) if token not in blocked and len(token) >= 4]
            if len(tokens) < 2:
                continue
            phrase = " ".join(tokens[:3]).title()
            phrases[phrase] += 1

    result = []
    seen = set()
    for phrase, _ in phrases.most_common(limit * 2):
        key = phrase.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(phrase)
        if len(result) >= limit:
            break
    return result


def _significant_terms(route_name: str, keywords: list[str]) -> list[str]:
    blocked = {"ai", "ml", "llm", "agent", "agents", "learning", "model", "models"}
    terms = []
    for term in route_seed_terms(route_name, keywords):
        normalized = str(term).strip().lower()
        if normalized and normalized not in blocked:
            terms.append(normalized)
    for token in route_token_terms(route_name, keywords):
        if token not in blocked:
            terms.append(token)
    return list(dict.fromkeys(terms))


def _term_hits(route_name: str, keywords: list[str], paper: dict) -> int:
    haystack = " ".join(
        [paper.get("title") or "", paper.get("abstract") or "", paper.get("venue") or ""]
    ).lower()
    hits = 0
    for term in _significant_terms(route_name, keywords):
        if term in haystack:
            hits += 1
    return hits


def _has_required_terms(route_name: str, paper: dict) -> bool:
    haystack = " ".join(
        [paper.get("title") or "", paper.get("abstract") or "", paper.get("venue") or ""]
    )
    return matches_route_required_terms(route_name, haystack)


def _extract_salient_terms(route_name: str, keywords: list[str], papers: list[dict], limit: int = 6) -> list[str]:
    blocked = set(_significant_terms(route_name, keywords))
    blocked.update(TEXT_STOPWORDS)
    unigram_counter: Counter[str] = Counter()
    bigram_counter: Counter[str] = Counter()

    for paper in papers[:12]:
        title_tokens = [token for token in _tokenize(paper.get("title") or "") if len(token) >= 4]
        abstract_tokens = [token for token in _tokenize(paper.get("abstract") or "") if len(token) >= 4]

        for token in title_tokens:
            if token in blocked:
                continue
            unigram_counter[token] += 3
        for token in abstract_tokens[:40]:
            if token in blocked:
                continue
            unigram_counter[token] += 1

        for tokens, weight in ((title_tokens, 4), (abstract_tokens[:20], 1)):
            for idx in range(len(tokens) - 1):
                a, b = tokens[idx], tokens[idx + 1]
                if a in blocked or b in blocked:
                    continue
                phrase = f"{a} {b}"
                bigram_counter[phrase] += weight

    merged: list[str] = []
    for phrase, _ in bigram_counter.most_common(limit):
        merged.append(phrase.title())
    for token, _ in unigram_counter.most_common(limit * 2):
        merged.append(token.title())

    result = []
    seen = set()
    for item in merged:
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
        if len(result) >= limit:
            break
    return result


def _describe_route_shift(route_name: str, keywords: list[str], papers: list[dict]) -> tuple[list[str], list[str]]:
    recent_cutoff = datetime.utcnow() - timedelta(days=90)
    recent = [paper for paper in papers if (dt := _parse_date(paper.get("date"))) and dt >= recent_cutoff]
    older = [paper for paper in papers if (dt := _parse_date(paper.get("date"))) and dt < recent_cutoff]
    recent_terms = _extract_salient_terms(route_name, keywords, recent or papers, limit=4)
    older_terms = _extract_salient_terms(route_name, keywords, older, limit=3) if older else []
    return recent_terms, older_terms


def _paper_relevance_score(route_name: str, route_desc: str, keywords: list[str], paper: dict) -> float:
    title = (paper.get("title") or "").lower()
    abstract = (paper.get("abstract") or "").lower()
    venue = (paper.get("venue") or "").lower()
    text = " ".join([title, abstract, venue])
    seed_terms = [route_name, route_desc, *keywords]

    score = 0.0
    for term in seed_terms:
        normalized = str(term).strip().lower()
        if not normalized:
            continue
        if normalized in title:
            score += 5.0
        elif normalized in text:
            score += 2.0

    for token in _tokenize(route_name) + [item.lower() for item in keywords]:
        if token in title:
            score += 1.5
        elif token in text:
            score += 0.6

    dt = _parse_date(paper.get("date"))
    if dt:
        age_days = max((datetime.utcnow() - dt).days, 0)
        if age_days <= 30:
            score += 2.0
        elif age_days <= 90:
            score += 1.0
    elif paper.get("date"):
        score -= 3.0

    return score


def _rank_papers(route_name: str, route_desc: str, keywords: list[str], papers: list[dict]) -> list[dict]:
    ranked = sorted(
        papers,
        key=lambda paper: (
            _paper_relevance_score(route_name, route_desc, keywords, paper),
            _safe_date_key(paper.get("date")),
            paper.get("score") or 0,
        ),
        reverse=True,
    )
    route_phrase = route_name.lower()
    filtered = [
        paper
        for paper in ranked
        if _has_required_terms(route_name, paper)
        and (
            route_phrase in ((paper.get("title") or "").lower())
            or _term_hits(route_name, keywords, paper) >= 2
            or (len(_significant_terms(route_name, keywords)) <= 1 and _term_hits(route_name, keywords, paper) >= 1)
        )
    ]
    return filtered


def _papers_in_window(papers: list[dict], days: int) -> list[dict]:
    cutoff = datetime.utcnow() - timedelta(days=days)
    return [paper for paper in papers if (dt := _parse_date(paper.get("date"))) and dt >= cutoff]


def make_monthly_trend(seed: int) -> List[int]:
    base = max(seed, 6)
    values = []
    for idx in range(12):
        values.append(base + idx * max(1, base // 8))
    return values


def make_estimated_trend(seed_count: int, seed_text: str) -> List[int]:
    base = max(seed_count, 6)
    offset = sum(ord(ch) for ch in seed_text) % 5
    values = []
    current = max(2, base // 3)
    for idx in range(12):
        current += 1 + ((idx + offset) % 3 == 0)
        values.append(current)
    return values


def make_monthly_trend_from_dates(dates: list[str | None]) -> List[int]:
    today = datetime.utcnow()
    months = []
    year = today.year
    month = today.month
    for _ in range(12):
        months.append((year, month))
        month -= 1
        if month == 0:
            month = 12
            year -= 1
    months.reverse()

    parsed = [_parse_date(item) for item in dates]
    return [sum(1 for dt in parsed if dt and dt.year == item_year and dt.month == item_month) for item_year, item_month in months]


def _month_windows(months: int = 12) -> list[tuple[date, date]]:
    today = datetime.utcnow().date()
    year = today.year
    month = today.month
    windows: list[tuple[date, date]] = []
    for _ in range(months):
        start = date(year, month, 1)
        if month == 12:
            next_start = date(year + 1, 1, 1)
        else:
            next_start = date(year, month + 1, 1)
        windows.append((start, next_start - timedelta(days=1)))
        month -= 1
        if month == 0:
            month = 12
            year -= 1
    windows.reverse()
    return windows


def build_openalex_monthly_trend(route_name: str, keywords: list[str]) -> List[int]:
    query = " ".join(route_query_terms(route_name, keywords, limit=5))
    counts: list[int] = []
    for month_start, month_end in _month_windows(12):
        counts.append(count_openalex_works(query, from_date=month_start, to_date=month_end))
    return counts


def derive_keywords(route_name: str, route_desc: str, keywords: list[str], papers: list[dict]) -> list[str]:
    if keywords:
        return keywords[:6]
    preset_keywords = preset_keywords_for_route(route_name)
    if preset_keywords:
        return [route_name, *preset_keywords][:6]
    if not route_desc.strip():
        return route_seed_terms(route_name, [])[:6]

    stopwords = {
        "and", "for", "with", "from", "into", "using", "based", "toward", "towards",
        "the", "a", "an", "of", "in", "on", "to", "by", "via", "over", "under",
    }
    seed_text = " ".join([route_name, route_desc] + [paper.get("title", "") for paper in papers[:12]])
    tokens = []
    for token in seed_text.replace("/", " ").replace("-", " ").split():
        clean = token.strip(" ,.:;()[]{}'\"").lower()
        if len(clean) < 4 or clean in stopwords:
            continue
        tokens.append(clean)

    counter = Counter(tokens)
    merged = [route_name] + [token.title() for token, _ in counter.most_common(5)]
    result = []
    seen = set()
    for item in merged:
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result[:6]


def infer_topics(route_name: str, keywords: list[str], papers: list[dict], limit: int = 3) -> list[str]:
    return (_extract_salient_terms(route_name, keywords, papers, limit=limit + 2)[:limit]) or [route_name]


def _pick_recent_window(papers: list[dict]) -> tuple[list[dict], int]:
    for days, minimum_count in ((30, 3), (60, 3), (90, 2)):
        windowed = _papers_in_window(papers, days)
        if len(windowed) >= minimum_count:
            return windowed, days
    return (papers[:5], 180) if papers else ([], 180)


def _dedupe_topics(topics: list[str], route_name: str, limit: int = 3) -> list[str]:
    route_tokens = set(_tokenize(route_name))
    result: list[str] = []
    seen: set[str] = set()
    for topic in topics:
        value = str(topic or "").strip()
        if not value:
            continue
        key = value.lower()
        if key in seen:
            continue
        if set(_tokenize(value)).issubset(route_tokens) and route_tokens:
            continue
        seen.add(key)
        result.append(value)
        if len(result) >= limit:
            break
    return result or [route_name]


def _join_topics(topics: list[str], route_name: str) -> str:
    cleaned = _dedupe_topics(topics, route_name, limit=3)
    if len(cleaned) == 1:
        return cleaned[0]
    if len(cleaned) == 2:
        return f"{cleaned[0]} and {cleaned[1]}"
    return f"{cleaned[0]}, {cleaned[1]}, and {cleaned[2]}"


def _compose_year_focus(
    route_name: str,
    yearly_topics: list[str],
    recent_topics: list[str],
    older_topics: list[str],
) -> str:
    yearly_text = _join_topics(yearly_topics, route_name)
    recent_text = _join_topics(recent_topics, route_name)
    older_cleaned = _dedupe_topics(older_topics, route_name, limit=2)

    if older_cleaned and recent_text.lower() != _join_topics(older_cleaned, route_name).lower():
        older_text = _join_topics(older_cleaned, route_name)
        return (
            f"Over the last year, {route_name} papers have increasingly shifted from {older_text} "
            f"toward {recent_text}."
        )
    return f"Over the last year, {route_name} papers have mainly focused on {yearly_text}."


def _compose_recent_focus(route_name: str, recent_topics: list[str], recent_window_days: int) -> str:
    recent_text = _join_topics(recent_topics, route_name)
    if recent_window_days <= 90:
        return (
            f"Current papers in {route_name} are concentrating on {recent_text}, "
            f"which is where the route is moving most clearly right now."
        )
    return f"Current papers in {route_name} are mainly focused on {recent_text}."


def _compose_route_summary(route_name: str, route_desc: str, yearly_topics: list[str], recent_topics: list[str]) -> str:
    if route_desc.strip():
        return route_desc
    yearly_text = _join_topics(yearly_topics, route_name)
    recent_text = _join_topics(recent_topics, route_name)
    if yearly_text.lower() == recent_text.lower():
        return f"{route_name} has centered on {yearly_text} over the last year."
    return f"{route_name} has centered on {yearly_text}, with recent work leaning toward {recent_text}."


def derive_focus(
    route_name: str,
    route_desc: str,
    keywords: list[str],
    papers: list[dict],
    fallback_question: str | None,
) -> dict:
    ranked_papers = _rank_papers(route_name, route_desc, keywords, papers)
    recent_papers, recent_window_days = _pick_recent_window(ranked_papers)
    older_papers = [
        paper for paper in ranked_papers
        if paper not in recent_papers and (dt := _parse_date(paper.get("date")))
    ]

    yearly_topics = _dedupe_topics(
        _extract_title_focus_phrases(route_name, keywords, ranked_papers, limit=4)
        or _extract_salient_terms(route_name, keywords, ranked_papers, limit=4)
        or infer_topics(route_name, keywords, ranked_papers, limit=3),
        route_name,
        limit=3,
    )
    recent_topics = _dedupe_topics(
        _extract_title_focus_phrases(route_name, keywords, recent_papers, limit=4)
        or _extract_salient_terms(route_name, keywords, recent_papers, limit=4)
        or yearly_topics,
        route_name,
        limit=3,
    )
    older_topics = _dedupe_topics(
        _extract_salient_terms(route_name, keywords, older_papers, limit=3) if older_papers else [],
        route_name,
        limit=2,
    )

    route_question = _compose_year_focus(route_name, yearly_topics, recent_topics, older_topics)
    summary = _compose_route_summary(route_name, route_desc, yearly_topics, recent_topics)
    latest_problem = _compose_recent_focus(route_name, recent_topics, recent_window_days)
    latest_themes = recent_topics[:3]
    return {
        "route_question": route_question,
        "summary": summary,
        "latest_problem": latest_problem,
        "latest_themes": latest_themes,
    }


def select_recent_recommended_papers(
    route_name: str,
    route_desc: str,
    keywords: list[str],
    papers: list[dict],
    *,
    target_count: int = 6,
    minimum_count: int = 4,
) -> tuple[list[dict], int]:
    ranked = _rank_papers(route_name, route_desc, keywords, papers)
    for days in (30, 60, 90):
        windowed = _rank_papers(route_name, route_desc, keywords, _papers_in_window(ranked, days))
        if len(windowed) >= minimum_count:
            return windowed[:target_count], days

    fallback_window = _rank_papers(route_name, route_desc, keywords, _papers_in_window(ranked, 90))
    if fallback_window:
        return fallback_window[:target_count], 90
    return ranked[:target_count], 180


def select_focus_papers(
    route_name: str,
    route_desc: str,
    keywords: list[str],
    papers: list[dict],
    *,
    target_count: int = 5,
) -> tuple[list[dict], int]:
    ranked = _rank_papers(route_name, route_desc, keywords, papers)
    for days, minimum_count in ((30, 3), (60, 3), (90, 2)):
        windowed = _rank_papers(route_name, route_desc, keywords, _papers_in_window(ranked, days))
        if len(windowed) >= minimum_count:
            return windowed[:target_count], days
    return ranked[:target_count], 180


def filter_relevant_papers(route_name: str, route_desc: str, keywords: list[str], papers: list[dict]) -> list[dict]:
    return _rank_papers(route_name, route_desc, keywords, papers)


def ensure_route_snapshots(db: Session, *, use_claude: bool = False) -> int:
    created = 0
    taxonomy = load_taxonomy()
    for domain in taxonomy.get("domains", []):
        domain_name = domain.get("name", "")
        for section in domain.get("sections", []):
            section_name = section.get("name", "")
            for route_item in section.get("routes", []):
                if isinstance(route_item, str):
                    route = {
                        "name": route_item,
                        "desc": "",
                        "maturity": "增长期",
                        "hot": True,
                        "emerging": False,
                        "keywords": [],
                        "routeQuestion": f"{route_item} 当前最核心的研究问题是什么？",
                    }
                else:
                    route_name = route_item.get("name", "")
                    route = {
                        "name": route_name,
                        "desc": route_item.get("desc", ""),
                        "maturity": route_item.get("maturity", "增长期"),
                        "hot": bool(route_item.get("hot", True)),
                        "emerging": bool(route_item.get("emerging", False)),
                        "keywords": route_item.get("keywords", []),
                        "routeQuestion": route_item.get("routeQuestion", f"{route_name} 当前最核心的研究问题是什么？"),
                    }

                route_slug = f"{domain_name}-{section_name}-{route['name']}".replace(" ", "-").replace("/", "-")
                exists = db.query(RouteSnapshot).filter(RouteSnapshot.route_slug == route_slug).first()
                if exists:
                    continue

                fallback = derive_focus(route["name"], route["desc"], route.get("keywords", []), [], route.get("routeQuestion"))
                db.add(
                    RouteSnapshot(
                        domain=domain_name,
                        section_name=section_name,
                        route_name=route["name"],
                        route_slug=route_slug,
                        route_desc=route["desc"],
                        maturity=route["maturity"],
                        hot=route["hot"],
                        emerging=route["emerging"],
                        route_question=fallback["route_question"],
                        summary=fallback["summary"],
                        monthly_trend=[0] * 12,
                        keywords=derive_keywords(route["name"], route["desc"], route.get("keywords", []), []),
                        latest_problem=fallback["latest_problem"],
                        latest_themes=fallback["latest_themes"],
                        papers=[],
                    )
                )
                created += 1

    if created:
        db.commit()
    return created


def rebuild_route_snapshot(
    db: Session,
    *,
    domain: str,
    section_name: str,
    route_name: str,
    route_slug: str,
    route_desc: str,
    maturity: str,
    hot: bool,
    emerging: bool,
    keywords: list[str],
    fallback_question: str,
    use_claude: bool = True,
) -> None:
    rows = (
        db.query(RoutePaper, Paper)
        .join(Paper, RoutePaper.paper_id == Paper.id)
        .filter(RoutePaper.route_slug == route_slug)
        .order_by(Paper.published_date.desc().nullslast())
        .all()
    )

    all_papers = []
    for route_paper, paper in rows:
        try:
            authors = json.loads(paper.authors) if paper.authors else []
        except Exception:
            authors = []
        all_papers.append(
            {
                "title": paper.title,
                "abstract": paper.abstract,
                "url": paper.url,
                "date": paper.published_date,
                "venue": paper.venue,
                "authors": authors,
                "score": int(route_paper.score) if route_paper.score is not None else 80,
            }
        )

    effective_keywords = derive_keywords(route_name, route_desc, keywords, all_papers)
    relevant_papers = _rank_papers(route_name, route_desc, effective_keywords, all_papers)
    recommended_papers, _ = select_recent_recommended_papers(
        route_name, route_desc, effective_keywords, relevant_papers, target_count=6, minimum_count=4
    )
    focus_papers, _ = select_focus_papers(
        route_name, route_desc, effective_keywords, relevant_papers, target_count=5
    )
    fallback_focus = derive_focus(route_name, route_desc, effective_keywords, relevant_papers, fallback_question)

    if use_claude:
        try:
            llm = summarize_route(route_name, route_desc, focus_papers, fallback_question)
        except Exception:
            llm = fallback_focus
    else:
        llm = fallback_focus

    generic_themes = ["效果更强", "推理/训练成本更低", "更贴近真实应用场景"]
    if not llm.get("route_question") or "核心研究问题是什么" in llm.get("route_question", ""):
        llm["route_question"] = fallback_focus["route_question"]
    if not llm.get("summary"):
        llm["summary"] = fallback_focus["summary"]
    if not llm.get("latest_problem") or "近期论文主要在回答" in llm.get("latest_problem", ""):
        llm["latest_problem"] = fallback_focus["latest_problem"]
    if not llm.get("latest_themes") or llm.get("latest_themes") == generic_themes:
        llm["latest_themes"] = fallback_focus["latest_themes"]

    monthly = build_openalex_monthly_trend(route_name, effective_keywords)
    if not any(monthly):
        monthly = make_monthly_trend_from_dates([paper.get("date") for paper in relevant_papers])

    existing = db.query(RouteSnapshot).filter(RouteSnapshot.route_slug == route_slug).first()
    if existing:
        existing.domain = domain
        existing.section_name = section_name
        existing.route_name = route_name
        existing.route_desc = route_desc
        existing.maturity = maturity
        existing.hot = hot
        existing.emerging = emerging
        existing.route_question = llm["route_question"]
        existing.summary = llm["summary"]
        existing.monthly_trend = monthly
        existing.keywords = effective_keywords
        existing.latest_problem = llm["latest_problem"]
        existing.latest_themes = llm["latest_themes"]
        existing.papers = recommended_papers
    else:
        db.add(
            RouteSnapshot(
                domain=domain,
                section_name=section_name,
                route_name=route_name,
                route_slug=route_slug,
                route_desc=route_desc,
                maturity=maturity,
                hot=hot,
                emerging=emerging,
                route_question=llm["route_question"],
                summary=llm["summary"],
                monthly_trend=monthly,
                keywords=effective_keywords,
                latest_problem=llm["latest_problem"],
                latest_themes=llm["latest_themes"],
                papers=recommended_papers,
            )
        )
