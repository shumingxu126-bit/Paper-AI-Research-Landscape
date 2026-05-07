from __future__ import annotations

import re


ROUTE_KEYWORD_PRESETS: dict[str, list[str]] = {
    "Embodied AI": ["robotics", "embodied", "manipulation", "navigation", "visuomotor"],
    "Human-AI Interaction": ["human-ai interaction", "user study", "interactive systems", "human factors"],
    "Multimodal Chat": ["vision-language dialogue", "multimodal assistant", "dialogue", "chat"],
    "Real-time Multimodal Agent": ["real-time", "multimodal agent", "streaming", "interactive agent"],
    "Image Understanding": ["image understanding", "visual recognition", "scene understanding", "vision"],
    "Video Understanding": ["video understanding", "temporal modeling", "video reasoning", "long video"],
    "Audio-Visual Understanding": ["audio-visual", "speech vision", "cross-modal understanding", "sound event"],
    "Multimodal Reasoning": ["multimodal reasoning", "vision-language reasoning", "chain-of-thought", "grounded reasoning"],
    "Document Intelligence": ["document intelligence", "ocr", "layout analysis", "document understanding"],
    "Spatial Understanding": ["3d understanding", "spatial reasoning", "geometry", "scene reconstruction"],
    "Image Generation": ["image generation", "diffusion", "text-to-image", "image synthesis"],
    "Video Generation": ["video generation", "text-to-video", "video diffusion", "motion generation"],
    "Audio / Music Generation": ["music generation", "audio generation", "speech synthesis", "sound synthesis"],
    "Multimodal Generation": ["multimodal generation", "cross-modal generation", "vision-language generation"],
    "Editing & Control": ["image editing", "controllable generation", "instruction editing", "visual editing"],
    "Multimodal Retrieval": ["multimodal retrieval", "cross-modal retrieval", "image-text retrieval", "search"],
    "RAG for Multimodal Knowledge": ["multimodal rag", "retrieval augmented generation", "knowledge grounding"],
    "Multimodal Evaluation": ["multimodal evaluation", "benchmark", "evaluation", "assessment"],
    "Training Systems for Multimodal Models": ["training systems", "distributed training", "multimodal systems", "serving"],
    "Vision-Language Pretraining": ["vision-language pretraining", "contrastive learning", "multimodal pretraining"],
    "Unified Multimodal Representation": ["multimodal representation", "joint embedding", "cross-modal representation"],
    "Multimodal Foundation Model": ["multimodal foundation model", "vision-language model", "foundation model"],
    "Sequential Recommendation": ["sequential recommendation", "next-item recommendation", "session-based recommendation"],
    "Candidate Generation": ["candidate generation", "retrieval recommendation", "two-tower", "matching"],
    "Ranking Models": ["ranking model", "ctr prediction", "learning to rank", "reranking"],
    "Multi-task Recommendation": ["multi-task recommendation", "multi-task learning", "shared representation"],
    "Multi-objective Optimization": ["multi-objective recommendation", "pareto optimization", "trade-off"],
    "LLM-based Recommendation": ["llm recommendation", "recommendation with llm", "large language model recommendation"],
    "Generative Recommendation": ["generative recommendation", "autoregressive recommendation", "generative retrieval"],
    "Conversational Recommendation": ["conversational recommendation", "dialogue recommendation", "interactive recommendation"],
    "Agentic Recommendation": ["agentic recommendation", "recommendation agent", "planning recommendation"],
    "Multimodal Recommendation": ["multimodal recommendation", "cross-modal recommendation", "content recommendation"],
    "Video Recommendation": ["video recommendation", "short video recommendation", "watch time"],
    "Cross-domain Recommendation": ["cross-domain recommendation", "transfer recommendation", "domain adaptation"],
    "Knowledge-enhanced Recommendation": ["knowledge graph recommendation", "knowledge-enhanced recommendation"],
    "Exploration & Exploitation": ["bandit recommendation", "exploration exploitation", "online learning"],
    "Reinforcement Learning for Recommendation": ["reinforcement learning recommendation", "policy learning", "reward modeling"],
    "Causal Recommendation": ["causal recommendation", "counterfactual recommendation", "de-bias recommendation"],
    "Long-term Value Optimization": ["long-term value recommendation", "lifetime value", "long horizon optimization"],
    "Uplift / Incrementality": ["uplift modeling", "incrementality", "treatment effect", "uplift recommendation"],
    "Real-time Feature Systems": ["real-time feature system", "feature store", "online serving", "low latency"],
    "Retrieval Stack": ["retrieval stack", "vector retrieval", "ann search", "retrieval system"],
    "Evaluation & Benchmarking": ["recommendation evaluation", "benchmark", "offline evaluation", "online evaluation"],
    "Fairness / Safety / Diversity": ["fairness recommendation", "safety recommendation", "diversity recommendation"],
}

