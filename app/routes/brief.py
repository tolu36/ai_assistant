from fastapi import APIRouter

from app.services.brief_generator import generate_morning_brief

router = APIRouter()


@router.get("/morning")
async def get_morning_brief():
    return generate_morning_brief()
