from flask import Flask, render_template, request
print("현재 실행 중인 app.py:", __file__)
from company_info import company_data
from interview_api import get_company_interviews
from jobs_api import get_company_jobs
from news_api import get_news
from search_api import search_career_content

app = Flask(__name__)

companies = list(company_data.keys())


@app.route('/')
def home():

    news = get_news("현대자동차 자동차 산업")

    return render_template(
        'index.html',
        companies=companies,
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
    return render_template('news.html', news=news_items)

@app.route('/search')
def search():
    query = request.args.get('q', '')
    results, api_source, message = search_career_content(query)

    return render_template(
        'search.html',
        query=query.strip(),
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

    return render_template(
        'company.html',
        name=name,
        company=company,
        news=news
    )

@app.route('/test')
def test():
    return "EUNJIN PROJECT"


app.run(debug=True)
