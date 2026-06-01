COMPANY_PROFILES = {
    "현대모비스": {
        "name": "현대모비스",
        "aliases": ["현대모비스", "모비스", "Hyundai Mobis"],
        "search_hint": "자동차 부품 전장 모듈 자율주행 제동",
        "industry_terms": ["자동차", "부품", "전장", "모듈", "자율주행", "제동", "램프"],
        "business": "자동차 핵심 부품, 전장, 모듈, 자율주행, 제동 부품 중심 기업",
        "talent": ["전문성", "도전", "협업", "품질 의식", "미래 모빌리티 이해"],
        "jobs": ["전장 설계", "모듈 개발", "품질관리", "생산기술", "소프트웨어", "구매"],
        "career_page": "https://careers.mobis.com",
    },
    "에스엘": {
        "name": "에스엘",
        "aliases": ["에스엘", "SL", "S L"],
        "search_hint": "자동차 헤드램프 램프 부품 전장",
        "industry_terms": ["자동차", "헤드램프", "램프", "전장", "부품", "조명"],
        "business": "자동차 램프, 전장 부품, 헤드램프 중심의 자동차 부품 기업",
        "talent": ["기술 이해도", "품질 의식", "문제 해결력", "협업", "제조 현장 이해"],
        "jobs": ["램프 설계", "전장 설계", "품질관리", "생산기술", "구매", "영업"],
        "career_page": "https://www.slworld.com",
    },
    "현대차": {
        "name": "현대자동차",
        "aliases": ["현대차", "현대자동차"],
        "search_hint": "자동차 모빌리티 전기차 자율주행",
        "industry_terms": ["자동차", "모빌리티", "전기차", "자율주행", "생산", "품질"],
        "business": "완성차, 전기차, 수소, 자율주행, 모빌리티 서비스 중심 기업",
        "talent": ["도전", "고객 중심", "협업", "창의", "글로벌 감각"],
        "jobs": ["차량 개발", "생산기술", "품질", "구매", "영업/마케팅", "데이터/소프트웨어"],
        "career_page": "https://talent.hyundai.com",
    },
    "기아": {
        "name": "기아",
        "aliases": ["기아", "기아차"],
        "search_hint": "자동차 모빌리티 전기차 PBV",
        "industry_terms": ["자동차", "모빌리티", "전기차", "PBV", "생산", "품질"],
        "business": "완성차, 전기차, PBV, 모빌리티 솔루션 중심 기업",
        "talent": ["고객 중심", "도전", "협업", "실행력", "변화 대응"],
        "jobs": ["상품기획", "생산기술", "품질", "구매", "영업/마케팅", "전동화 개발"],
        "career_page": "https://career.kia.com",
    },
    "신라": {
        "name": "신라",
        "aliases": ["신라", "신라코퍼레이션"],
        "search_hint": "자동차 부품 전장 와이어링 하네스",
        "industry_terms": ["자동차", "부품", "전장", "와이어링", "하네스"],
        "business": "자동차 전장 부품과 와이어링 하네스 중심 기업",
        "talent": ["현장 이해", "품질 의식", "제조 이해", "성실성", "협업"],
        "jobs": ["전장 설계", "품질관리", "생산기술", "구매", "해외영업"],
        "career_page": "",
    },
    "THN": {
        "name": "THN",
        "aliases": ["THN", "티에이치엔", "티에이치엔 주식회사"],
        "search_hint": "자동차 와이어링 하네스 전장 부품",
        "industry_terms": ["자동차", "와이어링", "하네스", "전장", "부품", "커넥터"],
        "business": "자동차 와이어링 하네스와 전장 부품을 중심으로 하는 자동차 부품 기업",
        "talent": ["현장 이해", "품질 의식", "문제 해결력", "협업", "전장 부품 이해"],
        "jobs": ["전장 설계", "품질관리", "생산기술", "구매", "해외영업", "생산관리"],
        "career_page": "https://www.th-net.co.kr",
    },
}


