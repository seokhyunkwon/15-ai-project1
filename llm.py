from __future__ import annotations

import os
import time
from hashlib import sha256
from pathlib import Path
from typing import Any, Dict, List

import requests

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
CACHE_FILE = DATA_DIR / "llm_cache.json"


def llm_status() -> Dict[str, Any]:
    api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    return {
        "enabled": bool(api_key),
        "provider": "openai" if api_key else "",
    }


def build_news_brief(
    *,
    company: str,
    articles: List[Dict[str, str]],
    company_profile: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """
    Build a latest-news brief for job interview preparation.
    """
    company_profile = company_profile or {}
    status = llm_status()

    if not status["enabled"]:
        return _fallback_news_brief(company=company, articles=articles)

    api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    model = (os.getenv("OPENAI_MODEL") or "gpt-4o-mini").strip()
    if not model:
        model = "gpt-4o-mini"

    cache_key = _cache_key(
        kind="news_brief",
        company=company,
        model=model,
        articles=articles,
        company_profile=company_profile,
    )
    cached = _cache_get(cache_key)
    if cached:
        cached.setdefault("llm", {"enabled": True, "provider": "openai", "model": model})
        cached["cached"] = True
        return cached

    prompt = _news_brief_prompt(company=company, articles=articles, company_profile=company_profile)
    try:
        data = _openai_chat_with_retry(
            api_key=api_key,
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a career coach and analyst for Korean job seekers. "
                        "You must be factual, avoid hallucinations, and cite evidence by referencing the provided links. "
                        "Return JSON only."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
        )
    except Exception as exc:  # noqa: BLE001
        # If model is invalid, retry once with a safe default model.
        if _is_model_not_found(exc) and model != "gpt-4o-mini":
            try:
                model = "gpt-4o-mini"
                data = _openai_chat_with_retry(
                    api_key=api_key,
                    model=model,
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "You are a career coach and analyst for Korean job seekers. "
                                "You must be factual, avoid hallucinations, and cite evidence by referencing the provided links. "
                                "Return JSON only."
                            ),
                        },
                        {"role": "user", "content": prompt},
                    ],
                )
                parsed = _safe_parse_json(data)
                if parsed:
                    parsed.setdefault("company", company)
                    parsed.setdefault("sources", _sources_from_articles(articles))
                    parsed["llm"] = {"enabled": True, "provider": "openai", "model": model}
                    parsed["cached"] = False
                    _cache_set(
                        _cache_key(
                            kind="news_brief",
                            company=company,
                            model=model,
                            articles=articles,
                            company_profile=company_profile,
                        ),
                        parsed,
                    )
                    return parsed
            except Exception:
                pass
        out = _fallback_news_brief(company=company, articles=articles)
        out["error"] = f"LLM 호출 실패: {_format_openai_exception(exc)}"
        return out

    parsed = _safe_parse_json(data)
    if not parsed:
        out = _fallback_news_brief(company=company, articles=articles)
        out["error"] = "LLM 응답을 JSON으로 파싱하지 못했습니다."
        return out

    parsed.setdefault("company", company)
    parsed.setdefault("sources", _sources_from_articles(articles))
    parsed["llm"] = {"enabled": True, "provider": "openai", "model": model}
    parsed["cached"] = False
    _cache_set(cache_key, parsed)
    return parsed


