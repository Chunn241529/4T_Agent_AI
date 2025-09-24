# app/main.py

from fastapi import FastAPI
from app.routes import chat
from app.routes import search

app = FastAPI(title="Web Search Chatbot")

app.include_router(chat.router)
app.include_router(search.router)
