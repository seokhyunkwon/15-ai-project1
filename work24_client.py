from __future__ import annotations

import json
import os
import xml.etree.ElementTree as ET
from typing import Any, Dict, Iterable, List

import requests


JOBS_ENDPOINT = "https://www.work24.go.kr/cm/openApi/call/wk/callOpenApiSvcInfo210L01.do"
SMALL_GIANTS_ENDPOINT = "https://www.work24.go.kr/cm/openApi/call/wk/callOpenApiSvcInfo216L01.do"
JOB_DUTY_ENDPOINT = "https://www.work24.go.kr/cm/openApi/call/wk/callOpenApiSvcInfo215L01.do"


def work24_status() -> Dict[str, Any]:
    jobs_key = _env("WORK24_JOBS_API_KEY", "WORK24_API_KEY")
    small_giants_key = _env("WORK24_SMALL_GIANTS_API_KEY", "WORK24_API_KEY")
    job_duty_key = _env("WORK24_JOB_DUTY_API_KEY", "WORK24_API_KEY")
    return {
        "jobs": bool(jobs_key),
        "small_giants": bool(small_giants_key),
        "job_duty": bool(job_duty_key),
        "enabled": bool(jobs_key or small_giants_key or job_duty_key),
    }


def fetch_work24_snapshot(*, company_name: str) -> Dict[str, Any]:
    company_name = company_name.strip()
    jobs = fetch_jobs(keyword=company_name)
    small_giants = fetch_small_giants(company_name=company_name)

    duty_query = _duty_query(company_name=company_name, jobs=jobs.get("items", []))
    job_duties = fetch_job_duties(job_content=duty_query)

    return {
        "company_name": company_name,
        "jobs": jobs,
        "small_giants": small_giants,
        "job_duties": job_duties,
    }


def fetch_jobs(*, keyword: str, display: int = 5) -> Dict[str, Any]:
    api_key = _env("WORK24_JOBS_API_KEY", "WORK24_API_KEY")
    if not api_key:
        return _disabled("WORK24_JOBS_API_KEY")

    params = {
        "authKey": api_key,
        "callTp": "L",
        "returnType": "XML",
        "startPage": 1,
        "display": min(max(display, 1), 100),
        "keyword": keyword,
        "sortOrderBy": "DESC",
    }
    try:
        root = _get_xml(JOBS_ENDPOINT, params=params)
    except Exception as exc:  # noqa: BLE001
        return _failed(exc)

    items = []
    for node in root.findall(".//wanted"):
        item = _xml_fields(
            node,
            {
                "wanted_auth_no": "wantedAuthNo",
                "company": "company",
                "business_no": "busino",
                "industry": "indTpNm",
                "title": "title",
                "salary_type": "salTpNm",
                "salary": "sal",
                "region": "region",
                "work_type": "holidayTpNm",
                "education_min": "minEdubg",
                "education_max": "maxEdubg",
                "career": "career",
                "registered_at": "regDt",
                "close_at": "closeDt",
                "url": "wantedInfoUrl",
                "mobile_url": "wantedMobileInfoUrl",
                "address": "basicAddr",
                "job_code": "jobsCd",
            },
        )
        if item.get("company") or item.get("title"):
            items.append(item)

    return {
        "enabled": True,
        "items": items,
        "total": _text(root, "total"),
        "error": "",
    }


def fetch_small_giants(*, company_name: str, pages: int = 10, display: int = 100) -> Dict[str, Any]:
    api_key = _env("WORK24_SMALL_GIANTS_API_KEY", "WORK24_API_KEY")
    if not api_key:
        return _disabled("WORK24_SMALL_GIANTS_API_KEY")

    matches: List[Dict[str, str]] = []
    errors: List[str] = []
    scanned_count = 0
    total = ""
    for page in range(1, max(1, pages) + 1):
        params = {
            "authKey": api_key,
            "returnType": "XML",
            "startPage": page,
            "display": min(max(display, 1), 100),
        }
        try:
            root = _get_xml(SMALL_GIANTS_ENDPOINT, params=params)
        except Exception as exc:  # noqa: BLE001
            errors.append(str(exc))
            break

        if not total:
            total = _text(root, "total")
        page_items = []
        for node in root.findall(".//smallGiant"):
            item = _xml_fields(
                node,
                {
                    "selected_year": "selYear",
                    "brand": "sgBrandNm",
                    "company": "coNm",
                    "business_no": "busiNo",
                    "representative": "reperNm",
                    "industry_large": "superIndTpNm",
                    "industry": "indTpNm",
                    "phone": "coTelNo",
                    "region": "regionNm",
                    "address": "coAddr",
                    "main_product": "coMainProd",
                    "homepage": "coHomePage",
                    "workers": "alwaysWorkerCnt",
                },
            )
            page_items.append(item)

        scanned_count += len(page_items)
        matches.extend(_filter_company_matches(page_items, company_name))
        if not page_items:
            break

    return {
        "enabled": True,
        "items": _unique_by(matches, "business_no")[:5],
        "error": "; ".join(errors),
        "searched_pages": pages,
        "scanned_count": scanned_count,
        "total": total,
    }