FEATURED_COMPANIES = [
    {
        "keyword": "현대모비스",
        "label": "현대모비스",
        "description": "전장·모듈·자율주행",
    },
    {
        "keyword": "현대차",
        "label": "현대자동차",
        "description": "완성차·전동화·모빌리티",
    },
    {
        "keyword": "기아",
        "label": "기아",
        "description": "전기차·PBV·상품기획",
    },
    {
        "keyword": "에스엘",
        "label": "에스엘",
        "description": "헤드램프·전장 부품",
    },
    {
        "keyword": "THN",
        "label": "THN",
        "description": "와이어링 하네스·전장",
    },
    {
        "keyword": "신라",
        "label": "신라",
        "description": "전장·와이어링 하네스",
    },
]


DEFAULT_COMPANY_PROFILE = {
    "name": "검색 회사",
    "aliases": [],
    "search_hint": "자동차 모빌리티 부품 채용",
    "industry_terms": ["자동차", "모빌리티", "부품", "전장", "생산", "품질", "채용"],
    "business": "자동차 모빌리티 관련 기업으로 추정",
    "talent": ["문제 해결력", "협업", "직무 이해", "산업 관심도"],
    "jobs": ["생산기술", "품질관리", "연구개발", "구매", "영업"],
    "career_page": "",
}


JOB_SPEC_LIBRARY = {
    "생산기술": {
        "certificates": ["일반기계기사", "기계설계산업기사", "산업안전기사", "6시그마 GB"],
        "activities": ["공정 개선 프로젝트", "스마트팩토리 교육", "설비 데이터 분석 실습"],
        "portfolio": ["공정 불량 원인 분석", "작업 표준 개선안", "생산성 개선 리포트"],
    },
    "품질관리": {
        "certificates": ["품질경영기사", "6시그마 GB/BB", "ISO 9001 교육"],
        "activities": ["불량 분석 프로젝트", "통계적 품질관리 실습", "8D 리포트 작성"],
        "portfolio": ["불량률 개선 사례", "관리도 분석", "검사 기준 개선안"],
    },
    "전장 설계": {
        "certificates": ["전기기사", "전기공사기사", "전자기사", "임베디드 교육"],
        "activities": ["회로 설계 프로젝트", "CAN/LIN 통신 실습", "센서 제어 프로젝트"],
        "portfolio": ["회로/PCB 설계", "차량 센서 제어", "전장 부품 검증 리포트"],
    },
    "램프 설계": {
        "certificates": ["일반기계기사", "기계설계산업기사", "CATIA/UG/NX 교육"],
        "activities": ["3D 설계 프로젝트", "광학/열 해석 기초 학습", "자동차 램프 구조 분석"],
        "portfolio": ["램프 구조 벤치마킹", "방열 구조 개선안", "CAD 설계 결과물"],
    },
    "구매": {
        "certificates": ["물류관리사", "국제무역사", "컴퓨터활용능력"],
        "activities": ["원가 분석", "협력사 조사", "공급망 리스크 분석"],
        "portfolio": ["부품 원가 구조 분석", "협력사 비교표", "공급망 이슈 리포트"],
    },
    "영업": {
        "certificates": ["국제무역사", "무역영어", "컴퓨터활용능력"],
        "activities": ["시장 조사", "고객사 분석", "B2B 제안서 작성"],
        "portfolio": ["시장 진입 전략", "고객사 니즈 분석", "제품 제안서"],
    },
}


def get_company_profile(keyword):
    normalized = (keyword or "").replace(" ", "").lower()

    for key, profile in COMPANY_PROFILES.items():
        aliases = profile.get("aliases", []) + [key]

        if any(alias.replace(" ", "").lower() == normalized for alias in aliases):
            return profile

    profile = DEFAULT_COMPANY_PROFILE.copy()
    profile["name"] = keyword or profile["name"]
    profile["aliases"] = [keyword] if keyword else []
    return profile


def get_spec_library_text():
    lines = []

    for job, data in JOB_SPEC_LIBRARY.items():
        lines.append(f"- {job}")
        lines.append(f"  자격증: {', '.join(data['certificates'])}")
        lines.append(f"  활동: {', '.join(data['activities'])}")
        lines.append(f"  포트폴리오: {', '.join(data['portfolio'])}")

    return "\n".join(lines)
