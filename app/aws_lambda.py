from datetime import date

from mangum import Mangum

from app.main import app
from app.services.brief_audio import ensure_brief_audio
from app.services.brief_generator import generate_morning_brief
from app.services.brief_history import (
    get_morning_brief,
    list_morning_briefs,
    save_morning_brief,
)
from app.services.email_delivery import send_morning_brief_email

api_handler = Mangum(app, lifespan="off")


def _is_scheduled_event(event: dict) -> bool:
    return event.get("source") in ("aws.events", "aws.scheduler") or event.get(
        "detail-type"
    ) in ("Scheduled Event", "Scheduler Event")


def _scheduled_action(event: dict) -> str:
    detail = event.get("detail") if isinstance(event.get("detail"), dict) else {}
    return detail.get("action") or event.get("action") or "send_morning_brief"


def _latest_prepared_morning_brief() -> dict | None:
    today = date.today().isoformat()
    for summary in list_morning_briefs(limit=10):
        if summary.get("brief_date") != today:
            continue
        saved = get_morning_brief(summary["id"])
        if saved:
            return saved
    return None


def _prepare_morning_brief() -> dict:
    saved = _latest_prepared_morning_brief()
    if not saved:
        brief = generate_morning_brief()
        saved = save_morning_brief(brief)

    brief = saved["brief"]
    brief["history_id"] = saved["id"]
    brief["audio_status"] = ensure_brief_audio(brief, saved["id"])
    return {
        "status": "prepared",
        "history_id": saved["id"],
        "audio_status": brief["audio_status"],
    }


def _send_morning_brief() -> dict:
    saved = _latest_prepared_morning_brief()
    if not saved:
        _prepare_morning_brief()
        saved = _latest_prepared_morning_brief()
    if not saved:
        raise RuntimeError("Morning brief could not be prepared.")

    brief = saved["brief"]
    brief["history_id"] = saved["id"]
    result = send_morning_brief_email(brief)
    return {
        "status": "sent",
        "history_id": saved["id"],
        "email": result,
    }


def handler(event, context):
    if isinstance(event, dict) and _is_scheduled_event(event):
        action = _scheduled_action(event)
        if action == "prepare_morning_brief":
            body = _prepare_morning_brief()
        else:
            body = _send_morning_brief()
        return {
            "statusCode": 200,
            "body": body,
        }

    return api_handler(event, context)
