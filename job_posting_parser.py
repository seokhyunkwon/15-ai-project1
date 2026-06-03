from __future__ import annotations

import ipaddress
import re
import socket
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup


JOB_HINTS = (
    "채용",
    "모집",
    "공고",
    "신입",
    "경력",
    "직무",
    "담당업무",
    "자격요건",
    "우대사항",
    "근무지",
    "전형",
    "지원",
)

BLOCKED_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0"}


def collect_job_posting(url: str) -> dict:
    url = (url or "").strip()
    if not url:
        return {"url": "", "error": "지원공고 링크를 입력해 주세요."}

    validation_error = _validate_public_url(url)
    if validation_error:
        return {"url": url, "error": validation_error}

    try:
        response = requests.get(
            url,
            headers={"User-Agent": "Mozilla/5.0 BriefJob/1.0"},
            timeout=10,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        return {
            "url": url,
            "error": f"지원공고 링크를 열지 못했습니다: {exc}",
        }

    soup = BeautifulSoup(response.text[:350_000], "html.parser")
    title = _first_meta(soup, ("og:title", "twitter:title")) or _title_text(soup)
    description = _first_meta(
        soup,
        ("og:description", "twitter:description", "description"),
    )
    text = soup.get_text("\n", strip=True)
    snippet_lines = _relevant_lines(text)
    snippet = "\n".join(snippet_lines[:22])
    company_guess, role_guess = _guess_company_role(title)

    return {
        "url": url,
        "title": title,
        "description": description,
        "snippet": snippet,
        "company_guess": company_guess,
        "role_guess": role_guess,
        "requirements": _requirement_lines(snippet_lines),
        "host": urlparse(url).netloc.lower().removeprefix("www."),
        "error": "",
    }


def _validate_public_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return "http 또는 https로 시작하는 지원공고 링크를 입력해 주세요."
    host = (parsed.hostname or "").lower()
    if host in BLOCKED_HOSTS:
        return "로컬 주소는 지원공고 링크로 사용할 수 없습니다."
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return "지원공고 링크의 도메인을 확인하지 못했습니다."
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local:
            return "내부망 주소는 지원공고 링크로 사용할 수 없습니다."
    return ""


def _first_meta(soup: BeautifulSoup, names: tuple[str, ...]) -> str:
    for name in names:
        tag = soup.find("meta", attrs={"property": name}) or soup.find("meta", attrs={"name": name})
        if tag and tag.get("content"):
            return _clean_text(str(tag["content"]))
    return ""


def _title_text(soup: BeautifulSoup) -> str:
    if soup.title and soup.title.string:
        return _clean_text(soup.title.string)
    h1 = soup.find("h1")
    return _clean_text(h1.get_text(" ", strip=True) if h1 else "")


def _relevant_lines(text: str) -> list[str]:
    lines = []
    seen = set()
    for raw in re.split(r"[\n\r]+", text or ""):
        line = _clean_text(raw)
        if not (8 <= len(line) <= 180):
            continue
        compact = re.sub(r"\s+", "", line.lower())
        if compact in seen:
            continue
        if any(hint in line for hint in JOB_HINTS):
            seen.add(compact)
            lines.append(line)
        if len(lines) >= 40:
            break
    return lines


def _requirement_lines(lines: list[str]) -> list[str]:
    tokens = ("자격", "우대", "역량", "경험", "전공", "기술", "능력", "담당")
    return [line for line in lines if any(token in line for token in tokens)][:8]


def _guess_company_role(title: str) -> tuple[str, str]:
    cleaned = _clean_text(title)
    if not cleaned:
        return "", ""
    cleaned = re.sub(r"\s*[-|]\s*(사람인|잡코리아|워크넷|고용24|원티드|인크루트).*$", "", cleaned)
    company = ""
    role = ""
    bracket = re.match(r"^\[(?P<company>[^\]]{2,50})\]\s*(?P<role>.+)$", cleaned)
    if bracket:
        company = bracket.group("company")
        role = bracket.group("role")
    else:
        parts = [p.strip() for p in re.split(r"\s*[-|:]\s*", cleaned) if p.strip()]
        if len(parts) >= 2:
            company = parts[0]
            role = parts[1]
        else:
            role = cleaned
    role = re.sub(r"\s*(채용|공고|모집)\s*$", "", role).strip(" -|")
    return company[:40], role[:60]


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()
