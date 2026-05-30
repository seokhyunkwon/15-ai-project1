import re
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, flash, redirect, render_template, request, url_for

from config import (
    CATEGORY_RULES,
    DEFAULT_INDUSTRY_KEYWORDS,
    HYUNDAI_KIA_FIRST_TIER_VENDORS,
)

SOURCE_LABELS = {"naver": "네이버", "kakao": "카카오"}
KNOWN_COMPANIES = set(HYUNDAI_KIA_FIRST_TIER_VENDORS) | {
    "현대자동차",
    "기아",
    "아진",
}
INDUSTRY_HINTS = {
    "자동차",
    "자동차부품",
    "부품",
    "전장",
    "전장부품",
    "전기차",
    "배터리",
    "공급망",
    "품질관리",
    "생산기술",
    "생산관리",
    "제조업",
    "반도체",
    "센서",
    "물류",
    "조달",
}
BLOCKED_SEARCH_TERMS = {
    "똥",
    "똥글",
    "개똥",
    "오줌",
    "방귀",
    "시발",
    "씨발",
    "병신",
    "빙시",
    "빙신",
    "븅신",
    "병시",
    "지랄",
    "좆",
    "존나",
    "fuck",
    "shit",
}
from news_collector import (
    collect_news,
    filter_loaded_items,
    load_payload,
    save_items,
)
from company_research import collect_company_research
from llm import (
    build_company_research,
    build_interview_questions_fallback,
    build_news_brief,
    llm_status,
)
from work24_client import fetch_jobs, work24_status


