import os
from dotenv import load_dotenv
from elasticsearch import Elasticsearch

# Load .env file
dotenv_file = os.getenv('DJANGO_ENV', '.env.dev')
load_dotenv(dotenv_file)

# Read environment variables
ES_HOST = os.getenv("ELASTICSEARCH_HOST")
ES_USER = os.getenv("ELASTICSEARCH_USER")
ES_PASSWORD = os.getenv("ELASTICSEARCH_PASSWORD")
INDEX_NAME = os.getenv("ELASTICSEARCH_INDEX")

# Create Elasticsearch client
es = Elasticsearch(
    ES_HOST,
    basic_auth=(ES_USER, ES_PASSWORD)  # Use `basic_auth` instead of deprecated `http_auth`
)

# Check and delete index
if es.indices.exists(index=INDEX_NAME):
    es.indices.delete(index=INDEX_NAME)
    print(f"Index '{INDEX_NAME}' deleted successfully.")
else:
    print(f"Index '{INDEX_NAME}' does not exist.")