def build_interview_questions_fallback(
    *,
    company: str,
    articles: List[Dict[str, str]],
    company_profile: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """
    Build interview questions from the visible article set.
    """
    company_profile = company_profile or {}
    status = llm_status()

    if not status["enabled"]:
        return _fallback_interview_questions(company=company, articles=articles)

    api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    model = (os.getenv("OPENAI_MODEL") or "gpt-4o-mini").strip() or "gpt-4o-mini"

    cache_key = _cache_key(
        kind="interview_questions",
        company=company,
        model=model,
        articles=articles,
        company_profile=company_profile,
    )
    cached = _cache_get(cache_key)
    if cached:
        cached.setdefault("llm", {"enabled": True, "provider": "openai", "model": model})
        cached["cached"] = True
        return cached

    prompt = _interview_questions_prompt(company=company, articles=articles, company_profile=company_profile)
    try:
        data = _openai_chat_with_retry(
            api_key=api_key,
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a career coach for Korean job seekers. "
                        "Only use the provided article snippets as evidence. "
                        "Return JSON only."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
        )
    except Exception as exc:  # noqa: BLE001
        out = _fallback_interview_questions(company=company, articles=articles)
        out["error"] = f"LLM 호출 실패: {_format_openai_exception(exc)}"
        return out

    parsed = _safe_parse_json(data)
    if not parsed:
        out = _fallback_interview_questions(company=company, articles=articles)
        out["error"] = "LLM 응답을 JSON으로 파싱하지 못했습니다."
        return out

    parsed.setdefault("company", company)
    parsed.setdefault("sources", _sources_from_articles(articles))
    parsed["llm"] = {"enabled": True, "provider": "openai", "model": model}
    parsed["cached"] = False
    _cache_set(cache_key, parsed)
    return parsed


def build_company_research(
    *,
    company: str,
    articles: List[Dict[str, str]],
    research_docs: List[Dict[str, str]],
    generated_queries: List[str] | None = None,
) -> Dict[str, Any]:
    """
    Build a public-source company research brief.
    """
    generated_queries = generated_queries or []
    status = llm_status()

    if not status["enabled"]:
        return _fallback_company_research(
            company=company,
            articles=articles,
            research_docs=research_docs,
            generated_queries=generated_queries,
        )

    api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    model = (os.getenv("OPENAI_MODEL") or "gpt-4o-mini").strip() or "gpt-4o-mini"
    cache_key = _cache_key(
        kind="company_research",
        company=company,
        model=model,
        articles=articles + research_docs,
        company_profile={"generated_queries": generated_queries},
    )
    cached = _cache_get(cache_key)
    if cached:
        cached.setdefault("llm", {"enabled": True, "provider": "openai", "model": model})
        cached["cached"] = True
        return cached

    prompt = _company_research_prompt(
        company=company,
        articles=articles,
        research_docs=research_docs,
        generated_queries=generated_queries,
    )
    try:
        data = _openai_chat_with_retry(
            api_key=api_key,
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a Korean career research analyst. "
                        "Use only the provided public snippets and news. "
                        "Do not pretend to have employee review data. "
                        "When evidence is weak, say it is a signal or insufficient. "
                        "Return JSON only."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
        )
    except Exception as exc:  # noqa: BLE001
        out = _fallback_company_research(
            company=company,
            articles=articles,
            research_docs=research_docs,
            generated_queries=generated_queries,
        )
        out["error"] = f"LLM 호출 실패: {_format_openai_exception(exc)}"
        return out

    parsed = _safe_parse_json(data)
    if not parsed:
        out = _fallback_company_research(
            company=company,
            articles=articles,
            research_docs=research_docs,
            generated_queries=generated_queries,
        )
        out["error"] = "LLM 응답을 JSON으로 파싱하지 못했습니다."
        return out

    parsed.setdefault("company", company)
    parsed.setdefault("generated_queries", generated_queries)
    parsed.setdefault("sources", _sources_from_articles(articles + research_docs))
    parsed["llm"] = {"enabled": True, "provider": "openai", "model": model}
    parsed["cached"] = False
    _cache_set(cache_key, parsed)
    return parsed


def _openai_chat_with_retry(
    *,
    api_key: str,
    model: str,
    messages: List[Dict[str, str]],
    max_retries: int = 2,
) -> str:
    last_exc: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            return _openai_chat(api_key=api_key, model=model, messages=messages)
        except requests.HTTPError as exc:
            last_exc = exc
            resp = getattr(exc, "response", None)
            status = getattr(resp, "status_code", None)
            if status != 429 or attempt >= max_retries:
                raise
            retry_after = 0
            if resp is not None:
                ra = resp.headers.get("Retry-After")
                if ra and ra.isdigit():
                    retry_after = int(ra)
            # Keep backoff short to avoid blocking web request too long.
            sleep_s = min(max(1, 2**attempt), 3) + min(retry_after, 2)
            time.sleep(sleep_s)
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            raise
    if last_exc:
        raise last_exc
    raise RuntimeError("LLM 호출 실패")


def _openai_chat(*, api_key: str, model: str, messages: List[Dict[str, str]]) -> str:
    url = "https://api.openai.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
    }
    resp = requests.post(url, headers=headers, json=payload, timeout=30)
    resp.raise_for_status()
    body = resp.json()
    return body["choices"][0]["message"]["content"]


