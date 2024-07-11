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
def log_article(category, title, url, date):
    c.execute("INSERT INTO articles VALUES (?, ?, ?, ?)", 
              (date, category, title, url))
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

# Determine the date range for the search (previous day)
def get_date_range():
    yesterday = datetime.now() - timedelta(days=1)
    start_date = datetime(yesterday.year, yesterday.month, yesterday.day)
    end_date = start_date + timedelta(days=1)
    return start_date, end_date

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

# Function to get the publication date of an article
def get_publication_date(soup):
    # This function should be customized based on the structure of each website
    # Example for a generic case:
    date_str = soup.find('time')  # Update this line based on the actual HTML structure
    if date_str:
        try:
            return datetime.strptime(date_str['datetime'], '%Y-%m-%dT%H:%M:%SZ')  # Adjust the format if needed
        except Exception as e:
            logging.warning(f"Could not parse date: {e}")
    return None

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
            if href not in processed_urls and not is_excluded_url(href) and any(keyword.lower() in title.lower() for keyword in keywords):
                if is_valid_url(href):
                    article_response = session.get(href, timeout=30)
                    article_soup = BeautifulSoup(article_response.content, 'lxml')
                    pub_date = get_publication_date(article_soup)
                    if pub_date and start_date <= pub_date < end_date:
                        articles.append({"title": title.strip(), "url": href, "date": pub_date.strftime('%Y-%m-%d')})
                        processed_urls.add(href)
                        logging.info(f"Found article: {title.strip()} - {href} - {pub_date}")
                        log_article(category, title.strip(), href, pub_date.strftime('%Y-%m-%d'))

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

    return categorized

# Collect articles
start_date, end_date = get_date_range()
all_articles = []
processed_urls = set()

for name, url in websites.items():
    if is_website_up(url):
        time.sleep(30)  # Wait for 30 seconds before processing each website
        articles = get_articles(url, sum(keywords.values(), []), processed_urls)
        all_articles.extend(articles)

# Categorize articles
categorized_articles = categorize_articles(all_articles)

# Build HTML email body with styles and images
email_body = """
<html>
<head>
<style>
    body {
        font-family: Arial, sans-serif; 
        line-height: 1.6;
    }
    h2 {
        color: #2E8B57;
    }
    ul {
        list-style-type: none; 
        padding: 0;
    }
    li {
        margin: 10px 0;
    }
    a {
        text-decoration: none; 
        color: #1E90FF;
    }
    a:hover {
        text-decoration: underline;
    }
    .category {
        margin-top: 20px;
    }
</style>
</head>
<body>
<h1>Daily Cybersecurity News</h1>
"""

for category, articles in categorized_articles.items():
    email_body += f"<div class='category'><h2>{category}</h2><ul>"
    for article in articles:
        email_body += f"<li><a href='{article['url']}'>{article['title']}</a> - {article['date']}</li>"
        email_body += "<hr>"
    email_body += "</ul></div>"

email_body += """
</body>
</html>
"""

# Check if email body is empty
if not any(categorized_articles.values()):
    email_body = """
    <html>
    <body>
    <p>Nothing new today. Thanks for checking in with us.</p>
    </body>
    </html>
    """

# Create email message
msg = MIMEMultipart()
msg['From'] = email_from
msg['To'] = ", ".join(email_to)
msg['Subject'] = email_subject
msg.attach(MIMEText(email_body, 'html'))

# Debug logs before sending the email
logging.info("Preparing to send email with the following content:")
logging.info(f"From: {email_from}")
logging.info(f"To: {email_to}")
logging.info(f"Subject: {email_subject}")
logging.info(f"Body: {email_body}")

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
