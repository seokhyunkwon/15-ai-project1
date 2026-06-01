from __future__ import annotations

import re
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Any, Dict, List
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from config import Config


JOB_SITE_DOMAINS = (
    "saramin.co.kr",
    "jobkorea.co.kr",
    "work24.go.kr",
    "work.go.kr",
    "incruit.com",
    "career.co.kr",
    "wanted.co.kr",
    "jumpit.saramin.co.kr",
    "catch.co.kr",
    "superookie.com",
    "jasoseol.com",
    "linkareer.com",
    "jobplanet.co.kr",
    "rallit.com",
    "programmers.co.kr",
    "rocketpunch.com",
)

RECRUIT_TERMS = (
    "채용",
    "채용공고",
    "모집",
    "입사지원",
    "신입",
    "경력",
    "인턴",
    "생산직",
    "품질",
    "recruit",
    "career",
    "job",
    "jobs",
    "apply",
)

BLOCKED_JOB_TERMS = (
    "블라인드",
    "blind",
    "디시",
    "dcinside",
    "면접후기",
    "연봉후기",
    "기업리뷰",
    "뉴스",
    "주가",
    "공시",
)

BLOCKED_JOB_EXTENSIONS = (
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".webp",
    ".svg",
    ".pdf",
    ".xls",
    ".xlsx",
    ".doc",
    ".docx",
    ".ppt",
    ".pptx",
    ".zip",
)


def collect_public_jobs(
    company: str,
    *,
    limit: int = 6,
    max_queries: int = 3,
    provider_strategy: str = "all",
) -> Dict[str, Any]:
    company = company.strip()
    if not company:
        return {"items": [], "error": "회사명이 비어 있습니다.", "providers": []}

    items: List[Dict[str, str]] = []
    errors: List[str] = []
    providers = []

    use_kakao = bool(Config.KAKAO_REST_API_KEY)
    use_naver = bool(Config.NAVER_CLIENT_ID and Config.NAVER_CLIENT_SECRET)
    if provider_strategy == "first":
        if use_kakao:
            use_naver = False
        elif use_naver:
            use_kakao = False

    queries = _job_queries(company)[:max(1, max_queries)]

    if use_kakao:
        providers.append("카카오")
        try:
            items.extend(_collect_kakao_jobs(queries))
        except Exception as exc:  # noqa: BLE001
            errors.append(f"카카오 검색 실패: {exc}")

    if use_naver:
        providers.append("네이버")
        try:
            items.extend(_collect_naver_jobs(queries))
        except Exception as exc:  # noqa: BLE001
            errors.append(f"네이버 검색 실패: {exc}")

    if not providers:
        errors.append("네이버 또는 카카오 검색 API 키가 없어 채용공고 공개 검색을 실행할 수 없습니다.")

    filtered = _dedupe_jobs(
        item for item in items if _is_relevant_job_item(company, item)
    )
    return {
        "items": [_with_reliability(item) for item in filtered[:limit]],
        "error": "; ".join(errors),
        "providers": providers,
    }


def _collect_kakao_jobs(queries: List[str]) -> List[Dict[str, str]]:
    headers = {"Authorization": f"KakaoAK {Config.KAKAO_REST_API_KEY}"}
    endpoint = "https://dapi.kakao.com/v2/search/web.json"
    out: List[Dict[str, str]] = []
    for query in queries:
        params = {"query": query, "sort": "recency", "size": 10}
        response = requests.get(endpoint, headers=headers, params=params, timeout=8)
        response.raise_for_status()
        payload = response.json()
        for raw in payload.get("documents", []):
            link = str(raw.get("url") or "").strip()
            out.append(
                {
                    "title": _strip_html(str(raw.get("title") or "")),
                    "summary": _strip_html(str(raw.get("contents") or "")),
                    "url": link,
                    "outlet": _host(link),
                    "provider": "카카오",
                    "published": _format_datetime(str(raw.get("datetime") or "")),
                }
            )
    return out


