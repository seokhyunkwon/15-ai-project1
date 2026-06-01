from flask import Flask, render_template, request
print("현재 실행 중인 app.py:", __file__)
from company_info import company_data
from interview_api import get_company_interviews
from jobs_api import get_company_jobs
from news_api import get_news
from search_api import search_career_content
from free_summarizer import summarize_news_item
from company_profile import build_company_profile

app = Flask(__name__)

companies = list(company_data.keys())
job_options = [
    "경영·사무",
    "인사·노무·HRD",
    "재무·회계",
    "영업·판매·무역",
    "구매·자재·물류",
    "마케팅·홍보",
    "생산관리",
    "생산기술",
    "품질관리",
    "설비·보전",
    "연구개발",
    "기계·설계",
    "전기·전자·전장",
    "SW·IT",
    "데이터·AI",
    "안전·환경",
]
region_options = [
    "서울",
    "경기",
    "인천",
    "판교",
    "평택",
    "원주",
    "익산",
    "대구",
    "경산",
    "울산",
    "부산",
    "광주",
    "충청",
    "전라",
    "경상",
    "해외",
]
career_options = [
    "신입",
    "경력",
    "인턴",
    "계약직",
    "산학장학생",
    "전문연구요원",
]


def add_free_summaries(news_items):
    for item in news_items:
        item["free_summary"] = summarize_news_item(
            item["title"],
            item["description"]
        )
    return news_items


@app.route('/')
def home():

    news = get_news("현대자동차 자동차 산업")
    add_free_summaries(news)

    return render_template(
        'index.html',
        companies=companies,
        job_options=job_options,
        region_options=region_options,
        career_options=career_options,
        news=news
    )

@app.route('/jobs')
def jobs():
    selected_company = request.args.get('company', companies[0])

    if selected_company not in company_data:
        selected_company = companies[0]

    job_posts, api_source = get_company_jobs(selected_company)

    return render_template(
        'jobs.html',
        companies=companies,
        selected_company=selected_company,
        selected_info=company_data[selected_company],
        job_posts=job_posts,
        api_source=api_source
    )

@app.route('/news')
def news():
    news_items = get_news("현대자동차 자동차 산업 채용")
    add_free_summaries(news_items)
    return render_template('news.html', news=news_items)

@app.route('/search')
def search():
    query = request.args.get('q', '')
    selected_companies = request.args.getlist('company')
    selected_jobs = request.args.getlist('job')
    selected_regions = request.args.getlist('region')
    selected_careers = request.args.getlist('career')
    results, api_source, message = search_career_content(
        query,
        selected_companies,
        selected_jobs,
        selected_regions,
        selected_careers
    )

    return render_template(
        'search.html',
        query=query.strip(),
        companies=companies,
        job_options=job_options,
        region_options=region_options,
        career_options=career_options,
        selected_companies=selected_companies,
        selected_jobs=selected_jobs,
        selected_regions=selected_regions,
        selected_careers=selected_careers,
        results=results,
        api_source=api_source,
        message=message
    )

@app.route('/interview')
def interview():
    selected_company = request.args.get('company', companies[0])

    if selected_company not in company_data:
        selected_company = companies[0]

    interview_posts, api_source = get_company_interviews(selected_company)

    return render_template(
        'interview.html',
        companies=companies,
        selected_company=selected_company,
        selected_info=company_data[selected_company],
        interview_posts=interview_posts,
        api_source=api_source
    )

@app.route('/briefing')
def briefing():
    return render_template('briefing.html')

@app.route('/companies')
def company_info_page():
    return render_template('companies.html', companies=companies, company_data=company_data)

@app.route('/company/<name>')
def company_page(name):

    company = company_data[name]

    news = get_news(company['search_keyword'])
    add_free_summaries(news)

    return render_template(
        'company.html',
        name=name,
        company=company,
        profile=build_company_profile(name, company),
        news=news
    )

@app.route('/test')
def test():
    return "EUNJIN PROJECT"


app.run(debug=True)
