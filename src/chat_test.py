import os
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

client = genai.Client(api_key=GEMINI_API_KEY)

print("How do I add a YouTube video?")

print("Loading...")
files = []
youtube_file = None
try:
    for f in client.files.list():
        if f.display_name and f.display_name.startswith("optibot_doc_") and getattr(f, "state", None) == "ACTIVE":
            files.append(f)


except Exception as e:
    print(f"Lỗi khi lấy danh sách file: {e}")

print(f"Searched articles")
print("Read article")

system_instruction = (
    "You are OptiBot, the customer-support bot for OptiSigns.com.\n"
    "• Tone: helpful, factual, concise.\n"
    "• Only answer using the uploaded docs.\n"
    "• Max 5 bullet points; else link to the doc.\n"
    "• Cite up to 3 \"Article URL:\" lines per reply."
)

model = "gemini-2.5-flash"

contents = [
    types.Part.from_uri(file_uri=f.uri, mime_type=f.mime_type) for f in files
] + ["How do I add a YouTube video?"]

try:
    response = client.models.generate_content(
        model=model,
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=system_instruction
        )
    )

    print("\n--- Answer ---")
    print(response.text)
except Exception as e:
    print(f"\nLỗi khi truy vấn Gemini: {e}")
