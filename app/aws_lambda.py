from mangum import Mangum

from app.main import app
from app.services.brief_generator import generate_morning_brief
from app.services.brief_history import save_morning_brief
from app.services.email_delivery import send_morning_brief_email

api_handler = Mangum(app, lifespan="off")


def _is_scheduled_event(event: dict) -> bool:
    return event.get("source") in ("aws.events", "aws.scheduler") or event.get(
        "detail-type"
    ) in ("Scheduled Event", "Scheduler Event")


def handler(event, context):
    if isinstance(event, dict) and _is_scheduled_event(event):
        brief = generate_morning_brief()
        saved = save_morning_brief(brief)
        brief["history_id"] = saved["id"]
        result = send_morning_brief_email(brief)
        return {
            "statusCode": 200,
            "body": {
                "status": "sent",
                "history_id": saved["id"],
                "email": result,
            },
        }

    return api_handler(event, context)
