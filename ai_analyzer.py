import json

from openai import OpenAI

from career_data import get_spec_library_text
from config import Config


client = OpenAI(
    api_key=Config.OPENAI_API_KEY,
    max_retries=1,
    timeout=60,
)


def format_list(values):
    if not values:
        return "확인 필요"

    return ", ".join(values)


def format_profile(user_profile):
    if not user_profile:
        return "입력된 개인 프로필 없음"

    return f"""
전공: {user_profile.get("major", "") or "미입력"}
관심 직무: {user_profile.get("target_job", "") or "미입력"}
보유 자격증: {user_profile.get("certificates", "") or "미입력"}
경험/활동: {user_profile.get("experience", "") or "미입력"}
강점: {user_profile.get("strengths", "") or "미입력"}
""".strip()


def format_company(company_profile):
    if not company_profile:
        return "회사 정보 없음"

    return f"""
회사명: {company_profile.get("name", "")}
사업 특징: {company_profile.get("business", "")}
주요 직무: {format_list(company_profile.get("jobs", []))}
인재상/핵심 역량: {format_list(company_profile.get("talent", []))}
채용 페이지: {company_profile.get("career_page", "") or "확인 필요"}
""".strip()


def format_ai_value(value):
    if isinstance(value, list):
        return "\n".join(f"- {item}" for item in value)

    if isinstance(value, dict):
        lines = []

        for key, item in value.items():
            if isinstance(item, list):
                lines.append(f"- {key}")
                lines.extend(f"  - {entry}" for entry in item)
            else:
                lines.append(f"- {key}: {item}")

        return "\n".join(lines)

    return value or ""


def build_ai_analysis(result):
    return f"""
[뉴스 3줄 요약]
{result.get("ai_summary", "")}

[기사와 연결되는 직무]
{result.get("related_jobs", "")}

[스펙이 될 만한 자격증/활동]
{result.get("spec_activities", "")}

[포트폴리오 소재]
{result.get("portfolio_ideas", "")}

[회사 인재상 연결]
{result.get("talent_fit", "")}

[자기소개서에 녹일 방향]
{result.get("cover_letter_direction", "")}

[자기소개서 초안]
{result.get("cover_letter_draft", "")}

[면접 예상 질문]
{result.get("interview_questions", "")}

[답변 방향]
{result.get("answer_direction", "")}

[개인 맞춤 보완점]
{result.get("profile_gap", "")}

[한 줄 취업 전략]
{result.get("career_strategy", "")}
""".strip()


def failed_analysis(message):
    return {
        "analysis_status": "failed",
        "ai_summary": message,
        "related_jobs": message,
        "spec_activities": message,
        "portfolio_ideas": message,
        "talent_fit": message,
        "cover_letter_direction": message,
        "cover_letter_draft": message,
        "interview_questions": message,
        "answer_direction": message,
        "profile_gap": message,
        "career_strategy": message,
        "ai_analysis": message,
    }


def normalize_batch_item(item):
    result = {
        "analysis_status": "ok",
        "ai_summary": format_ai_value(item.get("ai_summary", "")),
        "related_jobs": format_ai_value(item.get("related_jobs", "")),
        "spec_activities": format_ai_value(item.get("spec_activities", "")),
        "portfolio_ideas": format_ai_value(item.get("portfolio_ideas", "")),
        "talent_fit": format_ai_value(item.get("talent_fit", "")),
        "cover_letter_direction": format_ai_value(item.get("cover_letter_direction", "")),
        "cover_letter_draft": format_ai_value(item.get("cover_letter_draft", "")),
        "interview_questions": format_ai_value(item.get("interview_questions", "")),
        "answer_direction": format_ai_value(item.get("answer_direction", "")),
        "profile_gap": format_ai_value(item.get("profile_gap", "")),
        "career_strategy": format_ai_value(item.get("career_strategy", "")),
    }

    result["ai_analysis"] = build_ai_analysis(result)
    return result