def _collect_naver_jobs(queries: List[str]) -> List[Dict[str, str]]:
    headers = {
        "X-Naver-Client-Id": Config.NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": Config.NAVER_CLIENT_SECRET,
    }
    endpoint = "https://openapi.naver.com/v1/search/webkr.json"
    out: List[Dict[str, str]] = []
    for query in queries:
        params = {"query": query, "display": 10, "sort": "date"}
        response = requests.get(endpoint, headers=headers, params=params, timeout=8)
        response.raise_for_status()
        payload = response.json()
        for raw in payload.get("items", []):
            link = str(raw.get("link") or "").strip()
            out.append(
                {
                    "title": _strip_html(str(raw.get("title") or "")),
                    "summary": _strip_html(str(raw.get("description") or "")),
                    "url": link,
                    "outlet": _host(link),
                    "provider": "네이버",
                    "published": "",
                }
            )
    return out


def _job_queries(company: str) -> List[str]:
    return [
        f"{company} 채용",
        f"{company} 채용공고",
        f"{company} 신입 경력 모집",
    ]


def _is_relevant_job_item(company: str, item: Dict[str, str]) -> bool:
    title = item.get("title", "")
    summary = item.get("summary", "")
    url = item.get("url", "")
    if not url or _is_file_url(url):
        return False

    blob = f"{title} {summary} {url}".lower()
    compact_blob = re.sub(r"\s+", "", blob)
    compact_company = re.sub(r"\s+", "", company.lower())

    if compact_company not in compact_blob:
        return False
    if any(term.lower() in blob for term in BLOCKED_JOB_TERMS):
        return False
    if not any(term.lower() in blob for term in RECRUIT_TERMS):
        return False

    host = _host(url)
    if _is_known_job_site(host):
        return True

    path = urlparse(url).path.lower()
    return any(token in path or token in host for token in ("recruit", "career", "job", "apply", "hr"))


def _is_known_job_site(host: str) -> bool:
    return any(host == domain or host.endswith(f".{domain}") for domain in JOB_SITE_DOMAINS)


def _with_reliability(item: Dict[str, str]) -> Dict[str, str]:
    host = _host(item.get("url", ""))
    path = urlparse(item.get("url", "")).path.lower()
    enriched = dict(item)
    if host in {"work24.go.kr", "work.go.kr"} or host.endswith(".work24.go.kr") or host.endswith(".work.go.kr"):
        enriched["confidence_label"] = "공공 채용"
        enriched["confidence_level"] = "public"
    elif _is_known_job_site(host):
        enriched["confidence_label"] = "채용플랫폼"
        enriched["confidence_level"] = "platform"
    elif any(token in path or token in host for token in ("recruit", "career", "apply", "hr")):
        enriched["confidence_label"] = "공식 후보"
        enriched["confidence_level"] = "official"
    else:
        enriched["confidence_label"] = "검색 후보"
        enriched["confidence_level"] = "candidate"
    return enriched


def _is_file_url(url: str) -> bool:
    parsed = urlparse(url)
    path = parsed.path.lower()
    query = parsed.query.lower()
    return path.endswith(BLOCKED_JOB_EXTENSIONS) or any(ext in query for ext in BLOCKED_JOB_EXTENSIONS)


def _dedupe_jobs(items: Any) -> List[Dict[str, str]]:
    seen = set()
    out = []
    for item in items:
        key = item.get("url") or item.get("title")
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def _strip_html(text: str) -> str:
    return BeautifulSoup(text or "", "html.parser").get_text(" ", strip=True)


def _host(url: str) -> str:
    host = urlparse(url).netloc.lower()
    return host.removeprefix("www.")


def _format_datetime(value: str) -> str:
    if not value:
        return ""
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError, IndexError):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return value
    return parsed.strftime("%Y-%m-%d")