ROUTE_QUERY_PRESETS: dict[str, list[str]] = {
    "Embodied AI": ["embodied ai", "robotics", "visuomotor", "embodied navigation"],
    "Human-AI Interaction": ["human-ai interaction", "human in the loop", "human factors", "user study"],
    "Multimodal Chat": ["multimodal chat", "multimodal assistant", "vision-language dialogue"],
    "Real-time Multimodal Agent": ["real-time multimodal agent", "streaming multimodal", "interactive agent"],
    "Multimodal Retrieval": ["multimodal retrieval", "cross-modal retrieval", "image-text retrieval"],
    "RAG for Multimodal Knowledge": ["multimodal rag", "retrieval augmented generation", "knowledge grounding"],
    "Multimodal Evaluation": ["multimodal evaluation", "multimodal benchmark"],
    "Training Systems for Multimodal Models": ["multimodal training systems", "distributed multimodal training", "multimodal serving"],
    "Sequential Recommendation": ["sequential recommendation", "next-item recommendation", "session-based recommendation"],
    "Generative Recommendation": ["generative recommendation", "autoregressive recommendation", "recommendation generation"],
    "LLM-based Recommendation": ["llm recommendation", "large language model recommendation"],
}

ROUTE_REQUIRED_TERMS: dict[str, list[str]] = {
    "Audio-Visual Understanding": ["audio", "speech", "sound", "visual", "video"],
    "Embodied AI": ["embodied", "robot", "robotic", "manipulation", "navigation"],
    "Human-AI Interaction": [
        "human-ai",
        "human ai",
        "human",
        "human-centered",
        "human centered",
        "human-in-the-loop",
        "human in the loop",
        "human factors",
        "human feedback",
        "feedback",
        "preference",
        "alignment",
        "user",
        "users",
        "user study",
        "user studies",
        "interface",
        "interaction",
        "interactive",
        "interactive system",
        "interactive ai",
        "hci",
    ],
    "Video Generation": ["video", "image-to-video", "text-to-video", "motion", "world model"],
    "Sequential Recommendation": ["recommendation"],
    "Candidate Generation": ["recommendation", "retrieval", "matching"],
    "Ranking Models": ["recommendation", "ranking", "ctr"],
    "Multi-task Recommendation": ["recommendation"],
    "Multi-objective Optimization": ["recommendation", "optimization"],
    "LLM-based Recommendation": ["recommendation"],
    "Generative Recommendation": ["recommendation"],
    "Conversational Recommendation": ["recommendation"],
    "Agentic Recommendation": ["recommendation"],
    "Multimodal Recommendation": ["recommendation"],
    "Video Recommendation": ["recommendation"],
    "Cross-domain Recommendation": ["recommendation"],
    "Knowledge-enhanced Recommendation": ["recommendation"],
    "Exploration & Exploitation": ["recommendation", "bandit"],
    "Reinforcement Learning for Recommendation": ["recommendation"],
    "Causal Recommendation": ["recommendation"],
    "Long-term Value Optimization": ["recommendation", "value"],
    "Uplift / Incrementality": ["uplift", "incrementality", "recommendation"],
    "Real-time Feature Systems": ["feature", "serving", "recommendation"],
    "Retrieval Stack": ["retrieval", "recommendation"],
    "Evaluation & Benchmarking": ["evaluation", "benchmark", "recommendation"],
    "Fairness / Safety / Diversity": ["recommendation", "fairness", "safety", "diversity"],
}

