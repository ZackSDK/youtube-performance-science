from dotenv import load_dotenv
import os
load_dotenv()

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")

if not YOUTUBE_API_KEY:
    raise ValueError("YOUTUBE_API_KEY not found in .env file")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL not found in .env file")

