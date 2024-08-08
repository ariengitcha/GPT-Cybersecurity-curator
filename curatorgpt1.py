import aiohttp
import asyncio
from bs4 import BeautifulSoup
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
import os
import logging
import json
from urllib.parse import urljoin
import smtplib
import re

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s:%(message)s')

# Configuration
EMAIL_FROM = os.environ.get('EMAIL_ADDRESS_GPT')
EMAIL_PASSWORD = os.environ.get('EMAIL_PASSWORD_GPT')
EMAIL_TO = json.loads(os.environ.get('EMAIL_TO', '[]'))
EMAIL_SUBJECT = f"Cybersecurity News - {datetime.now().strftime('%Y-%m-%d')}"

WEBSITES = {
    "Dark Reading": "https://www.darkreading.com/",
    "The Hacker News": "https://thehackernews.com/",
    "CSO Online": "https://www.csoonline.com/",
    "Krebs on Security": "https://krebsonsecurity.com/"
}

KEYWORDS = {
    "Breach": ["breach", "data breach", "leaked", "exposed"],
    "Vulnerability": ["vulnerability", "exploit", "flaw", "zero-day"],
    "Compliance": ["compliance", "regulation", "GDPR", "CCPA"],
    "Startup": ["startup", "funding", "venture capital", "series A"],
    "AI": ["AI", "artificial intelligence", "machine learning", "deep learning"]
}

async def fetch(session, url):
    async with session.get(url) as response:
        if response.status == 200:
            return await response.text()
        else:
            logging.error(f"Failed to fetch {url}: HTTP {response.status}")
            return None

async def get_articles(session, base_url, keywords):
    html = await fetch(session, base_url)
    if not html:
        return []

    soup = BeautifulSoup(html, 'html.parser')
    articles = []
    for link in soup.find_all('a', href=True):
        title = link.get_text().strip()
        if any(kw.lower() in title.lower() for kw in keywords):
            url = urljoin(base_url, link['href'])
            articles.append({"title": title, "url": url})
    return articles

async def categorize_article(article):
    for category, kw_list in KEYWORDS.items():
        if any(re.search(r'\b' + re.escape(kw.lower()) + r'\b', article['title'].lower()) for kw in kw_list):
            return category, article
    return None, None

async def process_websites():
    async with aiohttp.ClientSession() as session:
        tasks = [get_articles(session, url, sum(KEYWORDS.values(), [])) for url in WEBSITES.values()]
        all_articles = await asyncio.gather(*tasks)
        return [article for site_articles in all_articles for article in site_articles]

async def categorize_articles(articles):
    categorized = {category: [] for category in KEYWORDS.keys()}
    tasks = [categorize_article(article) for article in articles]
    results = await asyncio.gather(*tasks)
    for category, article in results:
        if category:
            categorized[category].append(article)
    return categorized

def generate_email_body(categorized_articles):
    email_body = """
    <html>
    <head>
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
        h1 { color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px; }
        h2 { color: #2980b9; margin-top: 20px; }
        ul { list-style-type: none; padding: 0; }
        li { margin: 10px 0; background-color: #f2f2f2; padding: 10px; border-radius: 5px; }
        a { color: #3498db; text-decoration: none; }
        a:hover { text-decoration: underline; }
        .category { margin-top: 30px; }
        .article-separator { border-top: 1px solid #bdc3c7; margin: 15px 0; }
    </style>
    </head>
    <body>
    <h1>Daily Cybersecurity News Roundup</h1>
    """

    for category, articles in categorized_articles.items():
        if articles:
            email_body += f"<div class='category'><h2>{category}</h2><ul>"
            for article in articles:
                email_body += f"""
                <li>
                    <a href="{article['url']}">{article['title']}</a>
                </li>
                <div class='article-separator'></div>
                """
            email_body += "</ul></div>"

    email_body += "</body></html>"
    return email_body

def send_email(body):
    msg = MIMEMultipart()
    msg['From'] = EMAIL_FROM
    msg['To'] = ", ".join(EMAIL_TO)
    msg['Subject'] = EMAIL_SUBJECT
    msg.attach(MIMEText(body, 'html'))

    try:
        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            server.login(EMAIL_FROM, EMAIL_PASSWORD)
            server.send_message(msg)
        logging.info("Email sent successfully")
    except Exception as e:
        logging.error(f"Failed to send email: {str(e)}")

async def main():
    articles = await process_websites()
    categorized_articles = await categorize_articles(articles)
    email_body = generate_email_body(categorized_articles)
    send_email(email_body)

def lambda_handler(event, context):
    asyncio.run(main())
    return {
        'statusCode': 200,
        'body': json.dumps('Cybersecurity news process completed successfully!')
    }

if __name__ == "__main__":
    asyncio.run(main())

# GitHub Actions workflow (save as .github/workflows/cybersecurity_news.yml)
"""
name: Daily Cybersecurity News

on:
  schedule:
    - cron: '0 8 * * *'  # Runs at 8:00 AM UTC daily
  workflow_dispatch:  # Allows manual trigger

jobs:
  send-news:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v2
    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: '3.8'
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install aiohttp beautifulsoup4
    - name: Run script
      env:
        EMAIL_ADDRESS_GPT: ${{ secrets.EMAIL_ADDRESS_GPT }}
        EMAIL_PASSWORD_GPT: ${{ secrets.EMAIL_PASSWORD_GPT }}
        EMAIL_TO: ${{ secrets.EMAIL_TO }}
      run: python cybersecurity_news_script.py
"""

# Requirements (save as requirements.txt)
"""
aiohttp==3.7.4
beautifulsoup4==4.9.3
"""