def _news_brief_prompt(*, company: str, articles: List[Dict[str, str]], company_profile: Dict[str, Any]) -> str:
    top = articles[:8]
    sources = [
        {
            "title": a.get("title", ""),
            "summary": a.get("summary", ""),
            "published": a.get("published", ""),
            "link": a.get("link", ""),
            "source": a.get("source", ""),
            "outlet": a.get("outlet", ""),
        }
        for a in top
    ]

    return (
        f"회사명: {company}\n"
        f"회사 프로필(가능한 범위): {company_profile}\n\n"
        "아래는 최신 뉴스 목록(최대 12개)이다. 이 데이터만 근거로 삼아 면접 준비에 도움이 되는 브리핑을 생성하라.\n"
        "반드시 링크를 근거로 포함해야 하며, 모르는 내용은 추측하지 마라.\n\n"
        "출력은 JSON 하나로만 반환하라. 스키마:\n"
        "{\n"
        '  "company": string,\n'
        '  "highlights": [{"claim": string, "why_it_matters": string, "evidence_links": [string]}],\n'
        '  "risks_and_watchouts": [{"item": string, "evidence_links": [string]}],\n'
        '  "keywords_to_prepare": [string],\n'
        '  "sources": [{"title": string, "link": string, "published": string, "outlet": string}]\n'
        "}\n\n"
        f"뉴스 목록: {sources}\n"
    )

def _interview_questions_prompt(*, company: str, articles: List[Dict[str, str]], company_profile: Dict[str, Any]) -> str:
    top = articles[:8]
    sources = [
        {
            "title": a.get("title", ""),
            "summary": a.get("summary", ""),
            "published": a.get("published", ""),
            "link": a.get("link", ""),
            "outlet": a.get("outlet", ""),
        }
        for a in top
    ]
    return (
        f"회사명: {company}\n"
        f"회사 프로필(가능한 범위): {company_profile}\n\n"
        "아래 최신 뉴스만 근거로, 면접에서 나올 법한 질문을 생성하라.\n"
        "출력은 JSON 하나로만 반환하라. 스키마:\n"
        "{\n"
        '  "company": string,\n'
        '  "likely_interview_questions": [{"question": string, "intent": string, "answer_outline": [string], "evidence_links": [string]}],\n'
        '  "sources": [{"title": string, "link": string, "published": string, "outlet": string}]\n'
        "}\n\n"
        f"뉴스 목록: {sources}\n"
    )


def _company_research_prompt(
    *,
    company: str,
    articles: List[Dict[str, str]],
    research_docs: List[Dict[str, str]],
    generated_queries: List[str],
) -> str:
    news_sources = [
        {
            "title": a.get("title", ""),
            "summary": a.get("summary", ""),
            "published": a.get("published", ""),
            "link": a.get("link", ""),
            "outlet": a.get("outlet", ""),
        }
        for a in articles[:10]
    ]
    public_sources = [
        {
            "query": d.get("query", ""),
            "title": d.get("title", ""),
            "summary": d.get("summary", ""),
            "link": d.get("link", ""),
            "outlet": d.get("outlet", ""),
            "source_type": d.get("source_type", ""),
            "published": d.get("published", ""),
        }
        for d in research_docs[:18]
    ]
    return (
        f"회사명: {company}\n"
        f"자동 생성 검색어: {generated_queries}\n\n"
        "아래 공개 검색 결과와 뉴스 스니펫만 근거로 취업 준비용 AI 기업 리서치를 작성하라.\n"
        "블라인드/커뮤니티/비공개 후기를 본 것처럼 말하지 마라.\n"
        "복지, 워라밸, 근무제도는 단정하지 말고 공개 자료에서 보이는 '신호'와 '확인 필요 포인트'로 정리하라.\n"
        "각 주장에는 가능한 evidence_links를 포함하라.\n\n"
        "출력은 JSON 하나로만 반환하라. 스키마:\n"
        "{\n"
        '  "company": string,\n'
        '  "company_overview": [string],\n'
        '  "recent_issues": [{"point": string, "evidence_links": [string]}],\n'
        '  "business_keywords": [string],\n'
        '  "welfare_signals": [{"signal": string, "confidence": string, "evidence_links": [string]}],\n'
        '  "work_life_notes": [string],\n'
        '  "likely_interview_questions": [{"question": string, "intent": string, "answer_direction": [string], "evidence_links": [string]}],\n'
        '  "answer_strategy": [string],\n'
        '  "generated_queries": [string],\n'
        '  "sources": [{"title": string, "link": string, "outlet": string, "source_type": string}]\n'
        "}\n\n"
        f"뉴스 스니펫: {news_sources}\n\n"
        f"공개 검색 스니펫: {public_sources}\n"
    )


