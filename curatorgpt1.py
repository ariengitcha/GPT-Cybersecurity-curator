import requests
from bs4 import BeautifulSoup
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timedelta
import os
import logging
import sqlite3
from urllib.parse import urljoin, urlparse
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
import concurrent.futures

# Setup logging
logging.basicConfig(filename='curatorgpt.log', level=logging.INFO, 
                    format='%(asctime)s %(levelname)s:%(message)s')

# Email configuration from environment variables
email_from = os.getenv('EMAIL_ADDRESS_GPT')
email_password = os.getenv('EMAIL_PASSWORD_GPT')
email_to = os.getenv('EMAIL_RECIPIENTS', 'ariennation@gmail.com, arien.seghetti@ironbow.com').split(', ')
email_subject = f"Daily Cybersecurity News and Threat Intelligence - {datetime.now().strftime('%Y-%m-%d')}"

# Define websites and categories in a config file or environment variables
websites = {
    "Dark Reading": "https://www.darkreading.com/",
    "The Hacker News": "https://thehackernews.com/",
    "CSO Online": "https://www.csoonline.com/",
    "Krebs on Security": "https://krebsonsecurity.com/"
}

keywords = {
    "Breach": ["breach", "data breach"],
    "Vulnerability": ["vulnerability", "exploit", "CVE"],
    "Compliance": ["compliance", "regulation", "GDPR", "CCPA", "NIST"],
    "Startup": ["startup", "funding"],
    "AI": ["AI", "artificial intelligence", "machine learning"],
    "Threat Intel": ["APT", "campaign", "malware", "ransomware"],
    "Phishing": ["phishing", "social engineering", "spam"],
}

# Create or connect to a SQLite database
conn = sqlite3.connect('articles.db')
c = conn.cursor()

# Create table
c.execute('''
    CREATE TABLE IF NOT EXISTS articles
    (date text, category text, title text, url text UNIQUE)
''')

# Insert a row of data
def log_article(category, title, url):
    try:
        c.execute("INSERT INTO articles VALUES (?, ?, ?, ?)", 
                  (datetime.now().strftime('%Y-%m-%d'), category, title, url))
        conn.commit()
    except sqlite3.IntegrityError:
        logging.info(f"Article already exists in database: {title}")

# Function to fetch and parse articles
def fetch_articles(url, keywords):
    articles = []
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')

        for link in soup.find_all('a', href=True):
            href = link['href']
            if not urlparse(href).netloc:
                href = urljoin(url, href)
            for category, terms in keywords.items():
                if any(term in link.text.lower() for term in terms):
                    articles.append((category, link.text.strip(), href))
    except Exception as e:
        logging.error(f"Failed to fetch articles from {url}: {e}")
    return articles

# Function to send an email
def send_email(body):
    msg = MIMEMultipart()
    msg['From'] = email_from
    msg['To'] = ", ".join(email_to)
    msg['Subject'] = email_subject
    msg.attach(MIMEText(body, 'html'))

    try:
        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            server.login(email_from, email_password)
            server.sendmail(email_from, email_to, msg.as_string())
        logging.info("Email sent successfully")
    except Exception as e:
        logging.error(f"Failed to send email: {e}")

# Main function
def main():
    email_body = "<html><body><h1>Daily Cybersecurity News</h1><div>"

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        future_to_url = {executor.submit(fetch_articles, url, keywords): url for url in websites.values()}
        for future in concurrent.futures.as_completed(future_to_url):
            url = future_to_url[future]
            try:
                articles = future.result()
                for category, title, href in articles:
                    log_article(category, title, href)
                    email_body += f"<p><strong>{category}:</strong> <a href='{href}'>{title}</a></p>"
            except Exception as e:
                logging.error(f"Error occurred for {url}: {e}")

    email_body += "</div></body></html>"

    send_email(email_body)

    conn.close()

if __name__ == "__main__":
    main()
