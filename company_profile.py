JOB_GUIDES = {
    "생산관리": {
        "competencies": ["공정 이해", "일정 관리", "현장 소통"],
        "preparation": "생산 계획, 납기, 품질 이슈를 조율한 경험을 수치와 함께 정리해 보세요.",
    },
    "품질관리": {
        "competencies": ["문제 분석", "개선 활동", "품질 기준 이해"],
        "preparation": "불량 원인 분석, 재발 방지, 표준 준수 경험을 STAR 구조로 준비해 보세요.",
    },
    "품질": {
        "competencies": ["검사 기준", "데이터 분석", "개선 제안"],
        "preparation": "품질 이슈를 발견하고 개선한 경험을 지원 기업의 제품과 연결해 보세요.",
    },
    "구매": {
        "competencies": ["협상력", "원가 의식", "공급망 이해"],
        "preparation": "협력사 관리, 원가 절감, 납기 리스크 대응 관점으로 경험을 정리해 보세요.",
    },
    "연구개발": {
        "competencies": ["기술 이해", "실험 설계", "협업 문서화"],
        "preparation": "프로젝트에서 맡은 기술 과제와 검증 과정을 구체적으로 설명할 수 있어야 합니다.",
    },
    "SW 개발": {
        "competencies": ["문제 해결", "시스템 사고", "협업 개발"],
        "preparation": "개발 프로젝트의 요구사항, 구현 방식, 오류 해결 과정을 중심으로 준비해 보세요.",
    },
    "생산기술": {
        "competencies": ["설비 이해", "공정 개선", "원인 분석"],
        "preparation": "공정 효율, 설비 안정화, 자동화 개선 경험을 직무 언어로 정리해 보세요.",
    },
    "설비기술": {
        "competencies": ["설비 보전", "트러블슈팅", "안전 의식"],
        "preparation": "설비 문제를 진단하고 재발을 줄인 경험을 구체적인 절차로 설명해 보세요.",
    },
    "설계": {
        "competencies": ["도면 이해", "제품 구조", "검증 사고"],
        "preparation": "설계 변경, 성능 검토, 협업 조율 경험을 제품 관점으로 연결해 보세요.",
    },
    "영업": {
        "competencies": ["고객 이해", "시장 분석", "커뮤니케이션"],
        "preparation": "고객 요구를 파악하고 해결안을 제안한 경험을 자동차 산업 흐름과 연결해 보세요.",
    },
}


DEFAULT_JOB_GUIDE = {
    "competencies": ["직무 이해", "문제 해결", "협업"],
    "preparation": "지원 직무의 역할을 조사하고 본인의 경험을 성과 중심으로 정리해 보세요.",
}


def build_company_profile(name, company):
    jobs = company.get("jobs", [])
    job_guides = []

    for job in jobs:
        guide = JOB_GUIDES.get(job, DEFAULT_JOB_GUIDE)
        job_guides.append({
            "name": job,
            "competencies": guide["competencies"],
            "preparation": guide["preparation"],
        })

    return {
        "facts": [
            {"label": "업종", "value": company.get("industry", "확인 필요")},
            {"label": "주요 지역", "value": company.get("location", "확인 필요")},
            {"label": "주요 직무", "value": ", ".join(jobs) or "확인 필요"},
            {"label": "기업 홈페이지", "value": "공식 홈페이지에서 최신 공고 확인"},
        ],
        "recruit_steps": [
            "기업 및 직무 조사",
            "채용공고 조건 확인",
            "이력서·자기소개서 작성",
            "직무/역량 면접 준비",
            "최근 뉴스 기반 질문 대비",
        ],
        "benefit_checks": [
            "근무지와 통근 가능성",
            "신입 교육 및 직무 온보딩",
            "성과급·복지포인트 등 보상 항목",
            "교대근무 여부와 근무 형태",
            "기숙사·식사·통근버스 제공 여부",
        ],
        "application_tips": [
            f"{company.get('industry', '해당 산업')} 흐름을 {name}의 제품·직무와 연결하기",
            "지원 직무에서 자주 쓰이는 용어를 자기소개서에 자연스럽게 반영하기",
            "최근 뉴스 요약을 면접 답변의 첫 문장 또는 근거로 활용하기",
        ],
        "job_guides": job_guides,
    }
