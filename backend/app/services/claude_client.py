from __future__ import annotations

import json
import re
from typing import Dict, List

import requests

from app.core.settings import get_settings

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"


def _fallback(route_name: str, route_desc: str, fallback_question: str) -> Dict:
    summary = route_desc or f"{route_name} is an active research route."
    return {
        "route_question": fallback_question,
        "summary": summary,
        "latest_problem": f"Current papers in {route_name} are focused on the route's most active technical problems.",
        "latest_themes": [route_name],
    }


def _compact_papers(papers: List[Dict]) -> List[Dict]:
    return [
        {
            "title": p.get("title", ""),
            "date": p.get("date", ""),
            "venue": p.get("venue", ""),
            "abstract": (p.get("abstract") or "")[:1000],
        }
        for p in papers[:10]
    ]


def _system_prompt() -> str:
    return (
        "You are an AI research analyst. Return strict JSON only, with exactly these keys: "
        "route_question, summary, latest_problem, latest_themes. "
        "route_question should summarize what papers under this route focused on over the last year. "
        "latest_problem should summarize what recent papers, roughly the last 1-3 months, are focused on. "
        "summary should be a concise route overview. "
        "latest_themes must be an array of 3 short English technical phrases. "
        "Do not mention representative works, do not list paper titles, and do not use generic wording "
        "such as effectiveness, efficiency, deployability, or stable usable solution unless the papers specifically support it."
    )


def _user_payload(route_name: str, route_desc: str, papers: List[Dict], fallback_question: str) -> str:
    return json.dumps(
        {
            "route_name": route_name,
            "route_desc": route_desc,
            "fallback_question": fallback_question,
            "papers": _compact_papers(papers),
        },
        ensure_ascii=False,
    )


def _extract_json(text: str) -> Dict:
    cleaned = (text or "").strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, re.DOTALL)
    if fenced:
        cleaned = fenced.group(1)
    return json.loads(cleaned)


def _normalize_result(data: Dict, route_name: str, route_desc: str, fallback_question: str) -> Dict:
    themes = data.get("latest_themes") or []
    if not isinstance(themes, list):
        themes = [str(themes)]
    themes = [str(item).strip() for item in themes if str(item).strip()][:3]
    if not themes:
        themes = [route_name]

    return {
        "route_question": data.get("route_question") or fallback_question,
        "summary": data.get("summary") or route_desc or f"{route_name} is an active research route.",
        "latest_problem": data.get("latest_problem")
        or f"Current papers in {route_name} are focused on the route's most active technical problems.",
        "latest_themes": themes,
    }


def _summarize_with_minimax(route_name: str, route_desc: str, papers: List[Dict], fallback_question: str) -> Dict:
    settings = get_settings()
    url = f"{settings.minimax_base_url.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.minimax_api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": settings.minimax_model,
        "messages": [
            {"role": "system", "content": _system_prompt()},
            {"role": "user", "content": _user_payload(route_name, route_desc, papers, fallback_question)},
        ],
        "temperature": 0.2,
        "max_tokens": 900,
    }
    resp = requests.post(url, headers=headers, json=payload, timeout=60)
    resp.raise_for_status()
    content = resp.json()["choices"][0]["message"]["content"]
    return _normalize_result(_extract_json(content), route_name, route_desc, fallback_question)


def _summarize_with_anthropic(route_name: str, route_desc: str, papers: List[Dict], fallback_question: str) -> Dict:
    settings = get_settings()
    headers = {
        "x-api-key": settings.anthropic_api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    payload = {
        "model": settings.anthropic_model,
        "max_tokens": 900,
        "temperature": 0.2,
        "system": _system_prompt(),
        "messages": [{"role": "user", "content": _user_payload(route_name, route_desc, papers, fallback_question)}],
    }
    resp = requests.post(ANTHROPIC_API_URL, headers=headers, json=payload, timeout=60)
    resp.raise_for_status()
    content = resp.json()["content"][0]["text"]
    return _normalize_result(_extract_json(content), route_name, route_desc, fallback_question)


def summarize_route(route_name: str, route_desc: str, papers: List[Dict], fallback_question: str) -> Dict:
    settings = get_settings()
    provider = (settings.llm_provider or "").strip().lower()
    try:
        if provider == "minimax" and settings.minimax_api_key:
            return _summarize_with_minimax(route_name, route_desc, papers, fallback_question)
        if provider == "anthropic" and settings.anthropic_api_key:
            return _summarize_with_anthropic(route_name, route_desc, papers, fallback_question)
    except Exception:
        return _fallback(route_name, route_desc, fallback_question)
    return _fallback(route_name, route_desc, fallback_question)
