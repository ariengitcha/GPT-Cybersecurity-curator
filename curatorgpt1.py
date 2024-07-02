import requests
from bs4 import BeautifulSoup
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timedelta
import os
import time

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
            print(f"Website {url} is up and running.")
            return True
        else:
            print(f"Website {url} returned status code: {response.status_code}")
            return False
    except requests.RequestException as e:
        print(f"Website {url} is not reachable. Error: {e}")
        return False

# Function to get articles from a website
def get_articles(url, keywords, start_date, end_date):
    print(f"Accessing URL: {url}")
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()  # Raise an exception for HTTP errors
        soup = BeautifulSoup(response.content, 'lxml')

        articles = []
        for link in soup.find_all('a', href=True):
            href = link['href']
            title = link.get_text()

            # Filter articles by keywords and date
            if any(keyword.lower() in title.lower() for keyword in keywords):
                # Ensure the URL is absolute
                if not href.startswith('http'):
                    href = url + href
                articles.append({"title": title.strip(), "url": href})
                print(f"Found article: {title.strip()} - {href}")

        return articles
    except Exception as e:
        print(f"Failed to fetch articles from {url}: {e}")
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
for name, url in websites.items():
    if is_website_up(url):
        time.sleep(30)  # Wait for 30 seconds before processing each website
        articles = get_articles(url, sum(keywords.values(), []), start_date, end_date)
        all_articles.extend(articles)

# Categorize articles
categorized_articles = categorize_articles(all_articles)

# Build email body
for category, articles in categorized_articles.items():
    email_body += f"\n\n{category}:\n"
    for article in articles:
        email_body += f"- {article['title']} ({article['url']})\n"

# Check if email body is empty
if not email_body.strip():
    email_body = "Nothing New today. Thanks for checking in with us."

# Create email message
msg = MIMEMultipart()
msg['From'] = email_from
msg['To'] = ", ".join(email_to)
msg['Subject'] = email_subject
msg.attach(MIMEText(email_body, 'plain'))

# Send email
try:
    server = smtplib.SMTP('smtp.gmail.com', 587)
    server.starttls()
    server.login(email_from, email_password)
    text = msg.as_string()
    server.sendmail(email_from, email_to, text)
    server.quit()
    print("Email sent successfully")
except Exception as e:
    print(f"Failed to send email: {e}")
