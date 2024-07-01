import requests
from bs4 import BeautifulSoup
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
import os

# Email configuration
email_from = os.getenv('EMAIL_USER')
email_password = os.getenv('EMAIL_PASSWORD')
email_to = "ariennation@gmail.com" "arien.seghetti@ironbow.com
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

# Function to get articles from a website
def get_articles(url, keywords):
    print(f"Accessing URL: {url}")
    try:
        response = requests.get(url)
        response.raise_for_status()  # Raise an exception for HTTP errors
        soup = BeautifulSoup(response.content, 'lxml')

        articles = []
        for link in soup.find_all('a', href=True):
            href = link['href']
            title = link.get_text()

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
all_articles = []
for name, url in websites.items():
    articles = get_articles(url, sum(keywords.values(), []))
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
msg['To'] = email_to
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

