from __future__ import annotations

import re
from datetime import datetime
from typing import Dict, List
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from config import Config
from news_collector import (
    _is_blocked_source,
    _is_file_like_title,
    _is_news_like_web_result,
    _publisher_from_url,
)


RESEARCH_SUFFIXES = [
    "",
    "기업정보",
    "사업 제품",
    "채용 복리후생",
    "복지",
    "근무제도",
    "면접",
]

CAREER_DOMAINS = [
    "jobkorea.co.kr",
    "incruit.com",
    "wanted.co.kr",
    "catch.co.kr",
    "work24.go.kr",
]

RESEARCH_PAGE_HINTS = [
    "회사소개",
    "기업정보",
    "사업",
    "제품",
    "채용",
    "인재채용",
    "복리후생",
    "복지",
    "근무제도",
    "면접",
    "직무",
]


def build_company_research_queries(company: str) -> List[str]:
    compact_company = company.strip()
    if not compact_company:
        return []
    return [f"{compact_company} {suffix}".strip() for suffix in RESEARCH_SUFFIXES]


def collect_company_research(company: str, *, limit: int = 18) -> Dict[str, object]:
    queries = build_company_research_queries(company)
    items: List[Dict[str, str]] = []
    errors: List[str] = []

    if not Config.KAKAO_REST_API_KEY:
        return {
            "queries": queries,
            "items": [],
            "error": "Kakao REST API 키가 없어 공개 검색 리서치를 건너뛰었습니다.",
        }

    for query in queries:
        try:
            items.extend(_collect_kakao_research(query=query, company=company, size=8))
        except requests.RequestException as exc:
            errors.append(f"{query}: {exc}")

    deduped = _dedupe_items(items)[:limit]
    return {
        "queries": queries,
        "items": deduped,
        "error": "; ".join(errors[:2]) if errors else "",
    }


def _collect_kakao_research(*, query: str, company: str, size: int) -> List[Dict[str, str]]:
    headers = {"Authorization": f"KakaoAK {Config.KAKAO_REST_API_KEY}"}
    endpoint = "https://dapi.kakao.com/v2/search/web.json"
    response = requests.get(
        endpoint,
        headers=headers,
        params={"query": query, "sort": "accuracy", "size": min(size, 50)},
        timeout=10,
    )
    response.raise_for_status()
    data = response.json()

    items: List[Dict[str, str]] = []
    for raw in data.get("documents", []):
        title = _strip_html(raw.get("title", ""))
        summary = _strip_html(raw.get("contents", ""))
        link = raw.get("url", "")
        text_blob = f"{title} {summary}"

        if not link or _is_file_like_title(title):
            continue
        if _is_blocked_source(link, text_blob):
            continue
        if not _mentions_company(text_blob, company):
            continue

        source_type = _classify_research_source(link, text_blob)
        if not source_type:
            continue

        items.append(
            {
                "query": query,
                "title": title,
                "summary": summary,
                "link": link,
                "outlet": _publisher_from_url(link),
                "source": "kakao",
                "source_type": source_type,
                "published": _format_kakao_datetime(raw.get("datetime", "")),
            }
        )
    return items


def _strip_html(text: str) -> str:
    return BeautifulSoup(text or "", "html.parser").get_text(" ", strip=True)


def _mentions_company(text: str, company: str) -> bool:
    compact_text = re.sub(r"\s+", "", text.lower())
    compact_company = re.sub(r"\s+", "", company.lower())
    if not compact_company:
        return False
    if compact_company in compact_text:
        return True
    if compact_company == "아진" and "아진산업" in compact_text:
        return True
    return False


def _classify_research_source(link: str, text: str) -> str:
    host = urlparse(link).netloc.lower().removeprefix("www.")
    compact_text = re.sub(r"\s+", "", text.lower())

    if _is_news_like_web_result(link):
        return "news"
    if any(host == domain or host.endswith(f".{domain}") for domain in CAREER_DOMAINS):
        return "career"
    if any(hint.lower().replace(" ", "") in compact_text for hint in RESEARCH_PAGE_HINTS):
        return "public"
    return ""


def _format_kakao_datetime(value: str) -> str:
    if not value:
        return ""
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return str(value)
    return dt.strftime("%Y-%m-%d %H:%M")


def _dedupe_items(items: List[Dict[str, str]]) -> List[Dict[str, str]]:
    seen = set()
    out: List[Dict[str, str]] = []
    for item in items:
        key = item.get("link") or item.get("title")
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out
