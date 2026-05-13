from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.services import preferences

router = APIRouter()


class PreferencesRequest(BaseModel):
    sports_interests: list[str] = Field(default_factory=list)
    sports_teams: list[str] = Field(default_factory=list)
    finance_topics: list[str] = Field(default_factory=list)
    finance_watchlist: list[str] = Field(default_factory=list)


@router.get("")
def get_preferences():
    return preferences.load_preferences()


@router.post("")
def update_preferences(request: PreferencesRequest):
    return preferences.save_preferences(request.model_dump(exclude_unset=True))
