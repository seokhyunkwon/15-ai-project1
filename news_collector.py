import html
import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List
from urllib.parse import urlparse

import requests

from config import CATEGORY_RULES, Config

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_FILE = DATA_DIR / "news.json"

TARGET_COMPANIES = list(Config.FIXED_COMPANIES.keys())

BLOCKED_DOMAINS = {
    "namu.wiki",
    "namu.moe",
    "dcinside.com",
    "fmkorea.com",
    "theqoo.net",
    "instiz.net",
    "clien.net",
    "ruliweb.com",
    "ppomppu.co.kr",
    "mlbpark.donga.com",
    "bobaedream.co.kr",
    "todayhumor.co.kr",
    "reddit.com",
    "quora.com",
    "youtube.com",
    "blog.naver.com",
    "cafe.naver.com",
}

NEWS_DOMAIN_HINTS = (
    "news.",
    "yna.co.kr",
    "yonhapnewstv.co.kr",
    "mk.co.kr",
    "hankyung.com",
    "etnews.com",
    "fnnews.com",
    "sedaily.com",
    "edaily.co.kr",
    "chosun.com",
    "joongang.co.kr",
    "donga.com",
    "khan.co.kr",
    "hani.co.kr",
    "bizwatch.co.kr",
    "bloter.net",
    "zdnet.co.kr",
    "newsis.com",
    "kakao.com",
    "daum.net",
)


def _clean_text(value: str) -> str:
    value = html.unescape(value or "")
    value = re.sub(r"<[^>]+>", "", value)
    return re.sub(r"\s+", " ", value).strip()


def _domain(url: str) -> str:
    host = urlparse(url or "").netloc.lower()
    return host[4:] if host.startswith("www.") else host


def _is_blocked(url: str) -> bool:
    host = _domain(url)
    return any(host == domain or host.endswith("." + domain) for domain in BLOCKED_DOMAINS)


def _looks_like_news(url: str) -> bool:
    host = _domain(url)
    return any(hint in host for hint in NEWS_DOMAIN_HINTS)


def _category_for(text: str) -> str:
    lowered = text.lower()
    for category, terms in CATEGORY_RULES.items():
        if any(term.lower() in lowered for term in terms):
            return category
    return "湲고?"


def _score_item(item: Dict, query_terms: Iterable[str]) -> int:
    text = f"{item.get('title', '')} {item.get('summary', '')}".lower()
    score = 0
    for term in query_terms:
        term = term.lower().strip()
        if term and term in text:
            score += 3
    if item.get("source") == "naver":
        score += 1
    if _looks_like_news(item.get("link", "")):
        score += 1
    return score


def load_payload() -> Dict:
    if not OUTPUT_FILE.exists():
        return {"updated_at": "", "keywords": [], "items": []}
    try:
        with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"updated_at": "", "keywords": [], "items": []}


def save_items(items: List[Dict], keywords: List[str]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "keywords": keywords,
        "items": items,
    }
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def _naver_news(query: str, display: int = 20) -> List[Dict]:
    if not Config.NAVER_CLIENT_ID or not Config.NAVER_CLIENT_SECRET:
        return []

    res = requests.get(
        "https://openapi.naver.com/v1/search/news.json",
        headers={
            "X-Naver-Client-Id": Config.NAVER_CLIENT_ID,
            "X-Naver-Client-Secret": Config.NAVER_CLIENT_SECRET,
        },
        params={"query": query, "display": display, "sort": "date"},
        timeout=8,
    )
    res.raise_for_status()

    items = []
    for raw in res.json().get("items", []):
        link = raw.get("originallink") or raw.get("link") or ""
        if _is_blocked(link):
            continue
        title = _clean_text(raw.get("title", ""))
        summary = _clean_text(raw.get("description", ""))
        if not title:
            continue
        items.append(
            {
                "title": title,
                "summary": summary,
                "link": link,
                "source": "naver",
                "published": raw.get("pubDate", "")[:16],
                "keyword": query,
                "category": _category_for(f"{title} {summary}"),
            }
        )
    return items


