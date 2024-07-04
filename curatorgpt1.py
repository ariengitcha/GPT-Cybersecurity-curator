
import asyncio
import aiohttp
from bs4 import BeautifulSoup
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timedelta
import os
import logging
import sqlite3
from urllib.parse import urljoin
import aiodns
import chardet
from aiohttp_retry import RetryClient, ExponentialRetry

# Setup logging
logging.basicConfig(filename='curatorgpt.log', level=logging.INFO, 
                    format='%(asctime)s %(levelname)s:%(message)s')

# Email configuration
email_from = os.getenv('EMAIL_ADDRESS_GPT')
email_password = os.getenv('EMAIL_PASSWORD_GPT')
email_to = ["ariennation@gmail.com", "arien.seghetti@ironbow.com"]
email_subject = f"Daily Cybersecurity News - {datetime.now().strftime('%Y-%m-%d')}"

# Define websites and categories
websites = {
    "Dark Reading": "https://www.darkreading.com/",
    "The Hacker News": "https://thehackernews.com/",
    "CSO Online": "https://www.csoonline.com/",
    "Krebs on Security": "https://krebsonsecurity.com/"
}

keywords = {
    "Breach": ["breach", "data breach"],
    "Vulnerability": ["vulnerability", "exploit"],
    "Compliance": ["compliance", "regulation"],
    "Startup": "startup, funding",
    "AI": ["AI", "artificial intelligence"]
}

category_images = {
    "Breach": "https://example.com/breach_image.jpg",
    "Vulnerability": "https://example.com/vulnerability_image.jpg",
    "Compliance": "https://example.com/compliance_image.jpg",
    "Startup": "https://example.com/startup_image.jpg",
    "AI": "https://example.com/ai_image.jpg"
}

# Database operations
def get_db_connection():
    return sqlite3.connect('articles.db')

def init_db():
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS articles
                     (date text, category text, title text, url text UNIQUE)''')
        conn.commit()

def log_article(category, title, url):
    with get_db_connection() as conn:
        c = conn.cursor()
        try:
            c.execute("INSERT OR IGNORE INTO articles VALUES (?, ?, ?, ?)", 
                      (datetime.now().strftime('%Y-%m-%d'), category, title, url))
            conn.commit()
        except sqlite3.IntegrityError:
            logging.info(f"Article already exists in database: {title}")

# Determine the date range for the search
def get_date_range():
    today = datetime.now()
    if today.weekday() == 0:  # Monday
        start_date = today - timedelta(days=3)  # From Friday
    else:
        start_date = today - timedelta(days=1)  # Past 24 hours
    return start_date, today

# Asynchronous functions for fetching and processing articles
async def fetch_url(session, url):
    try:
        async with session.get(url) as response:
            return await response.text()
    except Exception as e:
        logging.error(f"Failed to fetch {url}: {e}")
        return None

async def process_article(session, base_url, link, keywords, start_date):
    href = urljoin(base_url, link['href'])
    title = link.get_text().strip()

    if any(keyword.lower() in title.lower() for keyword in keywords):
        html = await fetch_url(session, href)
        if html:
            soup = BeautifulSoup(html, 'lxml')
            pub_date = get_publication_date(soup)
            
            if pub_date and pub_date >= start_date:
                summary = await summarize_article(session, href)
                return {"title": title, "url": href, "summary": summary}
    return None

async def get_articles(session, base_url, keywords, start_date):
    logging.info(f"Accessing URL: {base_url}")
    html = await fetch_url(session, base_url)
    if not html:
        return []

    soup = BeautifulSoup(html, 'lxml')
    tasks = []
    for link in soup.find_all('a', href=True):
        task = process_article(session, base_url, link, keywords, start_date)
        tasks.append(task)

    results = await asyncio.gather(*tasks)
    return [r for r in results if r]

# Function to get the publication date from an article
def get_publication_date(soup):
    date = None
    date_tags = soup.find_all(['time', 'span', 'p'], class_=['date', 'time', 'published'])
    for tag in date_tags:
        date_str = tag.get('datetime') or tag.get_text()
        try:
            date = datetime.strptime(date_str, '%Y-%m-%dT%H:%M:%S%z')
            break
        except ValueError:
            continue
    return date

# Function to summarize an article (placeholder - replace with actual API call)
async def summarize_article(session, url):
    # Simulate API call
    await asyncio.sleep(1)
    return f"Summary of {url}"

# Function to categorize articles
def categorize_articles(articles):
    categorized = {key: [] for key in keywords.keys()}
    
    for article in articles:
        for category, kw_list in keywords.items():
            if any(kw.lower() in article['title'].lower() for kw in kw_list):
                categorized[category].append(article)
                log_article(category, article['title'], article['url'])
                break  # Assign to first matching category

    return categorized

# Build HTML email body
def build_email_body(categorized_articles):
    email_body = """
    <html>
    <head>
    <style>
        body {font-family: Arial, sans-serif; line-height: 1.6;}
        h2 {color: #2E8B57;}
        ul {list-style-type: none; padding: 0;}
        li {margin: 10px 0;}
        a {text-decoration: none; color: #1E90FF;}
        a:hover {text-decoration: underline;}
        .summary {font-size: 0.9em; color: #555;}
        .category {margin-top: 20px;}
        .category img {width: 100px; height: auto; float: left; margin-right: 20px;}
    </style>
    </head>
    <body>
    <h1>Daily Cybersecurity News</h1>
    """

    for category, articles in categorized_articles.items():
        email_body += f"<div class='category'><img src='{category_images.get(category, '')}' alt='{category} Image'><h2>{category}</h2><ul>"
        for article in articles:
            email_body += f"<li><a href='{article['url']}'>{article['title']}</a><div class='summary'>{article['summary']}</div></li>"
        email_body += "</ul></div>"

    email_body += """
    </body>
    </html>
    """

    return email_body if any(categorized_articles.values()) else "<p>No new articles today. Thanks for checking in with us.</p>"

# Send email
def send_email(email_body):
    msg = MIMEMultipart()
    msg['From'] = email_from
    msg['To'] = ", ".join(email_to)
    msg['Subject'] = email_subject
    msg.attach(MIMEText(email_body, 'html'))

    try:
        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            server.login(email_from, email_password)
            server.sendmail(email_from, email_to, msg.as_string())
        logging.info("Email sent successfully")
    except Exception as e:
        logging.error(f"Failed to send email: {e}")

# Main asynchronous function
async def main():
    init_db()
    start_date, end_date = get_date_range()
    all_articles = []

    retry_options = ExponentialRetry(attempts=5)
    async with RetryClient(retry_options=retry_options) as session:
        tasks = []
        for name, url in websites.items():
            task = get_articles(session, url, sum(keywords.values(), []), start_date)
            tasks.append(task)

        results = await asyncio.gather(*tasks)
        for articles in results:
            all_articles.extend(articles)

    categorized_articles = categorize_articles(all_articles)
    email_body = build_email_body(categorized_articles)
    send_email(email_body)

# Run the main function
if __name__ == "__main__":
    asyncio.run(main())
```