ROUTE_REQUIRED_MIN_HITS: dict[str, int] = {
    "Audio-Visual Understanding": 2,
    "Embodied AI": 2,
    "Human-AI Interaction": 2,
    "Video Generation": 1,
}


def _tokenize(value: str) -> list[str]:
    return re.findall(r"[a-z0-9][a-z0-9\-+/]*", value.lower())


def preset_keywords_for_route(route_name: str) -> list[str]:
    return ROUTE_KEYWORD_PRESETS.get(route_name, []).copy()


def preset_query_terms_for_route(route_name: str) -> list[str]:
    return ROUTE_QUERY_PRESETS.get(route_name, []).copy()


def required_terms_for_route(route_name: str) -> list[str]:
    return ROUTE_REQUIRED_TERMS.get(route_name, []).copy()


def required_min_hits_for_route(route_name: str) -> int:
    return ROUTE_REQUIRED_MIN_HITS.get(route_name, 1)


def matches_route_required_terms(route_name: str, haystack: str) -> bool:
    value = haystack.lower()
    if route_name == "Human-AI Interaction":
        def contains(signal: str) -> bool:
            if re.fullmatch(r"[a-z0-9]+", signal):
                return re.search(rf"\b{re.escape(signal)}\b", value) is not None
            return signal in value

        human_signals = [
            "human-ai",
            "human ai",
            "human-centered",
            "human centered",
            "human-in-the-loop",
            "human in the loop",
            "human feedback",
            "human factors",
            "user",
            "users",
            "participant",
            "participants",
            "preference",
            "feedback",
            "interface",
            "hci",
        ]
        ai_signals = [
            "ai",
            "artificial intelligence",
            "agent",
            "agents",
            "assistant",
            "assistants",
            "llm",
            "language model",
            "large language model",
            "automation",
            "alignment",
        ]
        exact_signals = ["human-ai", "human ai", "human-centered ai", "interactive ai"]
        return (
            any(contains(signal) for signal in exact_signals)
            or (
                any(contains(signal) for signal in human_signals)
                and any(contains(signal) for signal in ai_signals)
            )
        )

    required = required_terms_for_route(route_name)
    if not required:
        return True
    hits = sum(1 for term in required if term.lower() in value)
    return hits >= required_min_hits_for_route(route_name)


def route_seed_terms(route_name: str, keywords: list[str]) -> list[str]:
    terms = [route_name]
    terms.extend(preset_keywords_for_route(route_name))
    terms.extend(keywords)

    seen = set()
    result = []
    for term in terms:
        clean = str(term).strip()
        if not clean:
            continue
        key = clean.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(clean)
    return result


def route_query_terms(route_name: str, keywords: list[str], *, limit: int = 6) -> list[str]:
    base_terms = preset_query_terms_for_route(route_name) or preset_keywords_for_route(route_name) or [route_name]
    merged = [route_name, *base_terms, *keywords]
    result: list[str] = []
    seen: set[str] = set()
    for term in merged:
        clean = str(term).strip()
        if not clean:
            continue
        key = clean.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(clean)
        if len(result) >= limit:
            break
    return result


def route_token_terms(route_name: str, keywords: list[str]) -> list[str]:
    tokens: list[str] = []
    for term in route_seed_terms(route_name, keywords):
        tokens.extend(_tokenize(term))
    return list(dict.fromkeys(tokens))
