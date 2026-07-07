import sys
import src.scraper as scraper
import src.uploader as uploader

def main():
    print("=" * 50)
    print("STARTING OPTISIGNS DAILY KNOWLEDGE SYNC")
    print("=" * 50)
    
    print("\n--- PHASE 1: SCRAPING ---")
    try:
        scraper.scrape_articles()
    except Exception as e:
        print(f"Error during scraping: {e}")
        sys.exit(1)
        
    print("\n--- PHASE 2: UPLOADING TO GEMINI ---")
    try:
        uploader.sync_articles()
    except Exception as e:
        print(f"Error during uploading: {e}")
        sys.exit(1)
        
    print("\n" + "=" * 50)
    print("SYNC PROCESS COMPLETED SUCCESSFULLY")
    print("=" * 50)

if __name__ == "__main__":
    main()