def _kakao_news(query: str, size: int = 20) -> List[Dict]:
    if not Config.KAKAO_REST_API_KEY:
        return []

    res = requests.get(
        "https://dapi.kakao.com/v2/search/web",
        headers={"Authorization": f"KakaoAK {Config.KAKAO_REST_API_KEY}"},
        params={"query": f"{query} " + "\ub274\uc2a4", "size": size, "sort": "recency"},
        timeout=8,
    )
    res.raise_for_status()

    items = []
    for raw in res.json().get("documents", []):
        link = raw.get("url", "")
        if _is_blocked(link) or not _looks_like_news(link):
            continue
        title = _clean_text(raw.get("title", ""))
        summary = _clean_text(raw.get("contents", ""))
        if not title:
            continue
        items.append(
            {
                "title": title,
                "summary": summary,
                "link": link,
                "source": "kakao",
                "published": (raw.get("datetime", "") or "")[:10],
                "keyword": query,
                "category": _category_for(f"{title} {summary}"),
            }
        )
    return items


def _build_queries(keywords: List[str], include_companies: bool) -> List[str]:
    cleaned = [k.strip() for k in keywords if k and k.strip()]
    if not include_companies:
        return cleaned

    queries = list(cleaned)
    for company in TARGET_COMPANIES:
        queries.append(company)
        for keyword in cleaned[:3]:
            if company.lower() not in keyword.lower():
                queries.append(f"{company} {keyword}")
    return queries


def collect_news(keywords: List[str], include_companies: bool = True, region_only: bool = False) -> List[Dict]:
    del region_only
    queries = _build_queries(keywords, include_companies)
    seen_links = set()
    collected: List[Dict] = []

    for query in queries:
        providers = (_naver_news, _kakao_news)
        for provider in providers:
            try:
                for item in provider(query):
                    key = item.get("link") or item.get("title")
                    if not key or key in seen_links:
                        continue
                    seen_links.add(key)
                    collected.append(item)
            except requests.RequestException:
                continue

    query_terms = keywords + TARGET_COMPANIES
    collected.sort(key=lambda item: _score_item(item, query_terms), reverse=True)
    return collected[:60]


def _empty_analysis(company_name: str) -> Dict:
    return {
        "summary": f"{company_name} 愿??理쒖떊 ?댁뒪媛 寃?됰릺吏 ?딆븘 AI 遺꾩꽍???앹꽦?섏? ?딆븯?듬땲??",
        "industry_trend": "寃?됰맂 ?ㅼ젣 湲곗궗 ?곗씠?곌? ?덉쓣 ?뚮쭔 ?듭떖 遺꾩꽍???쒓났?⑸땲??",
        "interview_questions": ["愿???댁뒪媛 寃?됰맂 ???ㅼ떆 遺꾩꽍???ㅽ뻾??二쇱꽭??"],
    }


def _analysis_prompt(company_name: str, news_titles: List[str]) -> str:
    context_news = "\n".join(f"- {title}" for title in news_titles[:12])
    return f"""
?뱀떊? ?먮룞李?遺??紐⑤퉴由ы떚 ?곗뾽 痍⑥뾽 而⑥꽕?댄듃?낅땲??
?꾨옒 ?ㅼ젣 ?댁뒪 ?쒕ぉ留?洹쇨굅濡?{company_name} 吏?먯옄瑜??꾪븳 湲곗뾽 遺꾩꽍???묒꽦?섏꽭??
?녿뒗 ?ъ떎, 湲곗궗, ?섏튂, ?ш굔? 留뚮뱾吏 留덉꽭??

[?댁뒪 ?쒕ぉ]
{context_news}

諛섎뱶??JSON留?諛섑솚?섏꽭??
{{
  "summary": "?댁뒪 湲곕컲 ?듭떖 ?붿빟 2~3臾몄옣",
  "industry_trend": "?곗뾽/湲곗뾽 愿?먯쓽 ?댁꽍 2~3臾몄옣",
  "interview_questions": ["?덉긽 硫댁젒 吏덈Ц 1", "?덉긽 硫댁젒 吏덈Ц 2", "?덉긽 硫댁젒 吏덈Ц 3"]
}}
""".strip()


