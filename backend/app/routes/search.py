# app/routes/search.py

from fastapi import APIRouter
from app.services.web_searcher import search_web

router = APIRouter(prefix="/search")

@router.get("")
async def search(query: str):
    results = await search_web(query)
    return {"results": results}
