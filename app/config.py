# Configuration settings for the application, such as database settings, environment variables, etc.
import os
from dotenv import load_dotenv

load_dotenv()

# PostgreSQL connection using the lumora user
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://lumora:Minhtan%402024@localhost/lumora")

# OpenAI API configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    print("Warning: OPENAI_API_KEY is not set. LLM-based query responses will not work.")

# Pinecone configuration
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_ENVIRONMENT = os.getenv("PINECONE_ENVIRONMENT", "aws-us-east-1")
PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "lumora")
