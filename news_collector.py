import argparse
import json
import re
from datetime import datetime
from email.utils import parsedate_to_datetime
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urljoin, urlparse

import pandas as pd
import requests
from bs4 import BeautifulSoup

from config import (
    CATEGORY_RULES,
    Config,
    DEFAULT_INDUSTRY_KEYWORDS,
    HYUNDAI_KIA_FIRST_TIER_VENDORS,
)


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_FILE = DATA_DIR / "news.json"
THUMB_CACHE_FILE = DATA_DIR / "news_thumbnails.json"

COMPANY_ALIASES = {
    "아진": "아진산업",
    "THN": "티에이치엔",
    "thn": "티에이치엔",
}
AMBIGUOUS_COMPANY_KEYWORDS = set(COMPANY_ALIASES)
RECOMMENDED_COMPANY_SET = {
    re.sub(r"\s+", "", company.lower()) for company in HYUNDAI_KIA_FIRST_TIER_VENDORS
}
MIN_RESULTS_BEFORE_SUPPLEMENTAL_SEARCH = 8
MAX_RESULTS_PER_PROVIDER_KEYWORD = 50
RELEVANT_CONTEXT_TERMS = [
    "자동차",
    "부품",
    "전장",
    "전기차",
    "배터리",
    "공급망",
    "제조",
    "공장",
    "생산",
    "품질",
    "산업",
    "기업",
    "실적",
    "매출",
    "영업이익",
    "투자",
    "수주",
    "채용",
    "현대차",
    "현대자동차",
    "기아",
    "모빌리티",
]
IRRELEVANT_CONTEXT_TERMS = [
    "로또",
    "복권",
    "당첨",
    "판매점",
    "도로명",
    "주소",
    "공인중개사",
    "아파트",
    "성분",
    "화장품",
    "술",
    "소주",
    "맛집",
    "쇼핑몰",
    "닥트",
    "설비사",
]
BLOCKED_FILE_EXTENSIONS = (
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".webp",
    ".svg",
    ".pdf",
    ".xls",
    ".xlsx",
    ".csv",
    ".doc",
    ".docx",
    ".ppt",
    ".pptx",
    ".zip",
)
BLOCKED_DOMAINS = [
    "dcinside.com",
    "teamblind.com",
    "blind.com",
    "instiz.net",
    "dogdrip.net",
    "fmkorea.com",
    "theqoo.net",
    "ruliweb.com",
    "clien.net",
    "ppomppu.co.kr",
    "82cook.com",
    "mlbpark.donga.com",
    "todayhumor.co.kr",
    "humoruniv.com",
    "bobaedream.co.kr",
    "ygosu.com",
    "etoland.co.kr",
    "inven.co.kr",
    "arca.live",
    "quasarzone.com",
    "gigglehd.com",
    "namu.wiki",
    "weseb.com",
    "life114.co.kr",
    "dokdokinfo.kr",
    "voiceofyouth.co.kr",
    "invione.com",
    "report.hangyeong.com",
]
BLOCKED_TEXT_HINTS = [
    "디시인사이드",
    "블라인드",
    "blind",
    "인스티즈",
    "개드립",
    "더쿠",
    "에펨코리아",
    "루리웹",
    "클리앙",
    "뽐뿌",
    "보배드림",
    "아카라이브",
]
TRUSTED_SOURCE_DOMAINS = (
    "news.naver.com",
    "v.daum.net",
    "yna.co.kr",
    "newsis.com",
    "mk.co.kr",
    "hankyung.com",
    "sedaily.com",
    "edaily.co.kr",
    "etnews.com",
    "zdnet.co.kr",
    "thelec.kr",
    "chosun.com",
    "joongang.co.kr",
    "donga.com",
    "khan.co.kr",
    "hani.co.kr",
    "ytn.co.kr",
    "sbs.co.kr",
    "mbc.co.kr",
    "kbs.co.kr",
    "mt.co.kr",
    "fnnews.com",
    "heraldcorp.com",
    "businesspost.co.kr",
    "bizwatch.co.kr",
    "bloter.net",
    "inews24.com",
    "digitaltoday.co.kr",
    "autodaily.co.kr",
    "autotimes.co.kr",
    "autoelectronics.co.kr",
)


def _strip_html(text: str) -> str:
    return BeautifulSoup(text or "", "html.parser").get_text(" ", strip=True)


