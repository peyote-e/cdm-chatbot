import logging

from fastapi import FastAPI
from app.api.routes import router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)

app = FastAPI(
    title="CDM Banking Chatbot",
    description="RAG + Knowledge Graph API for querying the Microsoft Common Data Model Banking schema.",
    version="1.0.0",
)

app.include_router(router)
