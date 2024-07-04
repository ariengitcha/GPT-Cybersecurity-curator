import requests
from bs4 import BeautifulSoup
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timedelta
import os
import time
import logging
import sqlite3
from urllib.parse import urljoin
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

# Setup logging
logging.basicConfig(filename='curatorgpt.log', level=logging.INFO, 
                    format='%(asctime)s %(levelname)s:%(message)s')

# Email configuration
email_from = os.getenv('EMAIL_ADDRESS_GPT')
email_password = os.getenv('EMAIL_PASSWORD_GPT')
email_to = ["ariennation@gmail.com", "arien.seghetti@ironbow.com"]
email_subject = f"Daily Cybersecurity News - {datetime.now().strftime('%Y-%m-%d')}"
email_body = ""

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
    "Startup": ["startup", "funding"],
    "AI": ["AI", "artificial intelligence"]
}

# Example images for categories
category_images = {
    "Breach": "https://example.com/breach_image.jpg",
    "Vulnerability": "https://example.com/vulnerability_image.jpg",
    "Compliance": "https://example.com/compliance_image.jpg",
    "Startup": "https://example.com/startup_image.jpg",
    "AI": "https://example.com/ai_image.jpg"
}

# Create or connect to a SQLite database
conn = sqlite3.connect('articles.db')
c = conn.cursor()

# Create table
c.execute('''CREATE TABLE IF NOT EXISTS articles
             (date text, category text, title text, url text)''')

# Insert a row of data
def log_article(category, title, url):
    c.execute("INSERT INTO articles VALUES (?, ?, ?, ?)", 
              (datetime.now().strftime('%Y-%m-%d'), category, title, url))
    conn.commit()

# Get a requests session with retries
def get_session():
    session = requests.Session()
    retry = Retry(
        total=5,
        backoff_factor=1,
        status_forcelist=[500, 502, 503, 504]
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session

session = get_session()

# Determine the date range for the search
def get_date_range():
    today = datetime.now()
    if today.weekday() == 0:  # Monday
        start_date = today - timedelta(days=3)  # From Friday
    else:
        start_date = today - timedelta(days=1)  # Past 24 hours
    return start_date, today

# Function to check if a website is up and running
def is_website_up(url):
    try:
        response = requests.head(url, timeout=30)
        if response.status_code == 200:
            logging.info(f"Website {url} is up and running.")
            return True
        else:
            logging.warning(f"Website {url} returned status code: {response.status_code}")
            return False
    except requests.RequestException as e:
        logging.error(f"Website {url} is not reachable. Error: {e}")
        return False

# Function to check if a URL returns a 404 error
def is_valid_url(url):
    try:
        response = session.head(url, timeout=30)
        if response.status_code == 404:
            logging.warning(f"URL {url} returned a 404 error.")
            return False
        return True
    except requests.RequestException as e:
        logging.error(f"Failed to check URL {url}: {e}")
        return False

# Example function to summarize an article
def summarize_article(url):
    # Simulate a summarization process (replace with actual API call if available)
    return f"Summary of {url}"

# Function to get the publication date from an article
def get_publication_date(soup):
    date = None
    # Example for generic date patterns, may need adjustment for specific websites
    date_tag = soup.find('time')
    if date_tag:
        try:
            date = datetime.strptime(date_tag['datetime'], '%Y-%m-%dT%H:%M:%SZ')
        except Exception:
            date = None
    return date

# Function to get articles from a website
def get_articles(base_url, keywords, processed_urls, start_date):
    logging.info(f"Accessing URL: {base_url}")
    try:
        response = session.get(base_url, timeout=30)
        response.raise_for_status()  # Raise an exception for HTTP errors
        soup = BeautifulSoup(response.content, 'lxml')

        articles = []
        for link in soup.find_all('a', href=True):
            href = link['href']
            title = link.get_text()

            # Ensure the URL is absolute using urljoin
            href = urljoin(base_url, href)
            if href not in processed_urls and any(keyword.lower() in title.lower() for keyword in keywords):
                if is_valid_url(href):
                    article_response = session.get(href, timeout=30)
                    article_response.raise_for_status()
                    article_soup = BeautifulSoup(article_response.content, 'lxml')
                    pub_date = get_publication_date(article_soup)
                    
                    if pub_date and pub_date >= start_date:
                        summary = summarize_article(href)
                        articles.append({"title": title.strip(), "url": href, "summary": summary})
                        processed_urls.add(href)
                        logging.info(f"Found article: {title.strip()} - {href} - {summary}")

        return articles
    except Exception as e:
        logging.error(f"Failed to fetch articles from {base_url}: {e}")
        return []

# Function to categorize articles
def categorize_articles(articles):
    categorized = {key: [] for key in keywords.keys()}
    
    for article in articles:
        for category, kw_list in keywords.items():
            if any(kw.lower() in article['title'].lower() for kw in kw_list):
                categorized[category].append(article)
                log_article(category, article['title'], article['url'])

    return categorized

# Collect articles
start_date, end_date = get_date_range()
all_articles = []
processed_urls = set()

for name, url in websites.items():
    if is_website_up(url):
        time.sleep(30)  # Wait for 30 seconds before processing each website
        articles = get_articles(url, sum(keywords.values(), []), processed_urls, start_date)
        all_articles.extend(articles)

# Categorize articles
categorized_articles = categorize_articles(all_articles)

# Build HTML email body with styles and images
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

# Check if email body is empty
if not email_body.strip():
    email_body = """
    <html>
    <body>
    <p>Nothing New today. Thanks for checking in with us.</p>
    </body>
    </html>
    """

# Create email message
msg = MIMEMultipart()
msg['From'] = email_from
msg['To'] = ", ".join(email_to)
msg['Subject'] = email_subject
msg.attach(MIMEText(email_body, 'html'))

# Send email
try:
    server = smtplib.SMTP('smtp.gmail.com', 587)
    server.starttls()
    server.login(email_from, email_password)
    text = msg.as_string()
    server.sendmail(email_from, email_to, text)
    server.quit()
    logging.info("Email sent successfully")
except Exception as e:
    logging.error(f"Failed to send email: {e}")

# Close the database connection
conn.close()