def create_app() -> Flask:
    load_dotenv(Path(__file__).resolve().parent / ".env", override=True)
    app = Flask(__name__)
    app.secret_key = "dev-news-dashboard"

    @app.route("/", methods=["GET"])
    def index():
        payload = load_payload()
        company = request.args.get("company", "").strip()
        search_q = request.args.get("q", "").strip()
        category = request.args.get("category", "전체")
        keyword = request.args.get("keyword", "").strip()
        brief_requested = request.args.get("brief") == "1"
        page = _positive_int(request.args.get("page"), default=1)
        per_page = 50
        brief_topic = company or keyword or search_q
        search_warning = _search_validation_message(brief_topic) if brief_topic else ""
        brief_mode = _brief_mode(brief_topic)

        filtered_news_items = filter_loaded_items(
            payload,
            keyword_filter=company or keyword,
            category_filter=category,
            search_query=search_q,
        )
        if search_warning:
            filtered_news_items = []

        total_news_count = len(filtered_news_items)
        total_pages = max(1, (total_news_count + per_page - 1) // per_page)
        page = min(page, total_pages)
        start = (page - 1) * per_page
        end = start + per_page
        news_items = filtered_news_items[start:end]
        pagination = {
            "page": page,
            "per_page": per_page,
            "total_pages": total_pages,
            "total_count": total_news_count,
            "start": start + 1 if total_news_count else 0,
            "end": min(end, total_news_count),
            "has_prev": page > 1,
            "has_next": page < total_pages,
            "prev_page": page - 1,
            "next_page": page + 1,
        }

        news_brief = None
        interview = None
        company_research = None
        work24_jobs = None
        research_payload = {"queries": [], "items": [], "error": ""}
        if brief_requested and brief_topic and not search_warning:
            news_brief = build_news_brief(
                company=brief_topic,
                articles=news_items,
                company_profile={},
            )
            if brief_mode == "company":
                work24_jobs = fetch_jobs(keyword=_work24_company_query(brief_topic), display=5)
                try:
                    research_payload = collect_company_research(brief_topic)
                except Exception as exc:  # noqa: BLE001
                    research_payload = {
                        "queries": [],
                        "items": [],
                        "error": f"공개 검색 리서치 수집 실패: {exc}",
                    }
                company_research = build_company_research(
                    company=brief_topic,
                    articles=news_items,
                    research_docs=research_payload.get("items", []),
                    generated_queries=research_payload.get("queries", []),
                )
                if research_payload.get("error"):
                    company_research["search_error"] = research_payload.get("error")

                interview_llm = build_interview_questions_fallback(
                    company=brief_topic,
                    articles=news_items,
                    company_profile={},
                )
                interview = {
                    "provider": "llm",
                    "questions": interview_llm.get("likely_interview_questions") or [],
                    "llm_meta": interview_llm.get("llm") or {},
                    "error": interview_llm.get("error") if isinstance(interview_llm, dict) else None,
                }

        categories = payload.get(
            "categories", ["전체"] + list(CATEGORY_RULES.keys()) + ["기타"]
        )
        used_keywords = payload.get("keywords", DEFAULT_INDUSTRY_KEYWORDS)

        return render_template(
            "index.html",
            news_items=news_items,
            pagination=pagination,
            updated_at=payload.get("updated_at", ""),
            categories=categories,
            used_keywords=used_keywords,
            default_keywords=", ".join(DEFAULT_INDUSTRY_KEYWORDS),
            recommended_keywords=DEFAULT_INDUSTRY_KEYWORDS,
            recommended_companies=HYUNDAI_KIA_FIRST_TIER_VENDORS,
            search_q=search_q,
            selected_category=category,
            selected_keyword=keyword,
            company=company,
            api_status=_api_status(),
            source_labels=SOURCE_LABELS,
            llm_status=llm_status(),
            brief_requested=brief_requested,
            brief_topic=brief_topic,
            brief_mode=brief_mode,
            search_warning=search_warning,
            news_brief=news_brief,
            interview=interview,
            company_research=company_research,
            research_docs=research_payload.get("items", []),
            company_info_docs=_unique_docs_by_outlet([
                doc for doc in research_payload.get("items", [])
                if doc.get("source_type") == "company_info" and doc.get("summary")
            ]),
            interview_review_docs=_unique_docs_by_outlet([
                doc for doc in research_payload.get("items", [])
                if doc.get("source_type") == "interview_review" and doc.get("summary")
            ]),
            work24_jobs=work24_jobs,
            work24_status=work24_status(),
        )

    @app.route("/collect", methods=["GET", "POST"])
    def collect():
        source = request.form if request.method == "POST" else request.args
        raw = source.get("keywords", "").strip()
        if raw:
            keywords = [k.strip() for k in raw.replace("\n", ",").split(",") if k.strip()]
        else:
            keywords = DEFAULT_INDUSTRY_KEYWORDS

        invalid_keywords = [
            keyword for keyword in keywords if _search_validation_message(keyword)
        ]
        if invalid_keywords:
            flash(
                "취업 뉴스 분석에 적합하지 않은 검색어입니다. 회사명, 산업명, 직무명 중심으로 검색해 주세요.",
                "error",
            )
            return redirect(url_for("index"))

        try:
            items = collect_news(keywords)
            save_items(items, keywords)
            flash(f"뉴스 {len(items)}건을 수집했습니다.", "success")
        except Exception as exc:
            flash(f"수집 실패: {exc}", "error")

        redirect_params = {"keyword": keywords[0] if keywords else ""}
        return redirect(url_for("index", **redirect_params))

    return app


def _normalize_search_term(value: str) -> str:
    normalized = re.sub(r"[\s\W_]+", "", value.lower(), flags=re.UNICODE)
    return normalized.translate(str.maketrans({
        "0": "o",
        "1": "l",
        "3": "e",
        "4": "a",
        "5": "s",
        "7": "t",
        "ㅂ": "븅",
    }))


def _search_validation_message(value: str) -> str:
    normalized = _normalize_search_term(value)
    collapsed_korean = re.sub(r"[0-9a-z]+", "", normalized)
    if not normalized:
        return "검색어를 입력해 주세요."
    if any(
        blocked in normalized or blocked in collapsed_korean
        for blocked in BLOCKED_SEARCH_TERMS
    ):
        return "취업 뉴스 분석에 적합하지 않은 검색어입니다. 회사명, 산업명, 직무명 중심으로 검색해 주세요."
    if len(normalized) < 2:
        return "검색어가 너무 짧습니다. 회사명, 산업명, 직무명을 2글자 이상 입력해 주세요."
    return ""


def _brief_mode(value: str) -> str:
    normalized = _normalize_search_term(value)
    if not normalized:
        return "industry"
    if any(normalized == _normalize_search_term(company) for company in KNOWN_COMPANIES):
        return "company"
    if any(hint in normalized for hint in INDUSTRY_HINTS):
        return "industry"
    return "industry"


def _work24_company_query(value: str) -> str:
    normalized = _normalize_search_term(value)
    if normalized in {"thn", _normalize_search_term("티에이치엔")}:
        return "티에이치엔"
    return value


def _unique_docs_by_outlet(docs: list[dict], *, limit: int = 3) -> list[dict]:
    best_by_outlet = {}
    for doc in docs:
        outlet = (doc.get("outlet") or doc.get("link") or "").lower()
        key = outlet.removeprefix("www.")
        current = best_by_outlet.get(key)
        if current is None or len(doc.get("summary", "")) > len(current.get("summary", "")):
            best_by_outlet[key] = doc
    return list(best_by_outlet.values())[:limit]


def _positive_int(value: str | None, *, default: int = 1) -> int:
    try:
        parsed = int(value or default)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def _api_status() -> dict:
    load_dotenv(Path(__file__).resolve().parent / ".env", override=True)
    from importlib import reload

    import config as config_module

    reload(config_module)
    cfg = config_module.Config

    return {
        "naver": bool(cfg.NAVER_CLIENT_ID and cfg.NAVER_CLIENT_SECRET),
        "kakao": bool(cfg.KAKAO_REST_API_KEY),
    }


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)
