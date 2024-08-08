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

# Function to get article summary
def get_article_summary(url):
    try:
        response = session.get(url, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'lxml')
        
        # Try to find the article body
        article_body = soup.find('article') or soup.find('div', class_='article-body')
        if article_body:
            paragraphs = article_body.find_all('p')
            summary = " ".join([p.get_text().strip() for p in paragraphs[:2]])  # First two paragraphs
            return summary[:200] + "..." if len(summary) > 200 else summary
        else:
            return "Summary not available."
    except Exception as e:
        logging.error(f"Failed to get summary for {url}: {e}")
        return "Failed to retrieve summary."

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
            title = link.get_text().strip()

            href = urljoin(base_url, href)
            if should_process_url(href, processed_urls) and any(keyword.lower() in title.lower() for keyword in keywords):
                if is_valid_url(href):
                    summary = get_article_summary(href)
                    articles.append({"title": title, "summary": summary, "url": href})
                    processed_urls.add(href)
                    logging.info(f"Found article: {title} - {summary}")
                    time.sleep(1)  # Rate limiting

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

# Function to fetch cybersecurity regulation updates
def get_regulation_updates():
    url = "https://www.nist.gov/cyberframework/getting-started/news"
    updates = []
    try:
        response = requests.get(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'lxml')
        news_items = soup.find_all('div', class_='views-row')
        for item in news_items[:5]:  # Get the first 5 news items
            title = item.find('h3').get_text().strip()
            link = urljoin(url, item.find('a')['href'])
            updates.append({"title": title, "url": link})
        return updates
    except Exception as e:
        logging.error(f"Failed to fetch regulation updates: {e}")
        return [{"title": "Failed to fetch updates", "url": "#"}]

# Function to get geopolitical updates
def get_geopolitical_updates():
    api_key = os.getenv('NEWS_API_KEY')  # You need to set this in your GitHub secrets
    url = f"https://newsapi.org/v2/top-headlines?country=us&category=technology&apiKey={api_key}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        return [{"title": article['title'], "summary": article['description']} for article in data['articles'][:5]]
    except Exception as e:
        logging.error(f"Failed to fetch geopolitical updates: {e}")
        return [{"title": "Failed to fetch updates", "summary": "Please check back later."}]

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
        if articles:  # Only add the category if there are articles
            email_body += f"<div class='category'><h2>{category}</h2><ul>"
            for article in articles:
                email_body += f"<li><a href='{article['url']}'>{article['title']}</a><div class='summary'>{article['summary']}</div></li>"
                email_body += "<div class='article-separator'></div>"
            email_body += "</ul></div>"

    # Add New CVEs
    if new_cves:
        email_body += "<h2>New Critical Vulnerabilities</h2><ul>"
        for cve in new_cves:
            cve_id = cve['cve']['CVE_data_meta']['ID']
            description = cve['cve']['description']['description_data'][0]['value']
            email_body += f"<li><strong>{cve_id}</strong>: {description[:200]}...</li>"
        email_body += "</ul>"
    else:
        email_body += "<h2>New Critical Vulnerabilities</h2><p>No new critical vulnerabilities reported today.</p>"

    # Add Regulation Updates
    if regulation_updates:
        email_body += "<h2>Regulatory and Compliance Updates</h2><ul>"
        for update in regulation_updates:
            email_body += f"<li><a href='{update['url']}'>{update['title']}</a></li>"
        email_body += "</ul>"
    else:
        email_body += "<h2>Regulatory and Compliance Updates</h2><p>No new regulatory updates available today.</p>"

    # Add Geopolitical Updates
    if geopolitical_updates:
        email_body += "<h2>Geopolitical Context</h2><ul>"
        for update in geopolitical_updates:
            email_body += f"<li><strong>{update['title']}</strong><br>{update['summary']}</li>"
        email_body += "</ul>"
    else:
        email_body += "<h2>Geopolitical Context</h2><p>No significant geopolitical updates related to cybersecurity today.</p>"

    email_body += """
    </div>
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
