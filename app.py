from pathlib import Path
import json

from flask import Flask, redirect, render_template, request, url_for

from career_data import FEATURED_COMPANIES, get_company_profile
from news_collector import collect_news, save_items


BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = BASE_DIR / "data" / "news.json"


app = Flask(__name__)


@app.route("/", methods=["GET", "POST"])
def home():
    if request.method == "POST":
        return redirect(
            url_for(
                "results",
                keyword=request.form.get("keyword", "").strip(),
                major=request.form.get("major", "").strip(),
                target_job=request.form.get("target_job", "").strip(),
                certificates=request.form.get("certificates", "").strip(),
                experience=request.form.get("experience", "").strip(),
                strengths=request.form.get("strengths", "").strip(),
            )
        )

    return render_template(
        "home.html",
        keyword="",
        user_profile=load_saved_profile(),
        featured_companies=FEATURED_COMPANIES,
    )


@app.route("/results", methods=["GET"])
def results():
    keyword = request.args.get("keyword", "").strip()
    user_profile = read_profile_from_request()
    items = []
    error_message = ""
    company_profile = get_company_profile(keyword) if keyword else None

    if keyword:
        try:
            items = collect_news(
                [keyword],
                display=20,
                ai_limit=20,
                user_profile=user_profile,
            )

            save_items(
                items,
                [keyword],
                user_profile=user_profile,
            )
        except Exception as e:
            error_message = f"분석 중 오류가 발생했습니다: {e}"
    elif DATA_FILE.exists():
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                payload = json.load(f)
                items = payload.get("items", [])
                user_profile.update(payload.get("user_profile", {}))
                saved_keywords = payload.get("keywords", [])

                if saved_keywords:
                    company_profile = get_company_profile(saved_keywords[0])
        except Exception as e:
            error_message = f"저장된 결과를 읽는 중 오류가 발생했습니다: {e}"

    items = prepare_items(items)

    return render_template(
        "results.html",
        items=items,
        keyword=keyword,
        user_profile=user_profile,
        featured_companies=FEATURED_COMPANIES,
        company_profile=company_profile,
        support_strategy=build_support_strategy(company_profile, user_profile),
        category_filters=get_category_filters(items),
        error_message=error_message,
    )


@app.route("/loading", methods=["GET"])
def loading_redirect():
    query_string = request.query_string.decode("utf-8")
    target = url_for("results")

    if query_string:
        target = f"{target}?{query_string}"

    return redirect(target)


def blank_profile():
    return {
        "major": "",
        "target_job": "",
        "certificates": "",
        "experience": "",
        "strengths": "",
    }


def read_profile_from_request():
    return {
        "major": request.args.get("major", "").strip(),
        "target_job": request.args.get("target_job", "").strip(),
        "certificates": request.args.get("certificates", "").strip(),
        "experience": request.args.get("experience", "").strip(),
        "strengths": request.args.get("strengths", "").strip(),
    }


def load_saved_profile():
    user_profile = blank_profile()

    if DATA_FILE.exists():
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            payload = json.load(f)
            user_profile.update(payload.get("user_profile", {}))

    return user_profile


def prepare_items(items):
    prepared = []

    for item in items:
        item = dict(item)
        category = item.get("category") or categorize_item(item)
        item["category"] = category
        item["category_label"] = CATEGORY_LABELS.get(category, "기타")
        prepared.append(item)

    return prepared


CATEGORY_LABELS = {
    "tech": "기술/개발",
    "production": "생산/공장",
    "quality": "품질/부품",
    "hiring": "채용/인재",
    "business": "실적/투자",
    "etc": "기타",
}


CATEGORY_KEYWORDS = {
    "tech": ["기술", "개발", "전장", "자율주행", "소프트웨어", "전기차", "배터리", "R&D", "연구", "모빌리티"],
    "production": ["생산", "공장", "라인", "설비", "제조", "양산", "스마트팩토리"],
    "quality": ["품질", "부품", "결함", "검사", "램프", "헤드램프", "모듈", "안전"],
    "hiring": ["채용", "인재", "신입", "인턴", "공채", "직무", "교육"],
    "business": ["실적", "투자", "수주", "매출", "영업이익", "계약", "증설", "협력"],
}


def categorize_item(item):
    text = " ".join(
        str(item.get(key, ""))
        for key in (
            "title",
            "summary",
            "related_jobs",
            "spec_activities",
            "portfolio_ideas",
        )
    )

    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(keyword.lower() in text.lower() for keyword in keywords):
            return category

    return "etc"


def get_category_filters(items):
    counts = {"all": len(items)}

    for item in items:
        category = item.get("category", "etc")
        counts[category] = counts.get(category, 0) + 1

    filters = [{"key": "all", "label": "전체", "count": counts["all"]}]

    for key, label in CATEGORY_LABELS.items():
        if counts.get(key, 0):
            filters.append(
                {
                    "key": key,
                    "label": label,
                    "count": counts[key],
                }
            )

    return filters


def build_support_strategy(company_profile, user_profile):
    if not company_profile:
        return None

    jobs = company_profile.get("jobs", [])
    talents = company_profile.get("talent", [])
    target_job = user_profile.get("target_job") if user_profile else ""

    primary_jobs = ", ".join(jobs[:3]) if jobs else "직무"
    primary_talents = ", ".join(talents[:3]) if talents else "문제 해결력, 협업"
    job_direction = target_job or (jobs[0] if jobs else "관심 직무")

    return {
        "headline": f"{company_profile.get('name', '이 회사')}는 {primary_jobs} 흐름을 중심으로 준비하면 좋습니다.",
        "bullets": [
            f"뉴스는 {company_profile.get('business', '주요 사업')}와 연결해서 읽어보세요.",
            f"자기소개서에서는 {primary_talents}을 기사 사례와 함께 보여주는 방향이 좋습니다.",
            f"면접에서는 '{job_direction}' 관점에서 기사 속 변화가 내 직무에 어떤 영향을 주는지 설명해보세요.",
        ],
    }


if __name__ == "__main__":
    app.run(debug=True)
