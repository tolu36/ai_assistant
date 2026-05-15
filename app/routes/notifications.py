from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.services.push_notifications import (
    PushNotificationError,
    delete_push_subscription,
    notification_status,
    save_push_subscription,
    send_notification_to_all,
)

router = APIRouter()


class PushSubscriptionRequest(BaseModel):
    endpoint: str = Field(min_length=1)
    keys: Dict[str, str]
    expirationTime: Any = None


class PushUnsubscribeRequest(BaseModel):
    endpoint: str = Field(min_length=1)


@router.get("/status")
def get_notification_status():
    return notification_status()


@router.get("/vapid-public-key")
def get_vapid_public_key():
    status = notification_status(include_count=False)
    if not status["configured"]:
        raise HTTPException(status_code=503, detail="Push notifications are not configured.")

    from config import PUSH_VAPID_PUBLIC_KEY
    import os

    return {
        "public_key": os.getenv("PUSH_VAPID_PUBLIC_KEY", PUSH_VAPID_PUBLIC_KEY),
    }


@router.post("/subscribe")
def subscribe_to_push_notifications(
    subscription: PushSubscriptionRequest,
    request: Request,
):
    payload = (
        subscription.model_dump()
        if hasattr(subscription, "model_dump")
        else subscription.dict()
    )
    try:
        saved = save_push_subscription(
            payload,
            request.headers.get("user-agent", ""),
        )
    except PushNotificationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "status": "subscribed",
        "endpoint_hash": saved["endpoint_hash"],
    }


@router.post("/unsubscribe")
def unsubscribe_from_push_notifications(subscription: PushUnsubscribeRequest):
    deleted = delete_push_subscription(subscription.endpoint)
    return {
        "status": "unsubscribed" if deleted else "not_found",
    }


@router.post("/test")
def send_test_notification():
    result = send_notification_to_all(
        title="Personal AI Assistant",
        body="Notifications are enabled.",
        url="/",
        tag="personal-ai-assistant-test",
    )
    if result.get("status") == "skipped":
        raise HTTPException(status_code=503, detail="Push notifications are not configured.")
    return result
