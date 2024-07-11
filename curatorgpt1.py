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

# Debugging prints
print(f"EMAIL_ADDRESS_GPT: {email_from}")
print(f"EMAIL_PASSWORD_GPT: {email_password}")

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

# URLs to exclude
excluded_urls = [
    "https://krebsonsecurity.com/category/",
    "https://krebsonsecurity.com/category/*",
    "*/author/*",
    "https://www.csoonline.com/compliance/",
    "https://www.csoonline.com/compliance/*",
    "https://www.darkreading.com/program/*",
    "https://thehackernews.com/#email-outer",
    "https://www.csoonline.com/artificial-intelligence/",
    "https://www.csoonline.com/generative-ai/"
]

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

# Function to check if a URL should be excluded
def is_excluded_url(url):
    for excluded in excluded_urls:
        if '*' in excluded:
            excluded_pattern = excluded.replace('*', '')
            if excluded_pattern in url:
                return True
        elif url.startswith(excluded):
            return True
    return False

# Function to get articles from a website
def get_articles(base_url, keywords, processed_urls):
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
            if href not in processed_urls and not is_excluded_url(href) and
