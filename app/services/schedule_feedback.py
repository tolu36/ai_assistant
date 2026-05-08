import re
from typing import Any, Dict

from app.services.schedule_store import add_constraint


def _parse_hour(text: str) -> int | None:
    match = re.search(r"\b(\d{1,2})(?::\d{2})?\s*(am|pm)?\b", text.lower())
    if not match:
        return None

    hour = int(match.group(1))
    suffix = match.group(2)
    if suffix == "pm" and hour != 12:
        hour += 12
    if suffix == "am" and hour == 12:
        hour = 0
    return max(0, min(23, hour))


def remember_feedback_constraint(feedback: str) -> Dict[str, Any] | None:
    text = feedback.lower()

    if any(word in text for word in ("sleep", "asleep", "sleeping", "too late", "late night", "3 am")):
        return add_constraint(
            reason="avoid_sleep_hours",
            start_hour=22,
            end_hour=9,
            raw_feedback=feedback,
        )

    if "too early" in text or "early morning" in text:
        return add_constraint(
            reason="avoid_early_morning",
            start_hour=0,
            end_hour=9,
            raw_feedback=feedback,
        )

    if "not before" in text or "after" in text:
        hour = _parse_hour(text)
        if hour is not None:
            return add_constraint(
                reason="not_before_time",
                start_hour=0,
                end_hour=hour,
                raw_feedback=feedback,
            )

    if "not after" in text or "before" in text:
        hour = _parse_hour(text)
        if hour is not None:
            return add_constraint(
                reason="not_after_time",
                start_hour=hour,
                end_hour=23,
                raw_feedback=feedback,
            )

    return None
