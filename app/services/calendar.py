import json
import logging
import os
from datetime import datetime
from typing import Dict, List

from dateutil import parser as dateutil_parser

from config import (
    CALENDAR_PROVIDER,
    GOOGLE_CALENDAR_ID,
    GOOGLE_CREDENTIALS_PATH,
    GOOGLE_TOKEN_PATH,
    SCOPES,
    TIMEZONE,
)

LOGGER = logging.getLogger(__name__)


def _calendar_provider() -> str:
    return os.getenv("CALENDAR_PROVIDER", CALENDAR_PROVIDER).lower()


def _is_mock_calendar() -> bool:
    return _calendar_provider() == "mock"


def _ensure_credentials():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow

    creds = None
    if os.path.exists(GOOGLE_TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(GOOGLE_TOKEN_PATH, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(GOOGLE_CREDENTIALS_PATH):
                raise FileNotFoundError(
                    f"Google credentials file not found at {GOOGLE_CREDENTIALS_PATH}."
                )
            flow = InstalledAppFlow.from_client_secrets_file(
                GOOGLE_CREDENTIALS_PATH,
                SCOPES,
            )
            creds = flow.run_local_server(port=0)
        os.makedirs(os.path.dirname(GOOGLE_TOKEN_PATH), exist_ok=True)
        with open(GOOGLE_TOKEN_PATH, "w", encoding="utf-8") as token_file:
            token_file.write(creds.to_json())

    return creds


def _get_service():
    from googleapiclient.discovery import build

    creds = _ensure_credentials()
    return build("calendar", "v3", credentials=creds, cache_discovery=False)


def _to_rfc3339(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=None)
    return value.isoformat()


def list_busy_slots(start: datetime, end: datetime) -> List[Dict[str, datetime]]:
    if _is_mock_calendar():
        return []

    service = _get_service()
    result = (
        service.events()
        .list(
            calendarId=GOOGLE_CALENDAR_ID,
            timeMin=start.isoformat() + "Z" if start.tzinfo is None else start.isoformat(),
            timeMax=end.isoformat() + "Z" if end.tzinfo is None else end.isoformat(),
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )

    busy = []
    for event in result.get("items", []):
        start_str = event["start"].get("dateTime") or event["start"].get("date")
        end_str = event["end"].get("dateTime") or event["end"].get("date")
        if start_str and end_str:
            busy.append(
                {
                    "start": dateutil_parser.parse(start_str),
                    "end": dateutil_parser.parse(end_str),
                }
            )
    return busy


def create_event(
    title: str,
    start: datetime,
    end: datetime,
    description: str = "",
) -> Dict[str, str]:
    if _is_mock_calendar():
        return {
            "id": "mock-event",
            "htmlLink": "mock://calendar/events/mock-event",
            "summary": title,
            "start": _to_rfc3339(start),
            "end": _to_rfc3339(end),
        }

    service = _get_service()
    event_body = {
        "summary": title,
        "description": description,
        "start": {"dateTime": _to_rfc3339(start), "timeZone": TIMEZONE},
        "end": {"dateTime": _to_rfc3339(end), "timeZone": TIMEZONE},
    }
    created = (
        service.events()
        .insert(calendarId=GOOGLE_CALENDAR_ID, body=event_body)
        .execute()
    )
    return {
        "id": created.get("id"),
        "htmlLink": created.get("htmlLink"),
        "summary": created.get("summary"),
        "start": created["start"].get("dateTime"),
        "end": created["end"].get("dateTime"),
    }
