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


INTERVIEW_DOMAINS = (
    "jobplanet.co.kr",
    "catch.co.kr",
    "jobkorea.co.kr",
    "saramin.co.kr",
    "incruit.com",
    "jasoseol.com",
    "weport.co.kr",
)

INTERVIEW_KEYWORDS = (
    "면접",
    "면접후기",
    "면접질문",
    "질문",
    "interview",
)


def make_interview_tips(title, description):
    text = f"{title} {description}".lower()

    if any(keyword in text for keyword in ("제품", "제품군", "부품", "기술", "r&d", "연구", "개발")):
        return [
            "대표 제품과 기술이 실제 차량에서 어떤 역할을 하는지 정리하기",
            "지원 직무 경험을 제품 품질, 성능, 원가, 안전성과 연결하기",
        ]

    if any(keyword in text for keyword in ("품질", "불량", "개선", "공정", "생산")):
        return [
            "품질 문제를 발견하고 원인을 분석했던 경험을 STAR 구조로 정리하기",
            "공정 개선, 재발 방지, 협업 과정을 숫자나 결과 중심으로 말하기",
        ]

    if any(keyword in text for keyword in ("프로젝트", "과제", "경험", "포트폴리오")):
        return [
            "프로젝트에서 본인이 맡은 역할과 의사결정 근거를 구체화하기",
            "성과보다 문제 해결 과정, 실패 대응, 배운 점을 중심으로 답변하기",
        ]

    if any(keyword in text for keyword in ("인성", "협업", "갈등", "소통", "팀")):
        return [
            "협업 중 의견 차이를 조율한 사례를 상황, 행동, 결과로 나누기",
            "상대방 관점 이해와 책임감 있는 후속 행동을 함께 설명하기",
        ]

    if any(keyword in text for keyword in ("지원동기", "회사", "기업", "직무", "입사")):
        return [
            "기업의 최근 이슈와 본인의 직무 관심사를 한 문장으로 연결하기",
            "왜 이 회사여야 하는지 경쟁사와 다른 강점을 근거로 준비하기",
        ]

    return [
        "요약에 나온 질문을 직무 역량, 기업 이해, 경험 사례로 나누어 답변하기",
        "답변 끝에는 입사 후 기여 방향을 짧게 덧붙이기",
    ]


def has_interview_company_signal(company_name, title, description, link):
    text = f"{title} {description} {link}".lower().replace(" ", "")
    aliases = COMPANY_ALIASES.get(company_name, (company_name,))
    return any(alias.lower().replace(" ", "") in text for alias in aliases)


def is_interview_result(company_name, title, description, link):
    domain = normalize_domain(link)
    text = f"{title} {description} {link}".lower()
    title_and_link = f"{title} {link}".lower()

    return (
        is_domain_match(domain, INTERVIEW_DOMAINS)
        and has_interview_company_signal(company_name, title, description, link)
        and any(keyword in text for keyword in INTERVIEW_KEYWORDS)
        and any(keyword in title_and_link for keyword in INTERVIEW_KEYWORDS)
    )


def dedupe_interviews(items):
    seen = set()
    unique_items = []

    for item in items:
        key = item.get("title", "").lower().strip()
        link = item.get("link", "").replace("http://", "https://").split("?")[0]
        dedupe_key = (key, link)

        if dedupe_key in seen:
            continue

        seen.add(dedupe_key)
        unique_items.append(item)

    return unique_items


def filter_interview_results(company_name, items):
    return [
        item
        for item in items
        if is_interview_result(
            company_name,
            item.get("title", ""),
            item.get("description", ""),
            item.get("link", ""),
        )
    ]


def get_interviews_from_naver(company_name, display=8):
    url = "https://openapi.naver.com/v1/search/webkr.json"
    headers = {
        "X-Naver-Client-Id": NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
    }
    params = {
        "query": f"{company_name} 면접후기 면접질문",
        "display": 20,
        "sort": "date",
    }

    response = requests.get(url, headers=headers, params=params, timeout=5)
    response.raise_for_status()
    data = response.json()

    interviews = []
    for item in data.get("items", []):
        title = clean_text(item.get("title"))
        description = clean_text(item.get("description"))
        link = item.get("link", "")

        if title and link:
            interviews.append(
                {
                    "title": title,
                    "description": description,
                    "link": link,
                    "source": "네이버 검색",
                    "tips": make_interview_tips(title, description),
                }
            )

    return filter_interview_results(company_name, interviews)[:display]


def get_interviews_from_kakao(company_name, display=8):
    if not KAKAO_REST_API_KEY:
        return []

    url = "https://dapi.kakao.com/v2/search/web"
    headers = {"Authorization": f"KakaoAK {KAKAO_REST_API_KEY}"}
    params = {
        "query": f"{company_name} 면접후기 면접질문",
        "size": 20,
        "sort": "recency",
    }

    response = requests.get(url, headers=headers, params=params, timeout=5)
    response.raise_for_status()
    data = response.json()

    interviews = []
    for item in data.get("documents", []):
        title = clean_text(item.get("title"))
        description = clean_text(item.get("contents"))
        link = item.get("url", "")

        if title and link:
            interviews.append(
                {
                    "title": title,
                    "description": description,
                    "link": link,
                    "source": "카카오 검색",
                    "tips": make_interview_tips(title, description),
                }
            )

    return filter_interview_results(company_name, interviews)[:display]


def make_interview_fallback(company_name):
    return [
        {
            "title": f"{company_name} 면접후기 검색",
            "description": "검색 API 결과가 부족합니다. 잡플래닛, 캐치, 잡코리아에서 기업명과 면접후기를 함께 검색해 보세요.",
            "link": f"https://www.google.com/search?q={company_name}+면접후기+면접질문",
            "source": "검색 링크",
            "tips": [
                "기업명과 직무명을 함께 검색해 실제 질문 유형을 먼저 수집하기",
                "수집한 질문을 지원동기, 직무역량, 협업경험으로 분류하기",
            ],
        }
    ]


def get_company_interviews(company_name):
    if company_name not in company_data:
        company_name = next(iter(company_data))

    results = []
    sources = []

    try:
        naver_results = get_interviews_from_naver(company_name)
        if naver_results:
            results.extend(naver_results)
            sources.append("네이버")
    except requests.RequestException:
        pass

    try:
        kakao_results = get_interviews_from_kakao(company_name)
        if kakao_results:
            results.extend(kakao_results)
            sources.append("카카오")
    except requests.RequestException:
        pass

    results = dedupe_interviews(dedupe_jobs(results))
    api_source = " + ".join(sources)

    if not results:
        results = make_interview_fallback(company_name)
        api_source = "면접후기 검색 링크"
    elif not api_source:
        api_source = "검색 API"

    return results, api_source
