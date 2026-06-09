import os
from pathlib import Path
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = os.getenv("DB_NAME", "test_db")

client=MongoClient(MONGO_URI)
db=client[DB_NAME]

#collection
users_collection = db["users"]
chunk_collection=db["text"]
chat_history_collection=db["chat_history"]
quiz_collection=db["quiz"]
quiz_history=db["quiz_history"]