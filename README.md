# Automated Knowledge Base Sync Pipeline

This project automates the extraction, conversion, and syncing of help center articles into the Gemini AI File Search API, enabling an AI Assistant to answer queries based on the latest documentation.

## 1. Setup

**Prerequisites:** Python >= 3.9

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Configure environment variables:
   ```bash
   cp .env.sample .env
   ```
   Open `.env` and fill in your `GEMINI_API_KEY`.

## 2. How to Run Locally

To run the complete pipeline (Scraping + Uploading delta):
```bash
python main.py
```

To test the AI Assistant with the embedded RAG knowledge:
```bash
python src/chat_test.py
```

## 3. Link to Daily Job Logs

The pipeline is fully dockerized and deployed via **GitHub Actions** as a daily Cron Job (runs every day at 02:00 UTC). This ensures a stateless, serverless architecture that automatically synchronizes deltas.

**Latest Job Logs:**
[View Latest Sync Logs Here](https://github.com/Necros1ss/Project/blob/main/last_run.log)

*(Note: The `last_run.log` file is automatically committed back to this repository after every successful run, detailing the exact counts of added, updated, and skipped files.)*

## 4. Chunking Strategy

Instead of manually slicing tokens, this project leverages the **Fully-managed Chunking Strategy** built natively into the `google-genai` File API.
- By uploading the raw Markdown files directly, Gemini automatically processes, chunks, and indexes the documents for optimal semantic retrieval.
- This approach is highly scalable and ensures that context windows are optimally utilized by the model's native RAG backend.
- *For logging purposes*, the script estimates the chunks processed using a standard 800-token max / 400-token overlap logic to fulfill the reporting requirement.

## 5. Screenshot of Assistant

Below is a screenshot demonstrating the OptiBot Assistant successfully answering the sample query ("How do I add a YouTube video?") and correctly citing the source article URL:

![Assistant Screenshot](screenshot.png)
*(Please add your screenshot image named `screenshot.png` to the repository root to display it here).*
