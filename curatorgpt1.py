import feedparser
import requests
from bs4 import BeautifulSoup

# Function to parse RSS feeds
def parse_rss_feed(url):
    feed = feedparser.parse(url)
    articles = []
    for entry in feed.entries:
        articles.append({
            'title': entry.title,
            'link': entry.link,
            'summary': entry.summary
        })
    return articles

# Function to scrape a webpage with better error handling and flexible parsing
def scrape_website(url):
    try:
        response = requests.get(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        articles = []
        
        # Example logic for different website structures
        if 'threatpost' in url:
            for item in soup.find_all('div', class_='c-article__content'):
                title_tag = item.find('h2', class_='c-article__title')
                if title_tag and title_tag.a:
                    title = title_tag.a.text.strip()
                    link = title_tag.a['href']
                    summary = item.find('p').text.strip() if item.find('p') else ''
                    articles.append({'title': title, 'link': link, 'summary': summary})
        elif 'scmagazine' in url:
            for item in soup.find_all('div', class_='listing'):
                title_tag = item.find('h2')
                if title_tag and title_tag.a:
                    title = title_tag.a.text.strip()
                    link = title_tag.a['href']
                    summary = item.find('p').text.strip() if item.find('p') else ''
                    articles.append({'title': title, 'link': link, 'summary': summary})
        else:
            for item in soup.find_all('article'):
                title = item.find('h2').text.strip() if item.find('h2') else ''
                link = item.find('a')['href'] if item.find('a') else ''
                summary = item.find('p').text.strip() if item.find('p') else ''
                articles.append({'title': title, 'link': link, 'summary': summary})
        
        return articles
    except requests.RequestException as e:
        print(f"Error fetching {url}: {e}")
        return []
    except Exception as e:
        print(f"Error parsing {url}: {e}")
        return []

# List of RSS feed URLs
rss_feeds = [
    'https://krebsonsecurity.com/feed/',
    'https://www.darkreading.com/rss.xml'
]

# List of websites to scrape
websites = [
    'https://threatpost.com',
    'https://www.scmagazine.com'
]

# Collect articles from RSS feeds
rss_articles = []
for feed in rss_feeds:
    rss_articles.extend(parse_rss_feed(feed))

# Collect articles from websites
scraped_articles = []
for site in websites:
    scraped_articles.extend(scrape_website(site))

# Combine and display articles
all_articles = rss_articles + scraped_articles
for article in all_articles:
    print(f"Title: {article['title']}\nLink: {article['link']}\nSummary: {article['summary']}\n")