def analyze_news(title, summary, company_profile=None, user_profile=None):
    return analyze_news_batch(
        [{"index": 0, "title": title, "summary": summary}],
        company_profile=company_profile,
        user_profile=user_profile,
    )[0]


def analyze_news_batch(
    articles,
    company_profile=None,
    user_profile=None,
    retry_missing=True,
):
    if not articles:
        return []

    article_text = json.dumps(articles, ensure_ascii=False, indent=2)

    prompt = f"""
너는 자동차·모빌리티 산업 취업 컨설턴트다.
아래 회사 정보, 지원자 프로필, 직무 준비 라이브러리, 뉴스 목록을 함께 보고 취업 준비 관점으로 분석해라.

중요 규칙:
- 반드시 JSON만 응답한다.
- 입력된 모든 기사 index를 빠짐없이 items에 포함한다.
- 회사 정보에 있는 인재상/주요 직무를 우선 참고한다.
- 뉴스에 없는 사실은 단정하지 말고 "추정" 또는 "확인 필요"라고 쓴다.
- 모든 값은 배열이 아니라 줄바꿈이 포함된 문자열로 작성한다.
- 면접 질문은 "- 질문" 형태로 4개 작성한다.
- talent_fit, cover_letter_direction, interview_questions는 너무 짧게 쓰지 말고 각각 2~4문장 또는 3~4개 bullet로 구체화한다.
- 화면에서 읽기 좋게 한 항목은 2~5줄 정도로 정리한다.

회사 정보:
{format_company(company_profile)}

지원자 프로필:
{format_profile(user_profile)}

직무 준비 라이브러리:
{get_spec_library_text()}

분석할 기사 목록 JSON:
{article_text}

응답 형식:
{{
  "items": [
    {{
      "index": 0,
      "ai_summary": "뉴스 3줄 요약",
      "related_jobs": "기사와 연결되는 직무",
      "spec_activities": "스펙이 될 만한 자격증/활동",
      "portfolio_ideas": "포트폴리오 소재",
      "talent_fit": "회사 인재상 연결",
      "cover_letter_direction": "자기소개서에 녹일 방향",
      "cover_letter_draft": "자기소개서 초안",
      "interview_questions": "면접 예상 질문",
      "answer_direction": "답변 방향",
      "profile_gap": "개인 맞춤 보완점",
      "career_strategy": "한 줄 취업 전략"
    }}
  ]
}}
""".strip()

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "너는 취업준비생을 위한 자동차 산업 뉴스 분석가다. JSON만 응답한다.",
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            temperature=0.2,
            max_tokens=4200,
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content
        payload = json.loads(content)
        raw_items = payload.get("items", [])
        result_map = {
            int(item.get("index")): normalize_batch_item(item)
            for item in raw_items
            if item.get("index") is not None
        }

        if retry_missing:
            missing_indexes = [
                index
                for index in range(len(articles))
                if index not in result_map
            ]

            if missing_indexes:
                retry_articles = [
                    {
                        "index": retry_index,
                        "title": articles[original_index].get("title", ""),
                        "summary": articles[original_index].get("summary", ""),
                    }
                    for retry_index, original_index in enumerate(missing_indexes)
                ]

                retry_results = analyze_news_batch(
                    retry_articles,
                    company_profile=company_profile,
                    user_profile=user_profile,
                    retry_missing=False,
                )

                for original_index, retry_result in zip(missing_indexes, retry_results):
                    result_map[original_index] = retry_result

        results = []

        for index in range(len(articles)):
            if index in result_map:
                results.append(result_map[index])
            else:
                results.append(failed_analysis("AI 분석 결과 누락"))

        return results

    except Exception as e:
        print(f"[AI 배치 분석 실패] {e}")
        return [
            failed_analysis("AI 배치 분석 실패. 새로고침하거나 다시 분석해 주세요.")
            for _ in articles
        ]
