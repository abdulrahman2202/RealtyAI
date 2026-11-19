
import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env", override=True)

api_key = os.getenv("GROQ_API_KEY")
base_url = os.getenv("GROQ_BASE_URL")
model = os.getenv("GROQ_MODEL")

if not all([api_key, base_url, model]):
    raise RuntimeError("Missing Groq configuration in .env")

client = OpenAI(
    api_key=api_key,
    base_url=base_url,
    timeout=60,
)

print("Testing Groq API...")
print("Model:", model)

try:
    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": "You are a helpful assistant."
            },
            {
                "role": "user",
                "content": "Reply exactly: RealtyAI Groq integration is working!"
            }
        ],
        max_completion_tokens=100,
    )

    print("\nSUCCESS")
    print(response.choices[0].message.content)

except Exception as error:
    print("\nFAILED")
    print(type(error).__name__)
    print(str(error))
