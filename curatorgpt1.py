import asyncio
import aiohttp
from bs4 import BeautifulSoup
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timedelta
import os
import logging
from urllib.parse import urlparse

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
    "Startup": ["startup", "funding"],
    "AI": ["AI", "artificial intelligence"]
}

# Set of processed URLs to avoid duplicates
processed_urls = set()

def should_process_url(url):
    parsed_url = urlparse(url)
    path = parsed_url.path

    # Check if URL has already been processed
    if url in processed_urls:
        return False

    # Check for /author/ in the URL
    if '/author/' in path:
        return False

    # Check if it's a category URL (you may need to adjust this based on the specific website structures)
    if any(keyword in path for keyword in ['category', 'topics', 'section']):
        return False

    return True

async def fetch_articles(session, url):
    async with session.get(url) as response:
        html = await response.text()
        soup = BeautifulSoup(html, 'lxml')
        articles = []
        for article in soup.find_all('article'):
            title_tag = article.find('h2')
            link_tag = article.find('a')
            if title_tag and link_tag:
                title = title_tag.text.strip()
                link = link_tag['href']
                if should_process_url(link):
                    articles.append({'title': title, 'url': link})
                    processed_urls.add(link)
        return articles

async def main():
    async with aiohttp.ClientSession() as session:
        tasks = [fetch_articles(session, url) for url in websites.values()]
        all_articles = await asyncio.gather(*tasks)

    # Flatten the list of articles
    articles = [article for site_articles in all_articles for article in site_articles]

    # Categorize articles
    categorized_articles = {category: [] for category in keywords.keys()}
    for article in articles:
        for category, kw_list in keywords.items():
            if any(kw.lower() in article['title'].lower() for kw in kw_list):
                categorized_articles[category].append(article)
                break

    # Build email content
    email_content = "<html><body>"
    for category, articles in categorized_articles.items():
        if articles:
            email_content += f"<h2>{category}</h2>"
            for article in articles:
                email_content += f"<p><a href='{article['url']}'>{article['title']}</a></p>"
                email_content += "<hr style='border-top: 2px solid #000; margin: 10px 0;'>"  # Bold line
    email_content += "</body></html>"

    # Send email
    msg = MIMEMultipart()
    msg['From'] = email_from
    msg['To'] = ", ".join(email_to)
    msg['Subject'] = email_subject
    msg.attach(MIMEText(email_content, 'html'))

    with smtplib.SMTP('smtp.gmail.com', 587) as server:
        server.starttls()
        server.login(email_from, email_password)
        server.send_message(msg)

if __name__ == "__main__":
    asyncio.run(main())