def _fallback_news_brief(*, company: str, articles: List[Dict[str, str]]) -> Dict[str, Any]:
    sources = _sources_from_articles(articles)
    highlights = []
    for a in articles[:5]:
        title = (a.get("title") or "").strip()
        link = (a.get("link") or "").strip()
        if not title:
            continue
        highlights.append(
            {
                "claim": title,
                "why_it_matters": "기사 제목/요약 기반 요약(LLM 미설정). 링크를 열어 세부 내용을 확인하세요.",
                "evidence_links": [link] if link else [],
            }
        )

    return {
        "company": company,
        "highlights": highlights,
        "risks_and_watchouts": [],
        "keywords_to_prepare": [],
        "sources": sources,
        "llm": {"enabled": False, "provider": "", "model": ""},
    }

def _fallback_interview_questions(*, company: str, articles: List[Dict[str, str]]) -> Dict[str, Any]:
    sources = _sources_from_articles(articles)
    questions = [
        {
            "question": f"{company}의 최근 주요 이슈(기사 기준)를 한 가지 설명하고, 지원 직무와 연결해보세요.",
            "intent": "최근 동향 이해도 + 직무 연결 능력",
            "answer_outline": ["핵심 이슈 1개 선정", "기사 근거 1~2개 인용", "직무 관점 영향", "내 경험/역량 연결"],
            "evidence_links": [s["link"] for s in sources[:2] if s.get("link")],
        }
    ]
    return {
        "company": company,
        "likely_interview_questions": questions,
        "sources": sources,
        "llm": {"enabled": False, "provider": "", "model": ""},
    }


def _fallback_company_research(
    *,
    company: str,
    articles: List[Dict[str, str]],
    research_docs: List[Dict[str, str]],
    generated_queries: List[str],
) -> Dict[str, Any]:
    sources = _sources_from_articles(articles + research_docs)
    welfare_docs = [
        d for d in research_docs
        if any(token in f"{d.get('title', '')} {d.get('summary', '')}" for token in ("복지", "복리후생", "근무제도", "채용", "면접"))
    ]
    return {
        "company": company,
        "company_overview": [
            f"{company} 관련 공개 검색 결과와 최신 뉴스 기반 리서치입니다.",
            "LLM 키가 없거나 호출에 실패한 경우라 세부 해석은 제한됩니다.",
        ],
        "recent_issues": [
            {
                "point": a.get("title", ""),
                "evidence_links": [a.get("link", "")] if a.get("link") else [],
            }
            for a in articles[:3]
            if a.get("title")
        ],
        "business_keywords": list(
            dict.fromkeys(
                [a.get("category", "") for a in articles if a.get("category")]
                + [a.get("keyword", "") for a in articles if a.get("keyword")]
            )
        )[:8],
        "welfare_signals": [
            {
                "signal": d.get("title", ""),
                "confidence": "낮음",
                "evidence_links": [d.get("link", "")] if d.get("link") else [],
            }
            for d in welfare_docs[:4]
        ],
        "work_life_notes": [
            "공개 검색 스니펫만으로 워라밸을 단정할 수 없습니다.",
            "채용공고의 근무제도, 복리후생, 조직/직무 설명을 면접 전 추가 확인하세요.",
        ],
        "likely_interview_questions": [
            {
                "question": f"{company}의 최근 이슈를 지원 직무와 연결해 설명해보세요.",
                "intent": "회사 이해도와 직무 연결 능력 확인",
                "answer_direction": ["최근 기사 1개 선택", "사업/제품 키워드 연결", "내 경험과 기여 방향 제시"],
                "evidence_links": [s["link"] for s in sources[:2] if s.get("link")],
            }
        ],
        "answer_strategy": [
            "기사 제목만 외우기보다 이슈가 회사의 제품, 고객, 품질, 공급망에 주는 영향을 정리하세요.",
            "복지와 워라밸은 단정 표현 대신 공개 채용 자료 기준으로 확인한 내용만 말하세요.",
        ],
        "generated_queries": generated_queries,
        "sources": sources,
        "llm": {"enabled": False, "provider": "", "model": ""},
    }


