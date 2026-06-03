from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import quote_plus

from config import HYUNDAI_KIA_FIRST_TIER_VENDORS
from job_collector import collect_public_jobs


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
JOBS_CACHE_FILE = DATA_DIR / "vendor_jobs_cache.json"
JOBS_CACHE_TTL_SECONDS = 60 * 60
JOBS_CACHE_VERSION = 7

COMPANY_SPECIALTIES = {
    "현대위아": ["파워트레인", "모빌리티 부품", "생산기술"],
    "에스엘": ["램프", "전장 부품", "자동차 조명"],
    "아진산업": ["차체 부품", "프레스", "자동차 구조부품"],
    "성우하이텍": ["차체", "프레스", "경량화 부품"],
    "현대케피코": ["엔진제어", "전장제어", "제어기"],
    "만도": ["제동", "조향", "샤시"],
    "경신": ["와이어링", "전장", "전기차 부품"],
    "유라코퍼레이션": ["와이어링", "전장", "커넥터"],
    "서연이화": ["내장재", "시트", "자동차 인테리어"],
    "현대성우쏠라이트": ["배터리", "에너지", "자동차 전원"],
}


def company_profiles() -> List[Dict[str, Any]]:
    profiles = []
    for idx, company in enumerate(HYUNDAI_KIA_FIRST_TIER_VENDORS, start=1):
        specialties = COMPANY_SPECIALTIES.get(company) or _default_specialties(company)
        profiles.append(
            {
                "rank": idx,
                "name": company,
                "group": _company_group(company, specialties),
                "specialties": specialties,
                "summary": _summary(company, specialties),
                "research_points": _research_points(company, specialties),
                "prep_keywords": _prep_keywords(company, specialties),
                "detail_blocks": _detail_blocks(company, specialties),
            }
        )
    return profiles


def vendor_jobs_snapshot(*, query: str = "", refresh: bool = False) -> Dict[str, Any]:
    query = query.strip()
    if not refresh:
        cached = _load_jobs_cache(query=query)
        if cached:
            return cached

    companies = [query] if query else HYUNDAI_KIA_FIRST_TIER_VENDORS
    rows = []
    errors = []
    for company in companies:
        try:
            result = collect_public_jobs(
                company,
                limit=8 if query else 5,
                max_queries=3 if query else 1,
                provider_strategy="all" if query else "first",
                refresh=refresh,
            )
        except Exception as exc:  # noqa: BLE001
            result = {"items": [], "error": str(exc), "providers": []}
        error = result.get("error", "")
        if error:
            errors.append(f"{company}: {error}")
        rows.append(_public_job_row(company, result))

    payload = {
        "version": JOBS_CACHE_VERSION,
        "mode": "public_search",
        "query": query,
        "api_blocked": False,
        "notice": (
            "채용공고는 고용24 채용정보 API 없이 네이버/카카오 공개 웹검색 결과에서 "
            "채용 사이트와 공식 채용 페이지 후보만 필터링해 표시합니다."
        ),
        "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "rows": rows,
        "errors": errors[:5],
    }
    _save_jobs_cache(payload)
    return payload


def _default_specialties(company: str) -> List[str]:
    if any(token in company for token in ("전기", "전자", "케피코", "경신", "유라")):
        return ["전장 부품", "전기·전자", "품질관리"]
    if any(token in company for token in ("화성", "화학", "금속", "메탈", "캐스팅")):
        return ["소재·금속", "부품 제조", "공정관리"]
    if any(token in company for token in ("공조", "쏠라이트")):
        return ["에너지·공조", "자동차 부품", "설비관리"]
    return ["자동차 부품", "1차 협력사", "생산·품질"]


def _company_group(company: str, specialties: List[str]) -> str:
    joined = " ".join(specialties)
    if "전장" in joined or "전자" in joined or "와이어링" in joined:
        return "전장/전자"
    if "차체" in joined or "프레스" in joined or "금속" in joined:
        return "차체/금속"
    if "배터리" in joined or "공조" in joined or "에너지" in joined:
        return "에너지/공조"
    if "내장" in joined or "시트" in joined:
        return "내외장"
    return "부품 제조"


