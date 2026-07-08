import os
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GEMINI_FILE_SEARCH_STORE_ID = os.environ.get("GEMINI_FILE_SEARCH_STORE_ID")

if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY is not set.")
if not GEMINI_FILE_SEARCH_STORE_ID:
    raise ValueError("GEMINI_FILE_SEARCH_STORE_ID is not set in env.")

client = genai.Client(api_key=GEMINI_API_KEY)

store_name = f"fileSearchStores/{GEMINI_FILE_SEARCH_STORE_ID}"

print("How do I add a YouTube video?")
print("Loading...")
print(f"Searching articles from Gemini Store: {store_name}...")

system_instruction = (
    "You are OptiBot, the customer-support bot for OptiSigns.com.\n"
    "• Tone: helpful, factual, concise.\n"
    "• Only answer using the uploaded docs.\n"
    "• Max 5 bullet points; else link to the doc.\n"
    "• Cite up to 3 \"Article URL:\" lines per reply."
)

model = "gemini-2.5-flash"

try:
    response = client.models.generate_content(
        model=model,
        contents="How do I add a YouTube video?",
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            tools=[
                types.Tool(
                    file_search=types.FileSearch(
                        file_search_store_names=[store_name]
                    )
                )
            ]
        )
    )

    print("\n--- Answer ---")
    print(response.text)
except Exception as e:
    print(f"\nLỗi khi truy vấn Gemini: {e}")
