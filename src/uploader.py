import os
import re
import math
import time
import requests
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

BASE_URL = "https://support.optisigns.com"
API_URL = f"{BASE_URL}/api/v2/help_center/en-us/articles.json"
ARTICLES_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "articles")

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

def get_zendesk_articles():
    """Fetch all active articles from Zendesk API to get current ids and updated_at."""
    url = f"{API_URL}?per_page=100"
    articles_map = {}
    
    print("Fetching current articles from Zendesk...")
    while url:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        
        for article in data.get("articles", []):
            if article.get("draft"):
                continue
            
            updated_at_str = article.get("updated_at")
            from datetime import datetime
            dt = datetime.strptime(updated_at_str, "%Y-%m-%dT%H:%M:%SZ")
            timestamp = int(dt.timestamp())
            
            title = article.get("title")
            slug = title.lower()
            slug = re.sub(r'[^a-z0-9]+', '-', slug)
            slug = slug.strip('-')
            
            articles_map[str(article.get("id"))] = {
                "slug": slug,
                "timestamp": timestamp,
                "title": title
            }
            
        url = data.get("next_page")
        
    return articles_map

def estimate_tokens_and_chunks(filepath):
    """Estimate tokens and chunks. Gemini API handles chunking internally during upload, 
    but we estimate here for logging purposes to fulfill the requirement."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            # 1 word is approx 1.3 tokens
            words = len(content.split())
            tokens = math.ceil(words * 1.3)
            
            # Assuming a standard 800/400 chunk strategy for estimation
            if tokens <= 800:
                chunks = 1
            else:
                chunks = 1 + math.ceil((tokens - 800) / 400)
                
            return tokens, chunks
    except Exception:
        return 0, 0

def get_gemini_files():
    """Fetch all files currently linked in the Gemini File API."""
    print("Fetching files attached to Gemini File API...")
    gemini_files = {}
    try:
        # Paginator implementation (using .list() directly, which returns an iterator)
        for file in client.files.list():
            if file.display_name and file.display_name.startswith("optibot_doc_"):
                match = re.match(r'^optibot_doc_(\d+)_(\d+)\.md$', file.display_name)
                if match:
                    article_id, ts = match.groups()
                    gemini_files[article_id] = {
                        "file_name": file.name,
                        "display_name": file.display_name,
                        "timestamp": int(ts)
                    }
    except Exception as e:
        print(f"Error listing files: {e}")
    return gemini_files

def sync_articles():
    if not client:
        print("ERROR: GEMINI_API_KEY is not set.")
        return
        
    active_gemini_files = get_gemini_files()
    
    # Fetch Zendesk articles
    zendesk_articles = get_zendesk_articles()
    
    stats = {"added": 0, "updated": 0, "deleted": 0, "skipped": 0}
    total_chunks = 0
    
    print(f"Found {len(zendesk_articles)} active articles on Zendesk.")
    print(f"Found {len(active_gemini_files)} active files in Gemini.")
    print("-" * 40)
    
    for article_id, zd_info in zendesk_articles.items():
        zd_ts = zd_info["timestamp"]
        slug = zd_info["slug"]
        filepath = os.path.join(ARTICLES_DIR, f"{slug}.md")
        
        if not os.path.exists(filepath):
            print(f"WARNING: Local file missing for {slug}. Please run scraper first.")
            continue
            
        is_add = article_id not in active_gemini_files
        is_update = not is_add and zd_ts > active_gemini_files[article_id]["timestamp"]
        
        if is_add or is_update:
            # Delete old if update
            if is_update:
                old_file_name = active_gemini_files[article_id]["file_name"]
                try:
                    client.files.delete(name=old_file_name)
                    stats["updated"] += 1
                except Exception as e:
                    print(f"Failed to delete old file {old_file_name}: {e}")
            else:
                stats["added"] += 1
                
            # Upload new file
            display_name = f"optibot_doc_{article_id}_{zd_ts}.md"
            print(f"Uploading {display_name}...")
            
            try:
                # Upload to file API
                file_obj = client.files.upload(
                    path=filepath,
                    config={'display_name': display_name}
                )
                
                # Wait for processing
                print(f"  Waiting for {display_name} to process...")
                while getattr(file_obj, 'state', None) == "PROCESSING":
                    time.sleep(1)
                    file_obj = client.files.get(name=file_obj.name)
                    
            except Exception as e:
                print(f"Failed to upload {display_name}: {e}")
            
            _, chunks = estimate_tokens_and_chunks(filepath)
            total_chunks += chunks
            
        else:
            stats["skipped"] += 1
            _, chunks = estimate_tokens_and_chunks(filepath)
            total_chunks += chunks
            
    # Process Deleted
    for article_id, gemini_info in active_gemini_files.items():
        if article_id not in zendesk_articles:
            print(f"Deleting outdated file for article {article_id}...")
            try:
                client.files.delete(name=gemini_info["file_name"])
                stats["deleted"] += 1
            except Exception as e:
                print(f"Failed to delete {gemini_info['file_name']}: {e}")
            
    print("-" * 40)
    print("SYNC COMPLETE")
    print(f"Total files in Gemini: {stats['added'] + stats['updated'] + stats['skipped']}")
    print(f"Estimated chunks embedded: {total_chunks}")
    print(f"Added: {stats['added']}, Updated: {stats['updated']}, Deleted: {stats['deleted']}, Skipped: {stats['skipped']}")

if __name__ == "__main__":
    sync_articles()
