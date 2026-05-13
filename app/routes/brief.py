from fastapi import APIRouter, BackgroundTasks, HTTPException

from app.services.brief_audio import (
    brief_audio_status,
    ensure_brief_audio,
    prebuild_audio_enabled,
)
from app.services.brief_generator import generate_morning_brief
from app.services.brief_history import (
    get_morning_brief as get_saved_morning_brief,
    list_morning_briefs,
    save_morning_brief,
)
from app.services.tts import tts_status

router = APIRouter()


def queue_brief_audio_generation(
    brief: dict,
    history_id: int | str,
    background_tasks: BackgroundTasks,
) -> dict:
    if not prebuild_audio_enabled():
        return {"available": False, "status": "disabled"}
    if not tts_status()["enabled"]:
        return {"available": False, "status": "not_configured"}

    background_tasks.add_task(ensure_brief_audio, brief, history_id)
    return {"available": False, "status": "generating"}


@router.get("/morning")
def get_morning_brief(
    background_tasks: BackgroundTasks,
    save: bool = True,
    audio: bool = True,
):
    brief = generate_morning_brief()
    if save:
        saved = save_morning_brief(brief)
        brief["history_id"] = saved["id"]
        if audio:
            brief["audio_status"] = queue_brief_audio_generation(
                brief,
                saved["id"],
                background_tasks,
            )
        else:
            brief["audio_status"] = {"available": False, "status": "disabled"}
    return brief


@router.get("/history")
def get_brief_history(limit: int = 10):
    return list_morning_briefs(limit=limit)


@router.get("/history/{brief_id}")
def get_brief_history_item(brief_id: str):
    saved = get_saved_morning_brief(brief_id)
    if not saved:
        raise HTTPException(status_code=404, detail="Morning brief not found.")
    saved.setdefault("brief", {})["history_id"] = saved["id"]
    saved["audio_status"] = brief_audio_status(saved["id"])
    return saved