def _sources_from_articles(articles: List[Dict[str, str]]) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    for a in articles[:12]:
        out.append(
            {
                "title": (a.get("title") or "").strip(),
                "link": (a.get("link") or "").strip(),
                "published": (a.get("published") or "").strip(),
                "outlet": (a.get("outlet") or "").strip(),
                "source_type": (a.get("source_type") or a.get("source") or "").strip(),
            }
        )
    return out


def _safe_parse_json(text: str) -> Dict[str, Any] | None:
    import json

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _cache_key(
    *,
    kind: str,
    company: str,
    model: str,
    articles: List[Dict[str, str]],
    company_profile: Dict[str, Any],
) -> str:
    # Stable key based on company+model+top sources.
    src = _sources_from_articles(articles)
    material = {
        "kind": kind,
        "company": company,
        "model": model,
        "sources": src,
        "company_profile": company_profile,
    }
    import json

    blob = json.dumps(material, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return sha256(blob).hexdigest()


def _cache_get(key: str) -> Dict[str, Any] | None:
    import json

    if not CACHE_FILE.exists():
        return None
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        value = data.get(key)
        if isinstance(value, dict):
            return value
        return None
    except Exception:  # noqa: BLE001
        return None


def _cache_set(key: str, value: Dict[str, Any]) -> None:
    import json

    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        data: Dict[str, Any] = {}
        if CACHE_FILE.exists():
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                data = loaded
        # Avoid unbounded growth in dev.
        if len(data) > 200:
            data = {}
        data[key] = value
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        # Best-effort cache; ignore.
        return


def _format_openai_exception(exc: Exception) -> str:
    """
    Provide actionable OpenAI error details without leaking secrets.
    """
    if isinstance(exc, requests.HTTPError):
        resp = getattr(exc, "response", None)
        status = getattr(resp, "status_code", None)
        code, message, request_id = _extract_openai_error(resp)
        parts = []
        if status:
            parts.append(str(status))
        if code:
            parts.append(code)
        if request_id:
            parts.append(f"request_id={request_id}")
        head = " / ".join(parts) if parts else "HTTPError"
        if message:
            return f"{head} - {message}"
        return head
    return str(exc)


def _is_model_not_found(exc: Exception) -> bool:
    if not isinstance(exc, requests.HTTPError):
        return False
    resp = getattr(exc, "response", None)
    code, _, _ = _extract_openai_error(resp)
    return code == "model_not_found"


def _extract_openai_error(resp: requests.Response | None) -> tuple[str, str, str]:
    """
    Attempts to parse OpenAI error JSON:
    { "error": { "message": "...", "type": "...", "code": "..." } }
    """
    if resp is None:
        return ("", "", "")
    request_id = resp.headers.get("x-request-id", "") or resp.headers.get("request-id", "") or ""
    try:
        data = resp.json()
    except Exception:  # noqa: BLE001
        text = (resp.text or "").strip()
        return ("", text[:300], request_id)

    err = data.get("error") if isinstance(data, dict) else None
    if not isinstance(err, dict):
        return ("", "", request_id)
    code = str(err.get("code") or "").strip()
    message = str(err.get("message") or "").strip()
    return (code, message, request_id)

