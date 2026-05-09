import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

from dateutil import parser as dateutil_parser

from config import DYNAMODB_TABLE_NAME, DYNAMODB_USER_ID, STORAGE_PROVIDER


def storage_provider() -> str:
    return os.getenv("STORAGE_PROVIDER", STORAGE_PROVIDER).lower()


def is_dynamodb_enabled() -> bool:
    return storage_provider() == "dynamodb"


def _table_name() -> str:
    return os.getenv("DYNAMODB_TABLE_NAME", DYNAMODB_TABLE_NAME)


def _user_id() -> str:
    return os.getenv("DYNAMODB_USER_ID", DYNAMODB_USER_ID)


def _pk() -> str:
    return f"USER#{_user_id()}"


def _table():
    import boto3

    return boto3.resource("dynamodb").Table(_table_name())


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json_default(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _serialize_slots(slots: List[Dict[str, datetime]]) -> List[Dict[str, str]]:
    return [
        {
            "start": slot["start"].isoformat(),
            "end": slot["end"].isoformat(),
        }
        for slot in slots
    ]


def _deserialize_slots(slots: List[Dict[str, str]]) -> List[Dict[str, datetime]]:
    return [
        {
            "start": dateutil_parser.parse(slot["start"]),
            "end": dateutil_parser.parse(slot["end"]),
        }
        for slot in slots
    ]


def _deserialize_parsed_task(parsed_json: str) -> Dict[str, Any]:
    parsed = json.loads(parsed_json)
    for field in ("start_datetime", "end_datetime"):
        value = parsed.get(field)
        if isinstance(value, str) and value:
            parsed[field] = dateutil_parser.parse(value)
    return parsed


def load_preferences(defaults: Dict[str, List[str]]) -> Dict[str, List[str]]:
    item = _table().get_item(
        Key={"pk": _pk(), "sk": "PREFERENCES"},
    ).get("Item")
    if not item:
        return defaults

    loaded = dict(defaults)
    for key in loaded:
        value = item.get(key)
        if isinstance(value, list):
            loaded[key] = [str(entry) for entry in value if str(entry).strip()]
    return loaded


def save_preferences(preferences: Dict[str, List[str]]) -> Dict[str, List[str]]:
    item = {
        "pk": _pk(),
        "sk": "PREFERENCES",
        "type": "preferences",
        "updated_at": _now(),
        **preferences,
    }
    _table().put_item(Item=item)
    return preferences


def save_morning_brief(brief: Dict[str, Any]) -> Dict[str, Any]:
    created_at = _now()
    brief_id = created_at.replace(":", "").replace(".", "-")
    item = {
        "pk": _pk(),
        "sk": f"BRIEF#{brief_id}",
        "type": "morning_brief",
        "id": brief_id,
        "brief_date": brief.get("date", ""),
        "created_at": created_at,
        "payload_json": json.dumps(brief, sort_keys=True, default=str),
    }
    _table().put_item(Item=item)
    return {
        "id": brief_id,
        "brief_date": item["brief_date"],
        "created_at": created_at,
        "brief": brief,
    }


def list_morning_briefs(limit: int = 10) -> List[Dict[str, Any]]:
    from boto3.dynamodb.conditions import Key

    response = _table().query(
        KeyConditionExpression=Key("pk").eq(_pk()) & Key("sk").begins_with("BRIEF#"),
        ScanIndexForward=False,
        Limit=max(1, min(100, int(limit))),
    )
    return [
        {
            "id": item.get("id", item["sk"].replace("BRIEF#", "")),
            "brief_date": item.get("brief_date", ""),
            "created_at": item.get("created_at", ""),
        }
        for item in response.get("Items", [])
    ]


def get_morning_brief(brief_id: str) -> Dict[str, Any] | None:
    item = _table().get_item(
        Key={"pk": _pk(), "sk": f"BRIEF#{brief_id}"},
    ).get("Item")
    if not item:
        return None
    return {
        "id": item.get("id", brief_id),
        "brief_date": item.get("brief_date", ""),
        "created_at": item.get("created_at", ""),
        "brief": json.loads(item.get("payload_json", "{}")),
    }


def create_proposal(
    task_text: str,
    parsed: Dict[str, Any],
    slots: List[Dict[str, datetime]],
) -> Dict[str, Any]:
    proposal_id = str(uuid.uuid4())
    now = _now()
    stored_slots = _serialize_slots(slots)
    item = {
        "pk": _pk(),
        "sk": f"PROPOSAL#{proposal_id}",
        "type": "schedule_proposal",
        "id": proposal_id,
        "task_text": task_text,
        "parsed_json": json.dumps(parsed, default=_json_default),
        "slots_json": json.dumps(stored_slots),
        "status": "proposed",
        "created_at": now,
        "feedback": "",
    }
    _table().put_item(Item=item)
    return {
        "id": proposal_id,
        "task_text": task_text,
        "parsed": parsed,
        "slots": stored_slots,
        "status": "proposed",
        "created_at": now,
        "feedback": "",
    }


def get_proposal(proposal_id: str) -> Dict[str, Any] | None:
    item = _table().get_item(
        Key={"pk": _pk(), "sk": f"PROPOSAL#{proposal_id}"},
    ).get("Item")
    if not item:
        return None
    return {
        "id": item["id"],
        "task_text": item["task_text"],
        "parsed": _deserialize_parsed_task(item["parsed_json"]),
        "slots": json.loads(item["slots_json"]),
        "status": item["status"],
        "created_at": item["created_at"],
        "feedback": item.get("feedback", ""),
    }


def update_proposal_slots(
    proposal_id: str,
    slots: List[Dict[str, datetime]],
    feedback: str = "",
) -> Dict[str, Any] | None:
    stored_slots = _serialize_slots(slots)
    table = _table()
    table.update_item(
        Key={"pk": _pk(), "sk": f"PROPOSAL#{proposal_id}"},
        UpdateExpression="SET slots_json = :slots, #status = :status, feedback = :feedback",
        ExpressionAttributeNames={"#status": "status"},
        ExpressionAttributeValues={
            ":slots": json.dumps(stored_slots),
            ":status": "revised",
            ":feedback": feedback,
        },
    )
    return get_proposal(proposal_id)


def mark_proposal_confirmed(proposal_id: str) -> None:
    _table().update_item(
        Key={"pk": _pk(), "sk": f"PROPOSAL#{proposal_id}"},
        UpdateExpression="SET #status = :status",
        ExpressionAttributeNames={"#status": "status"},
        ExpressionAttributeValues={":status": "confirmed"},
    )


def add_constraint(
    reason: str,
    raw_feedback: str,
    start_hour: int | None = None,
    end_hour: int | None = None,
) -> Dict[str, Any]:
    constraint_id = str(uuid.uuid4())
    now = _now()
    item = {
        "pk": _pk(),
        "sk": f"CONSTRAINT#{now}#{constraint_id}",
        "type": "scheduler_constraint",
        "id": constraint_id,
        "reason": reason,
        "start_hour": start_hour,
        "end_hour": end_hour,
        "raw_feedback": raw_feedback,
        "created_at": now,
    }
    _table().put_item(Item=item)
    return {
        "id": constraint_id,
        "reason": reason,
        "start_hour": start_hour,
        "end_hour": end_hour,
        "raw_feedback": raw_feedback,
        "created_at": now,
    }


def list_constraints() -> List[Dict[str, Any]]:
    from boto3.dynamodb.conditions import Key

    response = _table().query(
        KeyConditionExpression=Key("pk").eq(_pk())
        & Key("sk").begins_with("CONSTRAINT#"),
        ScanIndexForward=True,
    )
    return [
        {
            "id": item["id"],
            "reason": item["reason"],
            "start_hour": item.get("start_hour"),
            "end_hour": item.get("end_hour"),
            "raw_feedback": item.get("raw_feedback", ""),
            "created_at": item.get("created_at", ""),
        }
        for item in response.get("Items", [])
    ]


def proposal_slots_as_datetimes(proposal: Dict[str, Any]) -> List[Dict[str, datetime]]:
    return _deserialize_slots(proposal["slots"])
