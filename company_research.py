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
    "기업 복리후생",
    "사람인 기업정보",
    "사람인 복리후생",
    "사람인 면접후기",
    "복지",
    "근무제도",
    "면접",
]

CAREER_DOMAINS = [
    "saramin.co.kr",
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

        item = {
            "query": query,
            "title": title,
            "summary": summary,
            "link": link,
            "outlet": _publisher_from_url(link),
            "source": "kakao",
            "source_type": source_type,
            "published": _format_kakao_datetime(raw.get("datetime", "")),
        }
        item = _enrich_career_page(item, company=company)
        items.append(item)
    return items


def _strip_html(text: str) -> str:
    return BeautifulSoup(text or "", "html.parser").get_text(" ", strip=True)


def _mentions_company(text: str, company: str) -> bool:
    compact_text = re.sub(r"\s+", "", text.lower())
    variants = _company_variants(company)
    if not variants:
        return False
    return any(variant in compact_text for variant in variants)


def _company_variants(company: str) -> List[str]:
    aliases = {
        "아진": ["아진", "아진산업"],
        "thn": ["thn", "티에이치엔"],
        "티에이치엔": ["티에이치엔", "thn"],
    }
    compact_company = re.sub(r"\s+", "", company.lower())
    if not compact_company:
        return []
    return [
        re.sub(r"\s+", "", value.lower())
        for value in aliases.get(compact_company, [company])
    ]


def _classify_research_source(link: str, text: str) -> str:
    host = urlparse(link).netloc.lower().removeprefix("www.")
    compact_text = re.sub(r"\s+", "", text.lower())

    if _is_news_like_web_result(link):
        return "news"
    if any(host == domain or host.endswith(f".{domain}") for domain in CAREER_DOMAINS):
        if _is_interview_review_page(link):
            return "interview_review"
        return "company_info" if _is_company_info_page(link, text) else ""
    if any(hint.lower().replace(" ", "") in compact_text for hint in RESEARCH_PAGE_HINTS):
        return "public"
    return ""


def _is_company_info_page(link: str, text: str) -> bool:
    parsed = urlparse(link)
    host = parsed.netloc.lower().removeprefix("www.")
    path = parsed.path.lower()
    compact = re.sub(r"\s+", "", text.lower())

    if _is_recruit_posting_link(link):
        return False
    if host.endswith("saramin.co.kr"):
        return path.startswith("/zf_user/company-info/view")
    if host.endswith("jobkorea.co.kr"):
        return "/company/" in path or "기업정보" in compact
    if host.endswith("catch.co.kr"):
        return "comp" in path or "기업정보" in compact
    if host.endswith("wanted.co.kr"):
        return "/company/" in path or "회사소개" in compact
    if host.endswith("incruit.com"):
        return "company" in path or "기업정보" in compact
    if host.endswith("work24.go.kr"):
        return "기업정보" in compact or "복리후생" in compact
    return any(hint.lower().replace(" ", "") in compact for hint in ("기업정보", "회사소개", "복리후생", "근무제도"))


def _is_interview_review_page(link: str) -> bool:
    parsed = urlparse(link)
    host = parsed.netloc.lower().removeprefix("www.")
    path = parsed.path.lower()
    return host.endswith("saramin.co.kr") and (
        path.startswith("/zf_user/interview-review")
        or path.startswith("/zf_user/interview-review/detail")
    )


def _is_recruit_posting_link(link: str) -> bool:
    parsed = urlparse(link)
    path = parsed.path.lower()
    query = parsed.query.lower()
    blob = f"{path}?{query}"
    recruit_hints = (
        "/zf_user/jobs/",
        "/recruit/",
        "/jobs/",
        "/job/",
        "rec_idx=",
        "job_idx=",
        "recruitview",
        "recruit/view",
    )
    return any(hint in blob for hint in recruit_hints)


def _enrich_career_page(item: Dict[str, str], *, company: str) -> Dict[str, str]:
    host = urlparse(item.get("link", "")).netloc.lower().removeprefix("www.")
    if not any(host == domain or host.endswith(f".{domain}") for domain in CAREER_DOMAINS):
        return item
    source_type = item.get("source_type", "")
    if source_type not in {"company_info", "interview_review"}:
        return item

    try:
        response = requests.get(
            item["link"],
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=8,
        )
        response.raise_for_status()
    except requests.RequestException:
        return item

    text = BeautifulSoup(response.text or "", "html.parser").get_text("\n", strip=True)
    if not _mentions_company(text, company):
        return item

    if source_type == "interview_review":
        snippets = _extract_interview_snippets(text)
    else:
        snippets = _extract_relevant_snippets(text)
    if snippets:
        item["summary"] = " / ".join(snippets[:12])
        item["source_type"] = source_type
    return item


def _extract_relevant_snippets(text: str) -> List[str]:
    tokens = (
        "복리후생",
        "복지",
        "근무",
        "휴가",
        "식당",
        "카페",
        "통근",
        "출산",
        "육아",
        "장기근속",
        "수당",
        "멘토링",
        "건강",
        "주차",
    )
    chunks = re.split(r"[\n\r]+|(?<=[.!?。])\s+", text)
    snippets: List[str] = []
    seen = set()
    for chunk in chunks:
        cleaned = chunk.strip(" -·•\t\r\n")
        if not (4 <= len(cleaned) <= 80):
            continue
        compact = re.sub(r"\s+", "", cleaned.lower())
        if compact in seen:
            continue
        if any(token.lower() in compact for token in tokens):
            seen.add(compact)
            snippets.append(cleaned)
    return snippets


def _extract_interview_snippets(text: str) -> List[str]:
    first_review = text.find("전반적 평가")
    if first_review >= 0:
        text = text[first_review:]

    tokens = (
        "면접",
        "난이도",
        "결과",
        "질문",
        "전형",
        "진행",
        "분위기",
        "면접관",
        "지원자",
        "인성",
        "직무",
        "경력",
        "이직",
        "지원동기",
        "홈페이지",
        "사업",
        "팀워크",
        "장단점",
        "1분 자기소개",
        "자기소개",
    )
    blocked = (
        "사람인 고객센터",
        "이메일",
        "FAX",
        "회원가입",
        "로그인",
        "광고",
        "면접 코칭",
        "면접후기",
        "면접 경험, 공유해줘서",
        "면접 후기 등록하기",
        "직무·직업 전체",
        "후기상세보기",
    )
    chunks = re.split(r"[\n\r]+|(?<=[.!?。])\s+", text)
    snippets: List[str] = []
    seen = set()
    for chunk in chunks:
        cleaned = chunk.strip(" -·•\t\r\n")
        if not (3 <= len(cleaned) <= 120):
            continue
        if any(word.lower() in cleaned.lower() for word in blocked):
            continue
        compact = re.sub(r"\s+", "", cleaned.lower())
        if compact in seen:
            continue
        if any(token.lower().replace(" ", "") in compact for token in tokens):
            seen.add(compact)
            snippets.append(cleaned)
    return snippets


def _format_kakao_datetime(value: str) -> str:
    if not value:
        return ""
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return str(value)
    return dt.strftime("%Y-%m-%d %H:%M")


def _dedupe_items(items: List[Dict[str, str]]) -> List[Dict[str, str]]:
    best_by_key: Dict[tuple[str, str, str], Dict[str, str]] = {}
    for item in items:
        key = _dedupe_key(item)
        current = best_by_key.get(key)
        if current is None or _item_score(item) > _item_score(current):
            best_by_key[key] = item
    return list(best_by_key.values())


def _dedupe_key(item: Dict[str, str]) -> tuple[str, str, str]:
    source_type = item.get("source_type", "")
    host = _publisher_from_url(item.get("link", "")).lower()
    title = _normalize_title(item.get("title", ""))

    if source_type in {"company_info", "interview_review"}:
        return source_type, host, title

    link = item.get("link", "")
    return source_type, host, link or title


def _normalize_title(value: str) -> str:
    cleaned = BeautifulSoup(value or "", "html.parser").get_text(" ", strip=True)
    cleaned = re.sub(r"\([^)]*\)", "", cleaned)
    cleaned = re.sub(r"\b20\d{2}년?\b", "", cleaned)
    cleaned = re.sub(r"직원수|근무환경|복리후생|기업정보|기업 정보|등|잡코리아|사람인", "", cleaned)
    return re.sub(r"[\s|,·\-]+", "", cleaned.lower())


def _item_score(item: Dict[str, str]) -> int:
    score = len(item.get("summary", ""))
    host = _publisher_from_url(item.get("link", "")).lower()
    if "saramin.co.kr" in host:
        score += 30
    if item.get("source_type") == "company_info":
        score += 20
    if item.get("source_type") == "interview_review":
        score += 20
    return score
