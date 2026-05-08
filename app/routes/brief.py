from fastapi import APIRouter, HTTPException

from app.services.brief_generator import generate_morning_brief
from app.services.brief_history import (
    get_morning_brief as get_saved_morning_brief,
    list_morning_briefs,
    save_morning_brief,
)

router = APIRouter()


@router.get("/morning")
async def get_morning_brief(save: bool = True):
    brief = generate_morning_brief()
    if save:
        saved = save_morning_brief(brief)
        brief["history_id"] = saved["id"]
    return brief


@router.get("/history")
async def get_brief_history(limit: int = 10):
    return list_morning_briefs(limit=limit)


@router.get("/history/{brief_id}")
async def get_brief_history_item(brief_id: int):
    saved = get_saved_morning_brief(brief_id)
    if not saved:
        raise HTTPException(status_code=404, detail="Morning brief not found.")
    return saved
