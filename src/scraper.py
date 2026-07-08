import os
import re
import requests
from bs4 import BeautifulSoup
from markdownify import markdownify

BASE_URL = "https://support.optisigns.com"
API_URL = f"{BASE_URL}/api/v2/help_center/en-us/articles.json"
ARTICLES_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "articles")

def generate_slug(title):
    # Convert to lowercase
    slug = title.lower()
    # Replace non-alphanumeric characters with hyphens
    slug = re.sub(r'[^a-z0-9]+', '-', slug)
    # Strip leading and trailing hyphens
    slug = slug.strip('-')
    return slug

def process_html_content(html_body):
    if not html_body:
        return ""
    
    # Replace non-breaking spaces to avoid encoding issues (like Â)
    html_body = html_body.replace('\xa0', ' ').replace('&nbsp;', ' ')
    
    soup = BeautifulSoup(html_body, 'html.parser')
    
    # Convert relative links and images to absolute URLs
    for tag in soup.find_all(['a', 'img']):
        if tag.name == 'a' and tag.get('href'):
            href = tag['href']
            if href.startswith('/') and not href.startswith('//'):
                tag['href'] = f"{BASE_URL}{href}"
        elif tag.name == 'img' and tag.get('src'):
            src = tag['src']
            if src.startswith('data:'):
                tag.decompose()
            elif src.startswith('/') and not src.startswith('//'):
                tag['src'] = f"{BASE_URL}{src}"

    # Process links (a tags)
    for a in soup.find_all('a', href=re.compile(r'^#')):
        if not a.text.strip():
            a.decompose()
            
    return str(soup)

def scrape_articles():
    if not os.path.exists(ARTICLES_DIR):
        os.makedirs(ARTICLES_DIR)
        
    url = f"{API_URL}?per_page=100"
    article_count = 0
    
    print(f"Fetching articles from {url}")
    
    while url:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        
        articles = data.get("articles", [])
        
        for article in articles:
            if article.get("draft"):
                continue
                
            article_id = article.get("id")
            title = article.get("title")
            html_body = article.get("body")
            html_url = article.get("html_url")
            
            slug = generate_slug(title)
            filename = f"{slug}.md"
            filepath = os.path.join(ARTICLES_DIR, filename)
            
            # Process HTML to fix relative links and clean up
            processed_html = process_html_content(html_body)
            
            # Convert to Markdown
            markdown_content = markdownify(processed_html, heading_style="ATX")
            
            # Append Metadata URL for citations
            markdown_content += f"\n\n---\nArticle URL: {html_url}\n"
            
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(markdown_content)
                
            article_count += 1
            print(f"Saved: {filename}")
            
        url = data.get("next_page")
        
    print(f"Total articles scraped: {article_count}")

if __name__ == "__main__":
    scrape_articles()