def fetch_job_duties(*, job_content: str, limit: int = 5) -> Dict[str, Any]:
    api_key = _env("WORK24_JOB_DUTY_API_KEY", "WORK24_API_KEY")
    if not api_key:
        return _disabled("WORK24_JOB_DUTY_API_KEY")
    if not job_content.strip():
        return {"enabled": True, "items": [], "query": "", "error": ""}

    params = {
        "authKey": api_key,
        "jobCont": job_content,
        "limit": min(max(limit, 1), 10),
        "returnType": "JSON",
    }
    try:
        resp = requests.get(JOB_DUTY_ENDPOINT, params=params, timeout=10)
        resp.raise_for_status()
        payload = resp.json()
    except json.JSONDecodeError as exc:
        return _failed(exc)
    except requests.RequestException as exc:
        return _failed(exc)

    if isinstance(payload, dict) and payload.get("message"):
        return {
            "enabled": True,
            "items": [],
            "query": job_content,
            "error": str(payload.get("message") or ""),
        }

    raw_items = _extract_duty_items(payload)
    items = [
        {
            "unit_name": str(item.get("job_sdvn") or item.get("name") or "").strip(),
            "definition": str(item.get("ablt_def") or "").strip(),
            "category_large": str(item.get("job_lcfn") or "").strip(),
            "category_mid": str(item.get("job_mcn") or "").strip(),
            "category_small": str(item.get("job_scfn") or "").strip(),
            "unit_code": str(item.get("ablt_unit") or "").strip(),
            "knowledge_skill_attitude": str(item.get("knwg_tchn_attd") or "").strip(),
        }
        for item in raw_items
        if isinstance(item, dict)
    ]
    error = ""
    if not items:
        error = "직무정보 API가 추천 결과를 반환하지 않았습니다. 인증키 승인 서비스와 수행직무내용을 확인해 주세요."
    return {"enabled": True, "items": items, "query": job_content, "error": error}


def _env(*names: str) -> str:
    for name in names:
        value = (os.getenv(name) or "").strip()
        if value:
            return value
    return ""


def _get_xml(url: str, *, params: Dict[str, Any]) -> ET.Element:
    resp = requests.get(url, params=params, timeout=10)
    resp.raise_for_status()
    root = ET.fromstring(resp.content)
    error = _text(root, "error") or _text(root, "message") or _text(root, "messageText")
    if error:
        raise RuntimeError(error)
    return root


def _text(node: ET.Element, tag: str) -> str:
    found = node.find(tag)
    if found is None or found.text is None:
        return ""
    return found.text.strip()


def _xml_fields(node: ET.Element, mapping: Dict[str, str]) -> Dict[str, str]:
    return {key: _text(node, tag) for key, tag in mapping.items()}


def _normalize(value: str) -> str:
    return "".join(ch for ch in value.lower() if ch.isalnum())


def _filter_company_matches(items: Iterable[Dict[str, str]], company_name: str) -> List[Dict[str, str]]:
    target = _normalize(company_name)
    if not target:
        return []
    out = []
    for item in items:
        company = _normalize(item.get("company", ""))
        if target in company or company in target:
            out.append(item)
    return out


def _unique_by(items: Iterable[Dict[str, str]], key: str) -> List[Dict[str, str]]:
    seen = set()
    out = []
    for item in items:
        marker = item.get(key) or item.get("company") or repr(item)
        if marker in seen:
            continue
        seen.add(marker)
        out.append(item)
    return out


def _duty_query(*, company_name: str, jobs: List[Dict[str, str]]) -> str:
    for job in jobs:
        title = (job.get("title") or "").strip()
        if title:
            return title
    return f"{company_name} 지원 직무 수행 업무"


def _extract_duty_items(payload: Any) -> List[Dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []

    result = payload.get("result")
    if isinstance(result, list):
        return [item for item in result if isinstance(item, dict)]
    if isinstance(result, dict):
        if all(isinstance(v, dict) for v in result.values()):
            return list(result.values())
        return [result]

    dict_items = []
    for value in payload.values():
        if isinstance(value, dict) and any(k in value for k in ("job_sdvn", "ablt_def", "ablt_unit")):
            dict_items.append(value)
    return dict_items


def _disabled(key_name: str) -> Dict[str, Any]:
    return {
        "enabled": False,
        "items": [],
        "error": f"{key_name} 미설정",
    }


def _failed(exc: Exception) -> Dict[str, Any]:
    return {
        "enabled": True,
        "items": [],
        "error": str(exc),
    }