def _summary(company: str, specialties: List[str]) -> str:
    return (
        f"{company}은 현대/기아 1차 협력사 목록에 포함된 기업으로, "
        f"{', '.join(specialties[:2])} 관련 키워드를 중심으로 기업 리서치를 진행하기 좋습니다."
    )


def _research_points(company: str, specialties: List[str]) -> List[str]:
    return [
        f"{company}의 최근 수주, 투자, 실적 관련 뉴스 확인",
        f"{specialties[0]} 관련 제품과 고객사를 직무와 연결",
        "채용공고의 근무지, 직무, 필요 역량, 복리후생 문구 확인",
        "품질, 생산성, 공급망, 전동화 이슈가 회사에 주는 영향 정리",
    ]


def _prep_keywords(company: str, specialties: List[str]) -> List[str]:
    base = ["현대차그룹", "품질관리", "생산기술", "공급망"]
    return list(dict.fromkeys(specialties + base))[:7]


def _detail_blocks(company: str, specialties: List[str]) -> List[Dict[str, Any]]:
    main_area = specialties[0]
    secondary = specialties[1] if len(specialties) > 1 else "자동차 부품"
    return [
        {
            "title": "사업/제품 관점",
            "items": [
                f"{main_area}, {secondary} 키워드를 중심으로 현대/기아 공급망 내 역할을 확인",
                "전동화, 경량화, 품질 안정성, 원가 경쟁력 이슈와 연결해서 기사 해석",
                "제품이 완성차의 안전, 내구, 편의, 생산성 중 어디에 기여하는지 정리",
            ],
        },
        {
            "title": "직무 연결",
            "items": [
                "생산기술, 품질관리, 구매/SCM, 설비보전, 연구개발 직무와 연결 가능",
                f"{company} 채용공고가 있으면 요구 역량, 근무지, 우대사항을 우선 확인",
                "지원 직무가 현장 개선형인지, 개발/검증형인지, 고객 대응형인지 구분",
            ],
        },
        {
            "title": "지원 준비",
            "items": [
                "최근 뉴스에서 수주, 증설, 실적, 노사, 품질 이슈를 한 줄 근거로 정리",
                "회사 선택 이유는 제품군과 본인 경험을 연결해 구체화",
                "면접에서는 완성차 협력사 특성상 납기, 품질, 협업 경험을 준비",
            ],
        },
    ]


def _public_job_row(company: str, result: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "company": company,
        "enabled": bool(result.get("providers")),
        "jobs": result.get("items", []),
        "total": len(result.get("items", [])),
        "error": result.get("error", ""),
        "providers": result.get("providers", []),
        "search_links": _job_search_links(company),
    }


def _job_search_links(company: str) -> List[Dict[str, str]]:
    encoded_company = quote_plus(company)
    encoded_recruit = quote_plus(f"{company} 채용")
    return [
        {
            "label": "고용24",
            "url": "https://www.work24.go.kr/wk/a/b/1200/retriveDtlEmpSrchList.do",
        },
        {
            "label": "잡코리아",
            "url": f"https://www.jobkorea.co.kr/Search/?stext={encoded_company}",
        },
        {
            "label": "사람인",
            "url": f"https://www.saramin.co.kr/zf_user/search?searchword={encoded_company}",
        },
        {
            "label": "네이버",
            "url": f"https://search.naver.com/search.naver?where=web&query={encoded_recruit}",
        },
    ]


def _load_jobs_cache(*, query: str = "") -> Dict[str, Any] | None:
    if not JOBS_CACHE_FILE.exists():
        return None
    try:
        with open(JOBS_CACHE_FILE, "r", encoding="utf-8") as f:
            payload = json.load(f)
    except Exception:  # noqa: BLE001
        return None
    if time.time() - JOBS_CACHE_FILE.stat().st_mtime > JOBS_CACHE_TTL_SECONDS:
        return None
    if (
        isinstance(payload, dict)
        and payload.get("version") == JOBS_CACHE_VERSION
        and (payload.get("query") or "") == query
    ):
        return payload
    return None


def _save_jobs_cache(payload: Dict[str, Any]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(JOBS_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
