from __future__ import annotations

import json
import re
import time
from datetime import datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from config import Config


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
PUBLIC_JOBS_CACHE_FILE = DATA_DIR / "public_jobs_cache.json"
PUBLIC_JOBS_CACHE_TTL_SECONDS = 60 * 60
PUBLIC_JOBS_CACHE_VERSION = 3
PUBLIC_JOBS_CACHE_MAX_ENTRIES = 200

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

EDUCATION_JOB_STRONG_TERMS = (
    "학원",
    "강사",
    "교사",
    "과외",
    "보습",
    "입시",
    "어학원",
    "유치원",
    "어린이집",
    "학습지",
    "teacher",
    "tutor",
    "academy",
    "instructor",
)

EDUCATION_JOB_CONTEXT_TERMS = (
    "초등",
    "초등생",
    "중등",
    "고등",
    "수학",
    "영어",
    "국어",
    "과학",
    "논술",
)

EDUCATION_COMPANY_HINTS = (
    "교육",
    "학원",
    "어학원",
    "스터디",
    "에듀",
    "입시",
    "학습",
    "edu",
)

PLACE_NAME_SUFFIXES = (
    "빌딩",
    "타워",
    "상가",
    "아파트",
    "오피스텔",
    "프라자",
    "건물",
)

DIRECT_COMPANY_ROLE_TERMS = (
    "채용",
    "공채",
    "모집",
    "신입",
    "경력",
    "생산",
    "품질",
    "개발",
    "기술",
    "연구",
    "설계",
    "구매",
    "자재",
    "공정",
    "관리",
    "영업",
    "사무",
    "정규직",
    "계약직",
    "인턴",
)

LINK_CHECK_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

DEAD_LINK_STATUSES = {400, 404, 410, 451}

EXPIRED_JOB_MARKERS = (
    "페이지를 찾을 수 없습니다",
    "존재하지 않는 페이지",
    "존재하지 않는 공고",
    "삭제된 공고",
    "삭제된 채용",
    "마감된 채용",
    "채용이 마감",
    "공고가 마감",
    "모집이 마감",
    "접근할 수 없는 페이지",
    "not found",
    "page not found",
    "expired",
)

SUMMARY_CUTOFF_TERMS = (
    "채용 정보에 잘못된 내용이 있을 경우 해주세요",
    "잘못된 내용이 있을 경우 해주세요",
    "잘못된 내용",
    "회사 내규",
    "근무지주소",
    "근무지 주소",
    "근무시간",
    "근무 요일",
    "월~금",
    "월-금",
    "주 5일",
    "초대졸",
    "고졸",
    "대졸",
    "학력",
    "급여",
    "연봉",
    "담당업무",
    "자격요건",
    "복리후생",
)

JOB_BOILERPLATE_TERMS = (
    "채용 정보에 잘못된 내용이 있을 경우 해주세요.",
    "채용 정보에 잘못된 내용이 있을 경우 해주세요",
    "잘못된 내용이 있을 경우 해주세요.",
    "잘못된 내용이 있을 경우 해주세요",
)