def _parse_analysis(text: str) -> Dict:
    text = (text or "").strip()
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.MULTILINE).strip()
    data = json.loads(text)
    questions = data.get("interview_questions") or []
    if not isinstance(questions, list):
        questions = [str(questions)]
    return {
        "summary": str(data.get("summary", "")).strip(),
        "industry_trend": str(data.get("industry_trend", "")).strip(),
        "interview_questions": [str(q).strip() for q in questions if str(q).strip()][:5],
    }


def _openai_analysis(prompt: str) -> str:
    print("MODEL =", Config.OPENAI_MODEL)
    print("OpenAI \ud568\uc218 \uc9c4\uc785")
    print("API KEY \uc874\uc7ac \uc5ec\ubd80 =", bool(Config.OPENAI_API_KEY))

    if not Config.OPENAI_API_KEY or Config.OPENAI_API_KEY == "your_openai_api_key_here":
        print("OpenAI API Key \uc5c6\uc74c")
        return ""

    res = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {Config.OPENAI_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": Config.OPENAI_MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a Korean career consultant. Return only valid JSON.",
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.25,
            "response_format": {"type": "json_object"},
        },
        timeout=(10, 60),
    )

    print("STATUS =", res.status_code)
    if res.status_code >= 400:
        print(res.text[:1000])

    res.raise_for_status()
    choices = res.json().get("choices", [])
    if not choices:
        return ""
    return choices[0].get("message", {}).get("content", "")


def generate_llm_analysis(company_name: str, news_titles: List[str]) -> Dict:

    print("generate_llm_analysis \uc2e4\ud589")
    print("company =", company_name)
    print("news count =", len(news_titles))

    if not news_titles:
        return _empty_analysis(company_name)

    # \ub274\uc2a4 \uac1c\uc218 \uc81c\ud55c
    news_titles = news_titles[:10]

    prompt = _analysis_prompt(company_name, news_titles)

    try:
        print("\n===== OpenAI \ubd84\uc11d \uc2dc\uc791 =====")

        text = _openai_analysis(prompt)

        print("OpenAI \uc751\ub2f5:")
        print(text[:500] if text else "\uc751\ub2f5 \uc5c6\uc74c")

        if text:
            parsed = _parse_analysis(text)

            print("\ud30c\uc2f1 \uacb0\uacfc:")
            print(parsed)

            if parsed["summary"] and parsed["interview_questions"]:
                print("OpenAI \ubd84\uc11d \uc131\uacf5")
                return parsed

    except Exception as e:
        print("\nOpenAI \uc624\ub958 \ubc1c\uc0dd:")
        print(type(e).__name__)
        print(str(e))

    return {
        "summary": f"{company_name} \uad00\ub828 \ub274\uc2a4\ub294 \uc218\uc9d1\ub418\uc5c8\uc73c\ub098 AI \ubd84\uc11d \uc11c\ubc84 \uc5f0\uacb0\uc5d0 \uc2e4\ud328\ud588\uc2b5\ub2c8\ub2e4.",
        "industry_trend": "\ub274\uc2a4 \ubaa9\ub85d\uc740 \uc815\uc0c1 \uc218\uc9d1\ub418\uc5c8\uc2b5\ub2c8\ub2e4. OpenAI API Key \ub610\ub294 \uc0ac\uc6a9\ub7c9(quota)\uc744 \ud655\uc778\ud558\uc138\uc694.",
        "interview_questions": [
            "\ucd5c\uadfc \uae30\uc0ac\uc5d0\uc11c \uac00\uc7a5 \uc911\uc694\ud55c \uc774\uc288\ub294 \ubb34\uc5c7\uc785\ub2c8\uae4c?",
            "\ud574\ub2f9 \uc774\uc288\uac00 \uc790\ub3d9\ucc28\ubd80\ud488 \uc0b0\uc5c5\uc5d0 \ubbf8\uce58\ub294 \uc601\ud5a5\uc740 \ubb34\uc5c7\uc785\ub2c8\uae4c?",
            "\uc785\uc0ac \ud6c4 \uc774 \uc774\uc288\uc5d0 \uc5b4\ub5bb\uac8c \ub300\uc751\ud560 \uc218 \uc788\uc2b5\ub2c8\uae4c?",
        ],
    }