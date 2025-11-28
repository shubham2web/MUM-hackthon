import os
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("API_KEY")
print(f"API_KEY from .env: '{api_key}'")
print(f"Length: {len(api_key) if api_key else 0}")
print(f"Has quotes: {api_key.startswith(chr(34)) if api_key else False}")