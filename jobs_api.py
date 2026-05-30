import html
import os
import re
from datetime import datetime
from urllib.parse import quote_plus
from urllib.parse import urlparse

import requests

from company_info import company_data


NAVER_CLIENT_ID = os.getenv("NAVER_CLIENT_ID", "zcJPKaKkhJpQ4NJpOXgI")
NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET", "VAit_CLQ_P")
KAKAO_REST_API_KEY = os.getenv("KAKAO_REST_API_KEY", "52965b9323dd56cff9cef891d5e2ea1a")

JOB_DOMAINS = (
    "saramin.co.kr",
    "jobkorea.co.kr",
    "incruit.com",
    "catch.co.kr",
    "wanted.co.kr",
    "jumpit.co.kr",
    "jasoseol.com",
    "linkareer.com",
    "hyundai.co.kr",
    "mobis.co.kr",
    "hlmando.com",
    "slworld.com",
    "thn.co.kr",
    "ph.co.kr",
    "hwashin.co.kr",
    "ajin.co.kr",
    "sambomotors.com",
)

BLOCKED_DOMAINS = (
    "blog.naver.com",
    "m.blog.naver.com",
    "cafe.naver.com",
    "kin.naver.com",
    "post.naver.com",
    "tistory.com",
    "brunch.co.kr",
    "dcinside.com",
    "fmkorea.com",
    "ruliweb.com",
)

JOB_KEYWORDS = ("채용", "공고", "모집", "입사지원", "recruit", "career", "job")
BLOCKED_KEYWORDS = ("질문", "q&a", "qa", "블로그", "카페", "후기", "면접후기", "지식인")

COMPANY_ALIASES = {
    "현대모비스": ("현대모비스", "mobis"),
    "HL만도": ("HL만도", "에이치엘만도", "hlmando"),
    "THN": ("THN", "티에이치엔"),
    "SL": ("SL", "에스엘", "slworld"),
    "평화산업": ("평화산업", "ph.co.kr"),
    "화신": ("화신", "hwashin"),
    "아진산업": ("아진산업", "ajin"),
    "삼보모터스": ("삼보모터스", "sambomotors"),
}


def clean_text(value):
    value = re.sub("<.*?>", "", value or "")
    return html.unescape(value).strip()


def normalize_domain(link):
    domain = urlparse(link).netloc.lower()
    return domain[4:] if domain.startswith("www.") else domain


def is_domain_match(domain, candidates):
    return any(domain == item or domain.endswith(f".{item}") for item in candidates)


def has_company_signal(company_name, title, description, link):
    text = f"{title} {link}".lower().replace(" ", "")
    aliases = COMPANY_ALIASES.get(company_name, (company_name,))
    return any(alias.lower().replace(" ", "") in text for alias in aliases)


def is_recruiting_result(company_name, title, description, link):
    domain = normalize_domain(link)
    text = f"{title} {description} {link}".lower()
    years = [int(year) for year in re.findall(r"20\d{2}", title)]
    current_year = datetime.now().year

    if is_domain_match(domain, BLOCKED_DOMAINS):
        return False

    if any(keyword in text for keyword in BLOCKED_KEYWORDS):
        return False

    if years and max(years) < current_year:
        return False

    return (
        is_domain_match(domain, JOB_DOMAINS)
        and has_company_signal(company_name, title, description, link)
        and any(keyword in text for keyword in JOB_KEYWORDS)
    )


def filter_recruiting_results(company_name, jobs):
    return [
        job
        for job in jobs
        if is_recruiting_result(
            company_name,
            job.get("title", ""),
            job.get("description", ""),
            job.get("link", ""),
        )
    ]


def make_job_fallback(company_name):
    encoded = quote_plus(f"{company_name} 채용")
    return [
        {
            "title": f"{company_name} 채용공고 검색",
            "description": "현재 검색 API 결과를 불러오지 못했습니다. 채용 포털에서 최신 공고를 바로 확인해 보세요.",
            "link": f"https://www.jobkorea.co.kr/Search/?stext={encoded}",
            "source": "잡코리아",
        },
        {
            "title": f"{company_name} 채용정보 확인",
            "description": "사람인 검색 결과에서 모집 직무, 마감일, 지원 조건을 비교할 수 있습니다.",
            "link": f"https://www.saramin.co.kr/zf_user/search?searchword={encoded}",
            "source": "사람인",
        },
    ]


def get_jobs_from_naver(company_name, display=8):
    url = "https://openapi.naver.com/v1/search/webkr.json"
    headers = {
        "X-Naver-Client-Id": NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
    }
    params = {
        "query": f'{company_name} 채용공고 site:saramin.co.kr OR site:jobkorea.co.kr',
        "display": 20,
        "sort": "date",
    }

    response = requests.get(url, headers=headers, params=params, timeout=5)
    response.raise_for_status()
    data = response.json()

    jobs = []
    for item in data.get("items", []):
        title = clean_text(item.get("title"))
        description = clean_text(item.get("description"))
        link = item.get("link", "")

        if not title or not link:
            continue

        jobs.append(
            {
                "title": title,
                "description": description,
                "link": link,
                "source": "네이버 검색",
            }
        )

    return filter_recruiting_results(company_name, jobs)[:display]


def get_jobs_from_kakao(company_name, display=8):
    if not KAKAO_REST_API_KEY:
        return []

    url = "https://dapi.kakao.com/v2/search/web"
    headers = {"Authorization": f"KakaoAK {KAKAO_REST_API_KEY}"}
    params = {
        "query": f"{company_name} 채용공고 사람인 잡코리아 공식채용",
        "size": 20,
        "sort": "recency",
    }

    response = requests.get(url, headers=headers, params=params, timeout=5)
    response.raise_for_status()
    data = response.json()

    jobs = []
    for item in data.get("documents", []):
        title = clean_text(item.get("title"))
        description = clean_text(item.get("contents"))
        link = item.get("url", "")

        if not title or not link:
            continue

        jobs.append(
            {
                "title": title,
                "description": description,
                "link": link,
                "source": "카카오 검색",
            }
        )

    return filter_recruiting_results(company_name, jobs)[:display]


def dedupe_jobs(jobs):
    seen_links = set()
    unique_jobs = []

    for job in jobs:
        link = job.get("link")
        if not link or link in seen_links:
            continue

        seen_links.add(link)
        unique_jobs.append(job)

    return unique_jobs


def get_company_jobs(company_name):
    if company_name not in company_data:
        company_name = next(iter(company_data))

    jobs = []
    sources = []

    try:
        naver_jobs = get_jobs_from_naver(company_name)
        if naver_jobs:
            jobs.extend(naver_jobs)
            sources.append("네이버")
    except requests.RequestException:
        pass

    try:
        kakao_jobs = get_jobs_from_kakao(company_name)
        if kakao_jobs:
            jobs.extend(kakao_jobs)
            sources.append("카카오")
    except requests.RequestException:
        pass

    jobs = dedupe_jobs(jobs)
    api_source = " + ".join(sources)

    if not jobs:
        jobs = make_job_fallback(company_name)
        api_source = "채용 포털 검색 링크"
    elif not api_source:
        api_source = "검색 API"

    return jobs, api_source
