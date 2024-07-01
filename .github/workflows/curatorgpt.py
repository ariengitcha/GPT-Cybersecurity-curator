import requests
from bs4 import BeautifulSoup
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timedelta

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
    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'lxml')

    articles = []
    for link in soup.find_all('a', href=True):
        href = link['href']
        title = link.get_text()

        if any(keyword.lower() in title.lower() for keyword in keywords):
            articles.append({"title": title, "url": href})

    return articles

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

# Email setup
email_from = "your-email@gmail.com"
email_to = "arien.seghetti@ironbow.com"
email_subject = f"Daily Cybersecurity News - {datetime.now().strftime('%Y-%m-%d')}"
email_body = ""

for category, articles in categorized_articles.items():
    email_body += f"\n\n{category}:\n"
    for article in articles:
        email_body += f"- {article['title']} ({article['url']})\n"

# Create email message
msg = MIMEMultipart()
msg['From'] = email_from
msg['To'] = email_to
msg['Subject'] = email_subject
msg.attach(MIMEText(email_body, 'plain'))

# Send email
server = smtplib.SMTP('smtp.gmail.com', 587)
server.starttls()
server.login(email_from, "your-email-password")
server.sendmail(email_from, email_to, msg.as_string())
server.quit()
