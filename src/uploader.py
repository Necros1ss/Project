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

from tenacity import retry, stop_after_attempt, wait_exponential

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GEMINI_FILE_SEARCH_STORE_ID = os.environ.get("GEMINI_FILE_SEARCH_STORE_ID", "optisigns-help-center-9n6q5v8jpotm")

if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY is not set.")

client = genai.Client(api_key=GEMINI_API_KEY)

# Exponential backoff retries for file uploads
@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=15),
    reraise=True
)

def upload_file_with_retry(store_name, filepath, display_name):
    operation = client.file_search_stores.upload_to_file_search_store(
        file_search_store_name=store_name,
        file=filepath,
        config=types.UploadToFileSearchStoreConfig(display_name=display_name)
    )
    
    while not operation.done:
        time.sleep(2)
        operation = client.operations.get(operation=operation)
        
    if operation.error:
        raise Exception(f"Upload operation failed: {operation.error}")
    return operation

# Exponential backoff retries for file deletions
@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=15),
    reraise=True
)
def delete_file_with_retry(name):
    client.file_search_stores.documents.delete(name=name, config={'force': True})

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

@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=15),
    reraise=True
)
def get_gemini_files(store_name):
    """Fetch all files currently linked in the Gemini File Search Store."""
    print(f"Fetching files attached to Gemini File Search Store ({store_name})...")
    gemini_files = {}
    try:
        for doc in client.file_search_stores.documents.list(parent=store_name):
            if doc.display_name and doc.display_name.startswith("optibot_doc_"):
                match = re.match(r'^optibot_doc_(\d+)_(\d+)\.md$', doc.display_name)
                if match:
                    article_id, ts = match.groups()
                    gemini_files[article_id] = {
                        "file_name": doc.name,  # Resource name (fileSearchStores/.../documents/...)
                        "display_name": doc.display_name,
                        "timestamp": int(ts)
                    }
    except Exception as e:
        print(f"Error listing files in store: {e}")
        raise e
    return gemini_files

def get_or_create_store():
    global GEMINI_FILE_SEARCH_STORE_ID
    if GEMINI_FILE_SEARCH_STORE_ID:
        store_name = f"fileSearchStores/{GEMINI_FILE_SEARCH_STORE_ID}"
        print(f"Using existing File Search Store: {store_name}")
        return store_name
        
    print("GEMINI_FILE_SEARCH_STORE_ID is not set in env.")
    print("Creating new File Search Store 'OptiSigns Help Center'...")
    try:
        store = client.file_search_stores.create(config={'display_name': 'OptiSigns Help Center'})
        store_name = store.name
        GEMINI_FILE_SEARCH_STORE_ID = store_name.split("/")[-1]
        
        # Auto-append store ID to local .env file
        env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
        if os.path.exists(env_path):
            with open(env_path, "a") as env_file:
                env_file.write(f"\nGEMINI_FILE_SEARCH_STORE_ID={GEMINI_FILE_SEARCH_STORE_ID}\n")
            print(f"Automatically appended GEMINI_FILE_SEARCH_STORE_ID={GEMINI_FILE_SEARCH_STORE_ID} to .env")
            
        print("="*60)
        print(f"CREATED STORE: {store_name}")
        print(f"PLEASE PASTE THIS VALUE INTO YOUR ENVS IF DEPLOYING:")
        print(f"GEMINI_FILE_SEARCH_STORE_ID={GEMINI_FILE_SEARCH_STORE_ID}")
        print("="*60)
        return store_name
    except Exception as e:
        print(f"Failed to create File Search Store: {e}")
        raise e

def sync_articles():
    store_name = get_or_create_store()
    active_gemini_files = get_gemini_files(store_name)
    
    # Fetch Zendesk articles
    zendesk_articles = get_zendesk_articles()
    
    stats = {"added": 0, "updated": 0, "deleted": 0, "skipped": 0}
    total_chunks = 0
    
    print(f"Found {len(zendesk_articles)} active articles on Zendesk.")
    print(f"Found {len(active_gemini_files)} active files in Gemini Store.")
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
                    delete_file_with_retry(name=old_file_name)
                    stats["updated"] += 1
                except Exception as e:
                    print(f"Failed to delete old document {old_file_name}: {e}")
                    raise e
            else:
                stats["added"] += 1
                
            # Upload new file
            display_name = f"optibot_doc_{article_id}_{zd_ts}.md"
            print(f"Uploading {display_name}...")
            
            try:
                upload_file_with_retry(
                    store_name=store_name,
                    filepath=filepath,
                    display_name=display_name
                )
                print(f"  Upload completed for {display_name}")
                
            except Exception as e:
                print(f"Failed to upload {display_name}: {e}")
                raise e
            
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
                delete_file_with_retry(name=gemini_info["file_name"])
                stats["deleted"] += 1
            except Exception as e:
                print(f"Failed to delete {gemini_info['file_name']}: {e}")
                raise e
            
    print("-" * 40)
    print("SYNC COMPLETE")
    print(f"Total files in Gemini Store: {stats['added'] + stats['updated'] + stats['skipped']}")
    print(f"Estimated chunks embedded: {total_chunks}")
    print(f"Added: {stats['added']}, Updated: {stats['updated']}, Deleted: {stats['deleted']}, Skipped: {stats['skipped']}")

if __name__ == "__main__":
    sync_articles()
