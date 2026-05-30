import re

import requests

from company_info import company_data
from jobs_api import (
    COMPANY_ALIASES,
    KAKAO_REST_API_KEY,
    NAVER_CLIENT_ID,
    NAVER_CLIENT_SECRET,
    clean_text,
    dedupe_jobs,
    is_domain_match,
    normalize_domain,
)


BLOCKED_SEARCH_DOMAINS = (
    "dcinside.com",
    "fmkorea.com",
    "ruliweb.com",
    "theqoo.net",
    "instiz.net",
    "blog.naver.com",
    "m.blog.naver.com",
    "cafe.naver.com",
    "kin.naver.com",
    "tistory.com",
)

CAREER_KEYWORDS = (
    "채용",
    "취업",
    "공고",
    "직무",
    "면접",
    "자소서",
    "인턴",
    "신입",
    "경력",
    "생산관리",
    "품질",
    "품질관리",
    "생산기술",
    "연구개발",
    "설계",
    "구매",
    "영업",
    "sw",
    "소프트웨어",
    "전장",
    "자율주행",
    "자동차",
    "부품",
    "현대자동차",
)

BAD_KEYWORDS = (
    "똥",
    "시발",
    "씨발",
    "병신",
    "개새",
    "섹스",
    "야동",
)

BLOCKED_QUERY_KEYWORDS = (
    "디시",
    "디시인사이드",
    "dcinside",
    "에펨코리아",
    "fmkorea",
    "루리웹",
    "ruliweb",
    "더쿠",
    "theqoo",
    "인스티즈",
    "instiz",
)

COMPANY_ALIAS_TERMS = tuple(
    alias
    for aliases in COMPANY_ALIASES.values()
    for alias in aliases
)

COMPANY_TERMS = tuple(company_data.keys()) + COMPANY_ALIAS_TERMS + tuple(
    value
    for info in company_data.values()
    for value in (info.get("industry", ""), info.get("location", ""))
)

ALIAS_TO_COMPANY = {
    alias.lower().replace(" ", ""): company
    for company, aliases in COMPANY_ALIASES.items()
    for alias in aliases
}


def normalize_query(query):
    return re.sub(r"\s+", " ", (query or "").strip())


def is_initial_only(query):
    compact = query.replace(" ", "")
    return bool(compact) and all("ㄱ" <= char <= "ㅎ" for char in compact)


def expand_company_aliases(query):
    normalized = normalize_query(query)
    compact_query = normalized.lower().replace(" ", "")
    terms = [normalized]

    for alias, company in ALIAS_TO_COMPANY.items():
        if alias and alias in compact_query:
            terms.append(company)
            terms.extend(COMPANY_ALIASES.get(company, ()))

    seen = set()
    unique_terms = []

    for term in terms:
        if term and term not in seen:
            seen.add(term)
            unique_terms.append(term)

    return " ".join(unique_terms)


def is_allowed_query(query):
    normalized = normalize_query(query)
    lowered = normalized.lower()

    if any(keyword in lowered for keyword in BAD_KEYWORDS + BLOCKED_QUERY_KEYWORDS):
        return False, "취업 준비와 관련된 기업명, 직무, 산업 키워드만 검색할 수 있습니다."

    if len(normalized) < 2:
        return False, "검색어를 두 글자 이상 입력해 주세요."

    if is_initial_only(normalized):
        return False, "초성만으로는 관련 취업 정보를 찾기 어렵습니다. 기업명이나 직무명을 입력해 주세요."

    return True, ""


def is_allowed_result(title, description, link):
    domain = normalize_domain(link)
    text = f"{title} {description} {link}".lower()

    if is_domain_match(domain, BLOCKED_SEARCH_DOMAINS):
        return False

    if any(keyword in text for keyword in BAD_KEYWORDS):
        return False

    return True


def filter_results(items):
    return [
        item
        for item in items
        if is_allowed_result(
            item.get("title", ""),
            item.get("description", ""),
            item.get("link", ""),
        )
    ]


def search_naver(query, display=10):
    expanded_query = expand_company_aliases(query)
    url = "https://openapi.naver.com/v1/search/webkr.json"
    headers = {
        "X-Naver-Client-Id": NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
    }
    params = {
        "query": expanded_query,
        "display": 20,
        "sort": "date",
    }

    response = requests.get(url, headers=headers, params=params, timeout=5)
    response.raise_for_status()
    data = response.json()

    results = []
    for item in data.get("items", []):
        title = clean_text(item.get("title"))
        description = clean_text(item.get("description"))
        link = item.get("link", "")

        if title and link:
            results.append(
                {
                    "title": title,
                    "description": description,
                    "link": link,
                    "source": "네이버 검색",
                }
            )

    return filter_results(results)[:display]


def search_kakao(query, display=10):
    if not KAKAO_REST_API_KEY:
        return []

    expanded_query = expand_company_aliases(query)
    url = "https://dapi.kakao.com/v2/search/web"
    headers = {"Authorization": f"KakaoAK {KAKAO_REST_API_KEY}"}
    params = {
        "query": expanded_query,
        "size": 20,
        "sort": "recency",
    }

    response = requests.get(url, headers=headers, params=params, timeout=5)
    response.raise_for_status()
    data = response.json()

    results = []
    for item in data.get("documents", []):
        title = clean_text(item.get("title"))
        description = clean_text(item.get("contents"))
        link = item.get("url", "")

        if title and link:
            results.append(
                {
                    "title": title,
                    "description": description,
                    "link": link,
                    "source": "카카오 검색",
                }
            )

    return filter_results(results)[:display]


def search_career_content(query):
    query = normalize_query(query)
    is_valid, message = is_allowed_query(query)

    if not is_valid:
        return [], "검색 제한", message

    results = []
    sources = []

    try:
        naver_results = search_naver(query)
        if naver_results:
            results.extend(naver_results)
            sources.append("네이버")
    except requests.RequestException:
        pass

    try:
        kakao_results = search_kakao(query)
        if kakao_results:
            results.extend(kakao_results)
            sources.append("카카오")
    except requests.RequestException:
        pass

    results = dedupe_jobs(results)
    source = " + ".join(sources) if sources else "검색 API"

    if not results:
        return [], source, "관련 기업, 직무, 산업 자료를 찾지 못했습니다. 검색어를 조금 더 구체적으로 입력해 주세요."

    return results, source, ""