def _parse_published(value: str) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
        return parsed.replace(tzinfo=None)
    except (TypeError, ValueError, IndexError):
        pass
    for fmt in ("%Y-%m-%d", "%Y.%m.%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(value[:10], fmt)
        except ValueError:
            continue
    if value.isdigit() and len(value) >= 8:
        try:
            return datetime.strptime(value[:14].ljust(14, "0"), "%Y%m%d%H%M%S")
        except ValueError:
            pass
    return None


def _publisher_from_url(url: str) -> str:
    host = urlparse(url).netloc or ""
    return host.removeprefix("www.") if host else ""


def _is_blocked_source(link: str, text: str = "") -> bool:
    host = _publisher_from_url(link).lower()
    parsed = urlparse(link)
    path = parsed.path.lower()
    query = parsed.query.lower()
    if path.endswith(BLOCKED_FILE_EXTENSIONS) or any(ext in query for ext in BLOCKED_FILE_EXTENSIONS):
        return True
    if any(host == domain or host.endswith(f".{domain}") for domain in BLOCKED_DOMAINS):
        return True

    blob = text.lower()
    compact_blob = re.sub(r"\s+", "", blob)
    if compact_blob in {"img", "image", "pdf", "xlsx", "xls"}:
        return True
    if any(compact_blob.endswith(ext) for ext in BLOCKED_FILE_EXTENSIONS):
        return True
    return any(hint.lower() in blob for hint in BLOCKED_TEXT_HINTS)


def _is_news_like_web_result(link: str) -> bool:
    parsed = urlparse(link)
    host = parsed.netloc.lower().removeprefix("www.")
    path = parsed.path.lower()
    if host == "v.daum.net":
        return True
    if "news" in host:
        return True
    if any(token in path for token in ("/news/", "/article", "articleview", "view.php")):
        return True
    return False


def _canonical_keyword(keyword: str) -> str:
    compact = re.sub(r"\s+", "", keyword.strip())
    return COMPANY_ALIASES.get(compact, keyword.strip())


def _search_queries_for_keyword(keyword: str) -> List[str]:
    canonical = _canonical_keyword(keyword)
    compact = re.sub(r"\s+", "", canonical.lower())
    if compact not in RECOMMENDED_COMPANY_SET:
        return [canonical]

    queries = [
        canonical,
        f"{canonical} 자동차부품",
        f"{canonical} 현대차",
        f"{canonical} 채용",
    ]
    return list(dict.fromkeys(queries))


def _accepted_count(items: List[Dict[str, str]], keyword: str) -> int:
    return sum(1 for item in items if item.get("keyword") == keyword)


def _title_contains_keyword(title: str, keyword: str) -> bool:
    title_norm = re.sub(r"\s+", "", title.lower())
    keyword_norm = re.sub(r"\s+", "", keyword.lower())
    canonical_norm = re.sub(r"\s+", "", _canonical_keyword(keyword).lower())
    return keyword_norm in title_norm or canonical_norm in title_norm


def _is_file_like_title(title: str) -> bool:
    compact = re.sub(r"\s+", "", title.lower())
    if compact in {"img", "image", "pdf", "xlsx", "xls"}:
        return True
    return any(compact.endswith(ext) for ext in BLOCKED_FILE_EXTENSIONS)


def _contains_keyword(text: str, keyword: str) -> bool:
    text_norm = re.sub(r"\s+", "", text.lower())
    keyword_norm = re.sub(r"\s+", "", keyword.lower())
    canonical_norm = re.sub(r"\s+", "", _canonical_keyword(keyword).lower())
    return keyword_norm in text_norm or canonical_norm in text_norm


def _relevance_terms(keyword: str, search_query: str = "") -> List[str]:
    raw_terms = [keyword, _canonical_keyword(keyword)]
    if search_query:
        raw_terms.append(search_query)

    terms = []
    seen = set()
    for term in raw_terms:
        cleaned = str(term or "").strip()
        normalized = re.sub(r"\s+", "", cleaned.lower())
        if cleaned and normalized and normalized not in seen:
            terms.append(cleaned)
            seen.add(normalized)
    return terms


def _contains_any_keyword(text: str, terms: List[str]) -> bool:
    return any(_contains_keyword(text, term) for term in terms if term)


def _host_from_value(value: str) -> str:
    raw = str(value or "").strip().lower()
    if not raw:
        return ""
    parsed = urlparse(raw if "://" in raw else f"https://{raw}")
    host = parsed.netloc or parsed.path.split("/")[0]
    return host.removeprefix("www.")


def _is_trusted_source(item: Dict[str, str]) -> bool:
    candidates = [
        item.get("outlet", ""),
        item.get("link", ""),
        item.get("publisher", ""),
    ]
    for value in candidates:
        host = _host_from_value(value)
        if any(host == domain or host.endswith(f".{domain}") for domain in TRUSTED_SOURCE_DOMAINS):
            return True
    return False


def _score_relevance(item: Dict[str, str], search_query: str = "") -> tuple[int, List[str]]:
    terms = _relevance_terms(str(item.get("keyword", "")), search_query)
    title = str(item.get("title", ""))
    summary = str(item.get("summary", ""))
    score = 0
    reasons = []

    if _contains_any_keyword(title, terms):
        score += 3
        reasons.append("제목 일치 +3")
    if _contains_any_keyword(summary, terms):
        score += 2
        reasons.append("요약 일치 +2")
    if _is_trusted_source(item):
        score += 1
        reasons.append("신뢰 출처 +1")
    return score, reasons


def _has_relevant_context(text: str) -> bool:
    blob = re.sub(r"\s+", "", text.lower())
    return any(term.lower() in blob for term in RELEVANT_CONTEXT_TERMS)


def _is_title_or_context_match(title: str, summary: str, keyword: str) -> bool:
    if _title_contains_keyword(title, keyword):
        return True
    text = f"{title} {summary}"
    return _contains_keyword(text, keyword) and _has_relevant_context(text)


def _is_relevant_item(keyword: str, text: str) -> bool:
    compact_keyword = re.sub(r"\s+", "", keyword.strip())
    blob = re.sub(r"\s+", "", text.lower())
    if compact_keyword in AMBIGUOUS_COMPANY_KEYWORDS:
        canonical = COMPANY_ALIASES[compact_keyword]
        has_canonical = canonical.lower() in blob
        has_context = _has_relevant_context(text)
        has_irrelevant = any(term.lower() in blob for term in IRRELEVANT_CONTEXT_TERMS)
        if "기업보고서" in blob and not has_canonical:
            return False
        return (has_canonical or has_context) and not has_irrelevant
    return not any(term.lower() in blob for term in IRRELEVANT_CONTEXT_TERMS)


def _outlet_from_link(link: str) -> str:
    host = _publisher_from_url(link)
    if not host:
        return ""
    if "naver.com" in host:
        return "news.naver.com"
    return host


@lru_cache(maxsize=256)
def _thumbnail_for_url(url: str) -> str:
    if not url:
        return ""
    cache = _load_thumbnail_cache()
    if url in cache:
        return cache[url] if _is_valid_thumbnail_url(cache[url]) else ""
    thumbnail = _fetch_og_image(url)
    cache[url] = thumbnail
    _save_thumbnail_cache(cache)
    return thumbnail


def _fetch_og_image(url: str) -> str:
    try:
        resp = requests.get(
            url,
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=3,
            allow_redirects=True,
        )
        resp.raise_for_status()
    except requests.RequestException:
        return ""
    content_type = resp.headers.get("Content-Type", "")
    if "html" not in content_type.lower():
        return ""
    soup = BeautifulSoup(resp.text[:200000], "html.parser")
    for selector in (
        {"property": "og:image"},
        {"name": "twitter:image"},
        {"property": "twitter:image"},
    ):
        tag = soup.find("meta", attrs=selector)
        if tag and tag.get("content"):
            thumbnail = urljoin(resp.url, str(tag.get("content")).strip())
            return thumbnail if _is_valid_thumbnail_url(thumbnail) else ""
    return ""


def _is_valid_thumbnail_url(value: object) -> bool:
    if not isinstance(value, str):
        return False
    url = value.strip()
    if not url:
        return False

    lowered = url.lower()
    if lowered in {"nan", "none", "null"}:
        return False
    if "null" in lowered or "undefined" in lowered:
        return False

    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return False

    compact_path = re.sub(r"[^a-z0-9]", "", parsed.path.lower())
    generic_markers = (
        "logo",
        "ogimage",
        "shareimg",
        "snslogo",
        "facebook",
        "meta",
        "headerlogo",
        "tagimg",
    )
    if any(marker in compact_path for marker in generic_markers):
        return False

    image_markers = (
        ".jpg",
        ".jpeg",
        ".png",
        ".webp",
        ".gif",
        "thumbnail",
        "thumb",
        "getimage",
        "restmb",
        "photo",
        "image",
    )
    blob = lowered.split("?", 1)[0]
    return any(marker in blob for marker in image_markers)


def _load_thumbnail_cache() -> Dict[str, str]:
    if not THUMB_CACHE_FILE.exists():
        return {}
    try:
        with open(THUMB_CACHE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:  # noqa: BLE001
        return {}
    return data if isinstance(data, dict) else {}


def _save_thumbnail_cache(cache: Dict[str, str]) -> None:
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        if len(cache) > 500:
            cache = dict(list(cache.items())[-400:])
        with open(THUMB_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except Exception:  # noqa: BLE001
        return


def classify_category(text: str, search_keyword: str = "") -> str:
    blob = f"{text} {search_keyword}".lower()
    for category, tokens in CATEGORY_RULES.items():
        if any(token.lower() in blob for token in tokens):
            return category
    for category in CATEGORY_RULES:
        if category.replace(" ", "") in search_keyword.replace(" ", ""):
            return category
    return "기타"


def _build_item(
    *,
    keyword: str,
    title: str,
    summary: str,
    link: str,
    source: str,
    publisher: str,
    published: str,
    category: str,
    outlet: str = "",
    thumbnail: str = "",
) -> Dict[str, str]:
    item = {
        "keyword": keyword,
        "category": category,
        "title": title.strip(),
        "summary": summary.strip(),
        "source": source,
        "publisher": publisher,
        "published": published,
        "link": link.strip(),
    }
    if outlet:
        item["outlet"] = outlet
    if thumbnail:
        item["thumbnail"] = thumbnail
    score, reasons = _score_relevance(item)
    item["relevance_score"] = score
    item["relevance_reasons"] = reasons
    return item


def collect_from_naver(keywords: List[str], display: int = 10) -> List[Dict[str, str]]:
    items: List[Dict[str, str]] = []
    if not Config.NAVER_CLIENT_ID or not Config.NAVER_CLIENT_SECRET:
        return items

    headers = {
        "X-Naver-Client-Id": Config.NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": Config.NAVER_CLIENT_SECRET,
    }
    endpoint = "https://openapi.naver.com/v1/search/news.json"

    for keyword in keywords:
        for query_index, query in enumerate(_search_queries_for_keyword(keyword)):
            if (
                query_index > 0
                and _accepted_count(items, keyword) >= MIN_RESULTS_BEFORE_SUPPLEMENTAL_SEARCH
            ):
                break
            params = {"query": query, "display": display, "sort": "date"}
            try:
                response = requests.get(endpoint, headers=headers, params=params, timeout=10)
                response.raise_for_status()
                data = response.json()
            except requests.RequestException as exc:
                print(f"[naver] '{query}' 수집 실패: {exc}")
                continue

            for raw in data.get("items", []):
                title = _strip_html(raw.get("title", ""))
                summary = _strip_html(raw.get("description", ""))
                text_blob = f"{title} {summary}"

                if _is_file_like_title(title):
                    continue
                if not _is_title_or_context_match(title, summary, keyword):
                    continue
                if not _is_relevant_item(keyword, text_blob):
                    continue

                link = raw.get("link", "")
                original_link = raw.get("originallink", "") or link
                outlet = _outlet_from_link(original_link) or _outlet_from_link(link)
                if _is_blocked_source(original_link or link, text_blob):
                    continue
                thumbnail = _thumbnail_for_url(original_link or link)

                items.append(
                    _build_item(
                        keyword=keyword,
                        title=title,
                        summary=summary,
                        link=link,
                        source="naver",
                        publisher="네이버",
                        outlet=outlet,
                        published=raw.get("pubDate", ""),
                        category=classify_category(text_blob, keyword),
                        thumbnail=thumbnail,
                    )
                )
                if _accepted_count(items, keyword) >= MAX_RESULTS_PER_PROVIDER_KEYWORD:
                    break
            if _accepted_count(items, keyword) >= MAX_RESULTS_PER_PROVIDER_KEYWORD:
                break
    return items


def collect_from_kakao(keywords: List[str], size: int = 10) -> List[Dict[str, str]]:
    """카카오 Daum 웹 검색 API (뉴스 전용 엔드포인트 없음 → 웹 검색 + 최신순)."""
    items: List[Dict[str, str]] = []
    if not Config.KAKAO_REST_API_KEY:
        return items

    headers = {"Authorization": f"KakaoAK {Config.KAKAO_REST_API_KEY}"}
    endpoint = "https://dapi.kakao.com/v2/search/web.json"

    for keyword in keywords:
        for query_index, query in enumerate(_search_queries_for_keyword(keyword)):
            if (
                query_index > 0
                and _accepted_count(items, keyword) >= MIN_RESULTS_BEFORE_SUPPLEMENTAL_SEARCH
            ):
                break
            params = {"query": query, "sort": "recency", "size": min(size, 50)}
            try:
                response = requests.get(
                    endpoint, headers=headers, params=params, timeout=10
                )
                response.raise_for_status()
                data = response.json()
            except requests.RequestException as exc:
                print(f"[kakao] '{query}' 수집 실패: {exc}")
                continue

            for raw in data.get("documents", []):
                title = _strip_html(raw.get("title", ""))
                summary = _strip_html(raw.get("contents", ""))
                link = raw.get("url", "")
                text_blob = f"{title} {summary}"

                if _is_file_like_title(title):
                    continue
                if not _is_title_or_context_match(title, summary, keyword):
                    continue
                if not _is_relevant_item(keyword, text_blob):
                    continue
                if _is_blocked_source(link, text_blob):
                    continue
                if not _is_news_like_web_result(link):
                    continue

                dt_raw = raw.get("datetime", "")
                published = ""
                if dt_raw:
                    parsed = _parse_published(str(dt_raw))
                    published = parsed.strftime("%a, %d %b %Y %H:%M:%S +0900") if parsed else str(dt_raw)

                outlet = _publisher_from_url(link)
                thumbnail = _thumbnail_for_url(link)

                items.append(
                    _build_item(
                        keyword=keyword,
                        title=title,
                        summary=summary,
                        link=link,
                        source="kakao",
                        publisher="카카오",
                        outlet=outlet,
                        published=published,
                        category=classify_category(text_blob, keyword),
                        thumbnail=thumbnail,
                    )
                )
                if _accepted_count(items, keyword) >= MAX_RESULTS_PER_PROVIDER_KEYWORD:
                    break
            if _accepted_count(items, keyword) >= MAX_RESULTS_PER_PROVIDER_KEYWORD:
                break
    return items


def process_dataframe(
    items: List[Dict[str, str]],
    *,
    keyword_filter: Optional[str] = None,
    category_filter: Optional[str] = None,
    search_query: Optional[str] = None,
) -> pd.DataFrame:
    if not items:
        return pd.DataFrame(
            columns=[
                "keyword",
                "category",
                "title",
                "summary",
                "source",
                "publisher",
                "published",
                "published_dt",
                "link",
                "outlet",
                "thumbnail",
                "relevance_score",
                "relevance_reasons",
            ]
        )

    df = pd.DataFrame(items)
    if "link" in df.columns:
        mask = df.apply(
            lambda row: not _is_blocked_source(
                str(row.get("link", "")),
                f"{row.get('title', '')} {row.get('summary', '')} {row.get('outlet', '')}",
            ),
            axis=1,
        )
        df = df[mask]
    if "keyword" in df.columns:
        file_title_mask = df["title"].fillna("").astype(str).apply(lambda value: not _is_file_like_title(value))
        df = df[file_title_mask]
        relevance_mask = df.apply(
            lambda row: _is_relevant_item(
                str(row.get("keyword", "")),
                f"{row.get('title', '')} {row.get('summary', '')}",
            ),
            axis=1,
        )
        df = df[relevance_mask]
        title_mask = df.apply(
            lambda row: _is_title_or_context_match(
                str(row.get("title", "")),
                str(row.get("summary", "")),
                str(row.get("keyword", "")),
            ),
            axis=1,
        )
        df = df[title_mask]

    df["published_dt"] = df["published"].apply(
        lambda v: _parse_published(v) if isinstance(v, str) else None
    )

    if keyword_filter:
        df = df[df["keyword"].str.contains(keyword_filter, case=False, na=False)]

    if category_filter and category_filter != "전체":
        df = df[df["category"] == category_filter]

    if search_query:
        pattern = re.escape(search_query)
        mask = (
            df["title"].str.contains(pattern, case=False, na=False)
            | df["summary"].str.contains(pattern, case=False, na=False)
            | df["keyword"].str.contains(pattern, case=False, na=False)
        )
        df = df[mask]

    df = df.drop_duplicates(subset=["title", "link"], keep="first")
    if df.empty:
        df["relevance_score"] = pd.Series(dtype="int")
        df["relevance_reasons"] = pd.Series(dtype="object")
    else:
        relevance = df.apply(
            lambda row: _score_relevance(row.to_dict(), search_query or ""),
            axis=1,
        )
        df["relevance_score"] = relevance.apply(lambda value: value[0]).astype(int)
        df["relevance_reasons"] = relevance.apply(lambda value: value[1])
    df = df.sort_values(
        by=["relevance_score", "published_dt"],
        ascending=[False, False],
        na_position="last",
    )
    return df.reset_index(drop=True)


def dataframe_to_records(df: pd.DataFrame) -> List[Dict[str, str]]:
    if df.empty:
        return []
    out = df.copy()
    out["published_dt"] = out["published_dt"].apply(
        lambda dt: dt.isoformat(timespec="seconds") if pd.notna(dt) else ""
    )
    if "outlet" in out.columns:
        out["outlet"] = out["outlet"].fillna("").astype(str)
        out.loc[out["outlet"].str.lower() == "nan", "outlet"] = ""
    if "thumbnail" in out.columns:
        out["thumbnail"] = out["thumbnail"].apply(
            lambda value: value if _is_valid_thumbnail_url(value) else ""
        )
    if "relevance_score" in out.columns:
        out["relevance_score"] = out["relevance_score"].fillna(0).astype(int)
    if "relevance_reasons" in out.columns:
        out["relevance_reasons"] = out["relevance_reasons"].apply(
            lambda value: value if isinstance(value, list) else []
        )
    records = out.drop(columns=["published_dt"], errors="ignore").to_dict(orient="records")
    return [
        {k: v for k, v in row.items() if k != "outlet" or (v and str(v).lower() != "nan")}
        for row in records
    ]


def collect_news(
    keywords: List[str],
    *,
    display: int = 20,
) -> List[Dict[str, str]]:
    search_terms = [k.strip() for k in keywords if k.strip()]

    fetch_size = min(max(display * 4, display), 50)
    naver_items = collect_from_naver(search_terms, display=fetch_size)
    kakao_items = collect_from_kakao(search_terms, size=fetch_size)
    merged = naver_items + kakao_items

    df = process_dataframe(merged)
    return dataframe_to_records(df)


def save_items(items: List[Dict[str, str]], keywords_used: List[str]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "keywords": keywords_used,
        "categories": ["전체"] + list(CATEGORY_RULES.keys()) + ["기타"],
        "items": items,
    }
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def load_payload() -> Dict:
    if not OUTPUT_FILE.exists():
        return {
            "updated_at": "",
            "keywords": [],
            "categories": ["전체"] + list(CATEGORY_RULES.keys()) + ["기타"],
            "items": [],
        }
    with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def run_collection(keywords: Optional[List[str]] = None) -> List[Dict[str, str]]:
    kw = keywords or DEFAULT_INDUSTRY_KEYWORDS
    items = collect_news(kw)
    save_items(items, kw)
    return items


def filter_loaded_items(
    payload: Dict,
    *,
    keyword_filter: str = "",
    category_filter: str = "전체",
    search_query: str = "",
) -> List[Dict[str, str]]:
    items = payload.get("items", [])
    df = process_dataframe(
        items,
        keyword_filter=keyword_filter or None,
        category_filter=category_filter,
        search_query=search_query or None,
    )
    return dataframe_to_records(df)


def main() -> None:
    parser = argparse.ArgumentParser(description="산업 키워드 뉴스 수집")
    parser.add_argument(
        "--keywords",
        nargs="+",
        default=None,
        help='검색 키워드 (예: "에스엘" "전기차")',
    )
    args = parser.parse_args()

    keywords = args.keywords or DEFAULT_INDUSTRY_KEYWORDS
    items = run_collection(keywords)
    print(f"수집 완료: {len(items)}건 (키워드: {', '.join(keywords)})")
    if not Config.NAVER_CLIENT_ID and not Config.KAKAO_REST_API_KEY:
        print("경고: .env에 NAVER 또는 KAKAO REST API 키가 없습니다.")


if __name__ == "__main__":
    main()
