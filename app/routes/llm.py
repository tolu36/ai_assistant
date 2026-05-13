from fastapi import APIRouter

from app.services.llm_parser import get_llm_status

router = APIRouter()


@router.get("/status")
def llm_status(check: bool = False):
    return get_llm_status(check=check)
