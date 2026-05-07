from app.db.session import SessionLocal
from app.services.taxonomy_loader import load_taxonomy
from app.services.openalex_client import fetch_openalex
from app.services.arxiv_client import fetch_arxiv
from app.services.claude_client import summarize_route
from app.services.refresh_service import normalize_route, build_query


def main():
    print("=== debug start ===")

    # 1. 测 taxonomy
    taxonomy = load_taxonomy()
    print("taxonomy type:", type(taxonomy))
    print("taxonomy keys:", list(taxonomy.keys()) if isinstance(taxonomy, dict) else "not dict")

    if isinstance(taxonomy, dict) and "domains" in taxonomy:
        domains = taxonomy["domains"]
    elif isinstance(taxonomy, list):
        domains = taxonomy
    else:
        print("taxonomy structure invalid")
        return

    print("domains count:", len(domains))

    # 2. 取第一条 route 做最小测试
    first_domain = domains[0]
    first_section = first_domain["sections"][0]
    first_route_item = first_section["routes"][0]
    route = normalize_route(first_route_item)

    domain_name = first_domain["name"]
    section_name = first_section["name"]
    route_name = route["name"]
    route_desc = route.get("desc", "")
    keywords = route.get("keywords", [])
    fallback_question = route.get("routeQuestion", f"{route_name} 的核心研究问题是什么？")
    query = build_query(route_name, keywords)

    print("domain:", domain_name)
    print("section:", section_name)
    print("route:", route_name)
    print("query:", query)

    # 3. 测 OpenAlex
    papers = []
    try:
        print("fetching openalex...")
        oa = fetch_openalex(query, per_page=3)
        print("openalex ok, count =", len(oa))
        papers.extend(oa)
    except Exception as e:
        print("openalex failed:", repr(e))

    # 4. 测 arXiv
    try:
        print("fetching arxiv...")
        ax = fetch_arxiv(query, max_results=3)
        print("arxiv ok, count =", len(ax))
        papers.extend(ax)
    except Exception as e:
        print("arxiv failed:", repr(e))

    # 5. 去重后看论文
    deduped = []
    seen = set()
    for p in papers:
        title = (p.get("title") or "").strip().lower()
        if not title or title in seen:
            continue
        seen.add(title)
        deduped.append(p)

    papers = deduped[:5]
    print("papers after dedupe =", len(papers))

    for i, p in enumerate(papers, 1):
        print(f"[{i}] {p.get('title')}")

    # 6. 测 Claude
    try:
        print("calling claude...")
        llm = summarize_route(route_name, route_desc, papers, fallback_question)
        print("claude ok")
        print("route_question:", llm.get("route_question"))
        print("summary:", llm.get("summary"))
        print("latest_problem:", llm.get("latest_problem"))
        print("latest_themes:", llm.get("latest_themes"))
    except Exception as e:
        print("claude failed:", repr(e))

    # 7. 测数据库连接
    try:
        print("testing db session...")
        db = SessionLocal()
        from sqlalchemy import text
        db.execute(text("SELECT 1"))
        db.close()
        print("db ok")
    except Exception as e:
        print("db failed:", repr(e))

    print("=== debug end ===")


if __name__ == "__main__":
    main()