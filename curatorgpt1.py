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
from urllib.parse import urljoin, urlparse
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
import concurrent.futures

# Setup logging
logging.basicConfig(filename='curatorgpt.log', level=logging.INFO, 
                    format='%(asctime)s %(levelname)s:%(message)s')

# Email configuration
email_from = os.getenv('EMAIL_ADDRESS_GPT')
email_password = os.getenv('EMAIL_PASSWORD_GPT')
email_to = ["ariennation@gmail.com", "arien.seghetti@ironbow.com"]
email_subject = f"Daily Cybersecurity News and Threat Intelligence - {datetime.now().strftime('%Y-%m-%d')}"

# Define websites and categories
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
c.execute('''CREATE TABLE IF NOT EXISTS articles
             (date text, category text, title text, url text UNIQUE)''')

# Insert a row of data
def log_article(category, title, url):
    try:
        c.execute("INSERT INTO articles VALUES (?, ?, ?, ?)", 
                  (datetime.now().strftime('%Y-%m-%d'), category, title, url))
        conn.commit()
    except sqlite3.IntegrityError:
        logging.info(f"Article already exists in database: {title}")

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

# Function to check if a URL should be processed
def should_process_url(url, processed_urls):
    parsed_url = urlparse(url)
    path = parsed_url.path

    if url in processed_urls:
        return False
    if '/author/' in path:
        return False
    if any(keyword in path for keyword in ['category', 'topics', 'section']):
        return False

    return True

# Function to check if a URL is valid
def is_valid_url(url):
    try:
        response = session.head(url, timeout=30)
        return 200 <= response.status_code < 400
    except requests.RequestException as e:
        logging.error(f"Failed to check URL {url}: {e}")
        return False

# Function to summarize an article (placeholder)
def summarize_article(url):
    return f"Summary of article from {url}"

# Function to get articles from a website
def get_articles(base_url, keywords, processed_urls):
    logging.info(f"Accessing URL: {base_url}")
    articles = []
    try:
        response = session.get(base_url, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'lxml')

        for link in soup.find_all('a', href=True):
            href = link['href']
            title = link.get_text()

            href = urljoin(base_url, href)
            if should_process_url(href, processed_urls) and any(keyword.lower() in title.lower() for keyword in keywords):
                if is_valid_url(href):
                    summary = summarize_article(href)
                    articles.append({"title": title.strip(), "summary": summary, "url": href})
                    processed_urls.add(href)
                    logging.info(f"Found article: {title.strip()} - {summary}")
                    time.sleep(1)  # Rate limiting for requests to the same website

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
                break  # Assign to first matching category

    return categorized

# Collect articles using multi-threading
def collect_articles(websites, keywords):
    all_articles = []
    processed_urls = set()

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        future_to_url = {executor.submit(get_articles, url, sum(keywords.values(), []), processed_urls): name 
                         for name, url in websites.items() if is_website_up(url)}
        for future in concurrent.futures.as_completed(future_to_url):
            name = future_to_url[future]
            try:
                articles = future.result()
                all_articles.extend(articles)
            except Exception as exc:
                logging.error(f'{name} generated an exception: {exc}')

    return all_articles

# Function to fetch new CVEs from NVD
def get_new_cves():
    two_days_ago = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%S:000 UTC-00:00")
    url = f"https://services.nvd.nist.gov/rest/json/cves/1.0?pubStartDate={two_days_ago}&resultsPerPage=5"
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        return data['result']['CVE_Items']
    except Exception as e:
        logging.error(f"Failed to fetch new CVEs: {e}")
        return []

# Function to fetch cybersecurity regulation updates (placeholder)
def get_regulation_updates():
    return [
        {"title": "GDPR: New guidelines on AI and data protection", "url": "https://example.com/gdpr-ai"},
        {"title": "CCPA: Proposed modifications to regulations", "url": "https://example.com/ccpa-mods"}
    ]

# Function to get geopolitical updates (placeholder)
def get_geopolitical_updates():
    return [
        {"title": "Tensions rise in cyberspace between nations A and B", "summary": "Increased cyber activities observed..."},
        {"title": "New international cybersecurity coalition formed", "summary": "Five countries join forces to..."}
    ]

# Main execution function
def main():
    all_articles = collect_articles(websites, keywords)
    categorized_articles = categorize_articles(all_articles)
    
    new_cves = get_new_cves()
    regulation_updates = get_regulation_updates()
    geopolitical_updates = get_geopolitical_updates()

    # Build HTML email body with styles
    email_body = """
    <html>
    <head>
    <style>
        body {
            font-family: Arial, sans-serif; 
            line-height: 1.6;
            background-color: #f4f4f4;
            color: #333;
        }
        .container {
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            background-color: #fff;
            border-radius: 5px;
            box-shadow: 0 0 10px rgba(0,0,0,0.1);
        }
        h1, h2 {
            color: #2E8B57;
        }
        ul {
            list-style-type: none; 
            padding: 0;
        }
        li {
            margin: 10px 0;
            padding: 10px;
            background-color: #f9f9f9;
            border-radius: 5px;
        }
        .summary {
            font-size: 0.9em; 
            color: #555;
        }
        .category {
            margin-top: 20px;
        }
        .article-separator {
            border-top: 1px solid #ddd; 
            margin: 10px 0;
        }
    </style>
    </head>
    <body>
    <div class="container">
    <h1>Daily Cybersecurity News and Threat Intelligence</h1>
    """

    # Add categorized articles
    for category, articles in categorized_articles.items():
        email_body += f"<div class='category'><h2>{category}</h2><ul>"
        for article in articles:
            email_body += f"<li><a href='{article['url']}'>{article['title']}</a><div class='summary'>{article['summary']}</div></li>"
            email_body += "<div class='article-separator'></div>"
        email_body += "</ul></div>"

    # Add New CVEs
    email_body += "<h2>New Critical Vulnerabilities</h2><ul>"
    for cve in new_cves:
        email_body += f"<li><strong>{cve['cve']['CVE_data_meta']['ID']}</strong>: {cve['cve']['description']['description_data'][0]['value'][:200]}...</li>"
    email_body += "</ul>"

    # Add Regulation Updates
    email_body += "<h2>Regulatory and Compliance Updates</h2><ul>"
    for update in regulation_updates:
        email_body += f"<li><a href='{update['url']}'>{update['title']}</a></li>"
    email_body += "</ul>"

    # Add Geopolitical Updates
    email_body += "<h2>Geopolitical Context</h2><ul>"
    for update in geopolitical_updates:
        email_body += f"<li><strong>{update['title']}</strong><br>{update['summary']}</li>"
    email_body += "</ul>"

    email_body += """
    </div>
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

if __name__ == "__main__":
    main()
