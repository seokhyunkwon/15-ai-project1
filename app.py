import re
from hashlib import sha1
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
from news_collector import (
    collect_news,
    filter_loaded_items,
    load_payload,
    save_items,
)
from search_policy import normalize_search_query, validate_search_query
from company_research import collect_company_research
from company_directory import company_profiles, vendor_jobs_snapshot
from job_collector import collect_public_jobs
from llm import (
    build_article_summary,
    build_company_research,
    build_interview_questions_fallback,
    build_news_brief,
    llm_status,
)
from work24_client import work24_status


def create_app() -> Flask:
    load_dotenv(Path(__file__).resolve().parent / ".env", override=True)
    app = Flask(__name__)
    app.secret_key = "dev-news-dashboard"

    @app.context_processor
    def inject_asset_version():
        static_dir = Path(app.root_path) / "static"
        version = 1
        for filename in ("style.css", "app.js", "briefjob-logo.svg"):
            try:
                version = max(version, int((static_dir / filename).stat().st_mtime))
            except OSError:
                continue
        return {"asset_version": version}

    @app.route("/", methods=["GET"])
    def index():
        payload = load_payload()
        company = request.args.get("company", "").strip()
        search_q = request.args.get("q", "").strip()
        category = request.args.get("category", "전체")
        keyword = request.args.get("keyword", "").strip()
        brief_requested = request.args.get("brief") == "1"
        article_id = request.args.get("article", "").strip()
        landing_mode = not any([company, search_q, keyword, brief_requested, article_id])
        page = _positive_int(request.args.get("page"), default=1)
        per_page = 50
        brief_topic = company or keyword or search_q
        search_warning = _search_validation_message(brief_topic) if brief_topic else ""
        brief_mode = _brief_mode(brief_topic)

        filtered_news_items = []
        if not landing_mode:
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
        news_items = _with_article_ids(filtered_news_items[start:end])
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
        article_summary = None
        article_summary_id = ""
        research_payload = {"queries": [], "items": [], "error": ""}
        if article_id and not search_warning:
            selected_article = next(
                (item for item in news_items if item.get("article_id") == article_id),
                None,
            )
            if selected_article:
                article_summary_id = article_id
                article_summary = build_article_summary(
                    topic=brief_topic or selected_article.get("keyword", ""),
                    article=selected_article,
                )
        if brief_requested and brief_topic and not search_warning:
            news_brief = build_news_brief(
                company=brief_topic,
                articles=news_items,
                company_profile={},
            )
            if brief_mode == "company":
                work24_jobs = _public_jobs_for_brief(brief_topic)
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

                if not company_research.get("likely_interview_questions"):
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
            analysis_summary=_analysis_summary(payload, filtered_news_items),
            brief_requested=brief_requested,
            brief_topic=brief_topic,
            brief_mode=brief_mode,
            landing_mode=landing_mode,
            search_warning=search_warning,
            news_brief=news_brief,
            article_summary=article_summary,
            article_summary_id=article_summary_id,
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

    @app.route("/companies", methods=["GET"])
    def companies():
        q = request.args.get("q", "").strip()
        group = request.args.get("group", "전체").strip() or "전체"
        profiles = company_profiles()
        groups = ["전체"] + sorted({profile["group"] for profile in profiles})
        if q:
            normalized_q = _normalize_search_term(q)
            profiles = [
                profile for profile in profiles
                if normalized_q in _normalize_search_term(profile["name"])
                or any(normalized_q in _normalize_search_term(word) for word in profile["specialties"])
            ]
        if group != "전체":
            profiles = [profile for profile in profiles if profile["group"] == group]
        return render_template(
            "companies.html",
            profiles=profiles,
            groups=groups,
            selected_group=group,
            q=q,
        )

    @app.route("/jobs", methods=["GET"])
    def jobs():
        refresh = request.args.get("refresh") == "1"
        job_query = request.args.get("q", "").strip()
        snapshot = vendor_jobs_snapshot(query=job_query, refresh=refresh)
        rows = snapshot.get("rows", [])
        active_rows = [row for row in rows if row.get("jobs")]
        return render_template(
            "jobs.html",
            rows=rows,
            active_rows=active_rows,
            job_query=job_query,
            api_blocked=bool(snapshot.get("api_blocked")),
            notice=snapshot.get("notice", ""),
            mode=snapshot.get("mode", ""),
            updated_at=snapshot.get("updated_at", ""),
            errors=snapshot.get("errors", []),
            refreshed=refresh,
        )

    return app


def _normalize_search_term(value: str) -> str:
    return normalize_search_query(value)


def _search_validation_message(value: str) -> str:
    return validate_search_query(value)


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


def _public_jobs_for_brief(company: str) -> dict:
    result = collect_public_jobs(
        company,
        limit=3,
        max_queries=1,
        provider_strategy="first",
    )
    return {
        "enabled": bool(result.get("providers")),
        "items": result.get("items", []),
        "error": result.get("error", ""),
        "providers": result.get("providers", []),
    }


def _with_article_ids(items: list[dict]) -> list[dict]:
    out = []
    for item in items:
        enriched = dict(item)
        enriched["article_id"] = _article_id(item)
        out.append(enriched)
    return out


def _article_id(item: dict) -> str:
    material = "|".join(
        str(item.get(key, ""))
        for key in ("link", "title", "published", "outlet")
    )
    return sha1(material.encode("utf-8")).hexdigest()[:12]


def _analysis_summary(payload: dict, filtered_items: list[dict]) -> dict:
    raw_items = payload.get("items", [])
    raw_count = len(raw_items)
    filtered_count = len(filtered_items)
    excluded_count = max(0, raw_count - filtered_count)
    return {
        "raw_count": raw_count,
        "filtered_count": filtered_count,
        "excluded_count": excluded_count,
        "source_counts": _top_counts(filtered_items, "source", labels=SOURCE_LABELS),
        "category_counts": _top_counts(filtered_items, "category"),
        "keyword_counts": _top_counts(filtered_items, "keyword", limit=5),
        "notes": [
            "커뮤니티·파일·이미지성 결과는 수집 단계에서 제외",
            "제목/요약 기준 회사명 또는 산업 맥락 일치 여부 확인",
            "중복 제목·링크 제거 후 최신순 정렬",
        ],
    }


def _top_counts(items: list[dict], key: str, *, labels: dict | None = None, limit: int = 4) -> list[dict]:
    counts = {}
    for item in items:
        value = item.get(key) or "미분류"
        label = labels.get(value, value) if labels else value
        counts[label] = counts.get(label, 0) + 1
    total = max(1, len(items))
    return [
        {"label": label, "count": count, "share": round(count / total * 100)}
        for label, count in sorted(counts.items(), key=lambda entry: entry[1], reverse=True)[:limit]
    ]


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
