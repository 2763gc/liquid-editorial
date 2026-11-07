from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.services.search import perform_search

router = APIRouter(prefix="/search", tags=["search"])

@router.get("")
async def search_endpoint(
    q: str = Query(..., min_length=1),
    limit: int = Query(15, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    hits = await perform_search(db, q, limit=limit)
    return {
        "query": q,
        "total": len(hits),
        "results": hits,
    }