DEADLINE_PATTERNS = (
    re.compile(r"(?:~|마감\s*)\s*(\d{1,2})\s*[./월]\s*(\d{1,2})\s*일?"),
    re.compile(r"(\d{4})[.-](\d{1,2})[.-](\d{1,2})"),
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
    refresh: bool = False,
) -> Dict[str, Any]:
    company = company.strip()
    if not company:
        return {"items": [], "error": "회사명이 비어 있습니다.", "providers": []}

    cache_key = _job_cache_key(
        company,
        limit=limit,
        max_queries=max_queries,
        provider_strategy=provider_strategy,
    )
    if not refresh:
        cached = _load_public_jobs_cache(cache_key)
        if cached:
            return cached

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
    filtered = _filter_live_job_links(filtered, limit=limit)
    result = {
        "items": [_with_reliability(item) for item in filtered[:limit]],
        "error": "; ".join(errors),
        "providers": providers,
        "cached": False,
        "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    _save_public_jobs_cache(cache_key, result)
    return result


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
    if _is_non_target_job_item(company, title, summary, url):
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


def _is_non_target_job_item(company: str, title: str, summary: str, url: str) -> bool:
    text = f"{title} {summary}"
    if _has_strong_company_signal(company, title, url):
        return False
    if _company_used_as_place_name(company, text):
        return True
    if _looks_like_education_job(company, text):
        return True
    return False


def _has_strong_company_signal(company: str, title: str, url: str) -> bool:
    compact_company = _compact_for_match(company)
    compact_title = _compact_for_match(title)
    if not compact_company:
        return False

    legal_prefixes = ("주", "주식회사", "유", "유한회사")
    if any(f"{prefix}{compact_company}" in compact_title for prefix in legal_prefixes):
        return True

    compact_role_terms = [_compact_for_match(term) for term in DIRECT_COMPANY_ROLE_TERMS]
    if any(f"{compact_company}{term}" in compact_title for term in compact_role_terms):
        return True

    parsed = urlparse(url)
    host = _compact_for_match(parsed.netloc)
    path = parsed.path.lower()
    return compact_company in host and any(
        token in path for token in ("recruit", "career", "job", "apply", "hr")
    )


def _company_used_as_place_name(company: str, text: str) -> bool:
    compact_company = _compact_for_match(company)
    compact_text = _compact_for_match(text)
    if not compact_company:
        return False
    return any(
        f"{compact_company}{_compact_for_match(suffix)}" in compact_text
        for suffix in PLACE_NAME_SUFFIXES
    )


def _looks_like_education_job(company: str, text: str) -> bool:
    company_text = company.lower()
    if any(hint.lower() in company_text for hint in EDUCATION_COMPANY_HINTS):
        return False

    lower_text = text.lower()
    if any(term.lower() in lower_text for term in EDUCATION_JOB_STRONG_TERMS):
        return True

    context_hits = sum(
        1 for term in EDUCATION_JOB_CONTEXT_TERMS if term.lower() in lower_text
    )
    return context_hits >= 2


def _compact_for_match(value: str) -> str:
    return re.sub(r"[^0-9a-zA-Z가-힣]+", "", value or "").lower()


def _job_cache_key(
    company: str,
    *,
    limit: int,
    max_queries: int,
    provider_strategy: str,
) -> str:
    return "|".join(
        (
            str(PUBLIC_JOBS_CACHE_VERSION),
            _compact_for_match(company),
            str(limit),
            str(max_queries),
            provider_strategy,
        )
    )


def _load_public_jobs_cache(cache_key: str) -> Dict[str, Any] | None:
    payload = _read_public_jobs_cache()
    entry = payload.get("entries", {}).get(cache_key)
    if not isinstance(entry, dict):
        return None
    if entry.get("version") != PUBLIC_JOBS_CACHE_VERSION:
        return None
    cached_at = float(entry.get("cached_at") or 0)
    if time.time() - cached_at > PUBLIC_JOBS_CACHE_TTL_SECONDS:
        return None
    result = entry.get("result")
    if not isinstance(result, dict):
        return None
    cached_result = dict(result)
    cached_result["cached"] = True
    return cached_result


def _save_public_jobs_cache(cache_key: str, result: Dict[str, Any]) -> None:
    payload = _read_public_jobs_cache()
    entries = payload.setdefault("entries", {})
    entries[cache_key] = {
        "version": PUBLIC_JOBS_CACHE_VERSION,
        "cached_at": time.time(),
        "result": result,
    }
    if len(entries) > PUBLIC_JOBS_CACHE_MAX_ENTRIES:
        stale_keys = sorted(
            entries,
            key=lambda key: float(entries[key].get("cached_at") or 0),
        )
        for key in stale_keys[: len(entries) - PUBLIC_JOBS_CACHE_MAX_ENTRIES]:
            entries.pop(key, None)
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        with open(PUBLIC_JOBS_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
    except OSError:
        return


def _read_public_jobs_cache() -> Dict[str, Any]:
    if not PUBLIC_JOBS_CACHE_FILE.exists():
        return {"version": PUBLIC_JOBS_CACHE_VERSION, "entries": {}}
    try:
        with open(PUBLIC_JOBS_CACHE_FILE, "r", encoding="utf-8") as f:
            payload = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {"version": PUBLIC_JOBS_CACHE_VERSION, "entries": {}}
    if not isinstance(payload, dict):
        return {"version": PUBLIC_JOBS_CACHE_VERSION, "entries": {}}
    if payload.get("version") != PUBLIC_JOBS_CACHE_VERSION:
        return {"version": PUBLIC_JOBS_CACHE_VERSION, "entries": {}}
    if not isinstance(payload.get("entries"), dict):
        payload["entries"] = {}
    return payload


def _filter_live_job_links(items: List[Dict[str, str]], *, limit: int) -> List[Dict[str, str]]:
    live_items: List[Dict[str, str]] = []
    for item in items:
        if _is_live_job_url(item.get("url", "")):
            live_items.append(item)
        if len(live_items) >= limit:
            break
    return live_items


def _is_live_job_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return False

    try:
        response = requests.get(
            url,
            headers=LINK_CHECK_HEADERS,
            timeout=4,
            allow_redirects=True,
        )
    except requests.RequestException:
        return True

    if response.status_code in DEAD_LINK_STATUSES:
        return False
    if response.status_code in {401, 403, 429}:
        return True
    if response.status_code >= 500:
        return True

    final_path = urlparse(response.url).path.lower()
    if any(token in final_path for token in ("404", "not-found", "notfound", "error")):
        return False

    page_text = _strip_html(response.text[:30000]).lower()
    return not any(marker in page_text for marker in EXPIRED_JOB_MARKERS)


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
    return _with_display_fields(enriched)


def _with_display_fields(item: Dict[str, str]) -> Dict[str, str]:
    enriched = dict(item)
    title = _clean_job_title(enriched.get("title", ""))
    summary = _clean_job_summary(enriched.get("summary", ""))
    deadline = enriched.get("close_at") or _extract_deadline(
        f"{enriched.get('title', '')} {enriched.get('summary', '')}"
    )

    display_title = title or enriched.get("title", "")
    if deadline:
        enriched["close_at"] = deadline
        if deadline not in display_title:
            display_title = f"{display_title} {deadline}"
        enriched["display_summary"] = ""
    elif summary and summary != title:
        enriched["display_summary"] = summary
    else:
        enriched["display_summary"] = ""
    enriched["display_title"] = display_title
    return enriched


def _clean_job_title(value: str) -> str:
    text = _normalize_job_text(value)
    text = re.sub(r"^\[[^\]]+\]\s*", "", text)
    return _trim_noise_suffix(text)


def _clean_job_summary(value: str) -> str:
    text = _normalize_job_text(value)
    text = _trim_noise_suffix(text)
    if len(text) > 90:
        text = text[:90].rstrip() + "..."
    return text


def _trim_noise_suffix(value: str) -> str:
    text = value.strip()
    cut_positions = [
        text.find(term)
        for term in SUMMARY_CUTOFF_TERMS
        if term in text and text.find(term) >= 0
    ]
    if cut_positions:
        text = text[: min(cut_positions)].strip()
    text = re.sub(r"\s+([),.])", r"\1", text)
    text = re.sub(r"\(\s+", "(", text)
    text = re.sub(r"\s+\)", ")", text)
    return text.rstrip("·,-/ ")


def _extract_deadline(value: str) -> str:
    text = _normalize_job_text(value)
    if any(term in text for term in ("상시채용", "상시 채용", "채용시", "채용 시")):
        return "상시"
    for pattern in DEADLINE_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        if len(match.groups()) == 2:
            month, day = match.groups()
            return f"~{int(month)}/{int(day)}"
        if len(match.groups()) == 3:
            _, month, day = match.groups()
            return f"~{int(month)}/{int(day)}"
    return ""


def _normalize_job_text(value: str) -> str:
    text = _strip_html(value or "")
    for term in JOB_BOILERPLATE_TERMS:
        text = text.replace(term, " ")
    return re.sub(r"\s+", " ", text).strip()


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
