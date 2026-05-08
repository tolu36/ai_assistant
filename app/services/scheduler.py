import loggingffrom datetime import datetime, timedeltafrom typing import Any, Dict, List

from app.services.calendar import list_busy_slotsfrom app.services import schedule_store
from config import SCHEDULER_DAY_END_HOUR, SCHEDULER_DAY_START_HOUR, SCHEDULER_DEFAULT_HOUR, TIMEZONE

LOGGER = logging.getLogger(__name__)


def _to_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value


def _within_working_hours(start: datetime, duration_minutes: int) -> bool:
    end = start + timedelta(minutes=duration_minutes)
    day_start = start.replace(hour=SCHEDULER_DAY_START_HOUR, minute=0, second=0, microsecond=0)
    day_end = start.replace(hour=SCHEDULER_DAY_END_HOUR, minute=0, second=0, microsecond=0)
    return start >= day_start and end <= day_end


def _violates_constraints(start: datetime, duration_minutes: int) -> bool:
    end = start + timedelta(minutes=duration_minutes)
    for constraint in schedule_store.list_constraints():
 list_constraints():
        start_hour = constraint.get("start_hour")
        end_hour = constraint.get("end_hour")
        if start_hour is None or end_hour is None:
            continue
        blocked_start = start.replace(hour=int(start_hour), minute=0, second=0, microsecond=0)
        blocked_end = start.replace(hour=int(end_hour), minute=0, second=0, microsecond=0)
        if blocked_end <= blocked_start:
            blocked_end = blocked_end + timedelta(days=1)
        if start < blocked_end and end > blocked_start:
            return True
    return False


def _next_schedulable_slot(after: datetime, duration_minutes: int) -> datetime:
    candidate = after.replace(second=0, microsecond=0)
    if candidate.minute:
        candidate = candidate + timedelta(minutes=60 - candidate.minute)

    day_start = candidate.replace(hour=SCHEDULER_DAY_START_HOUR, minute=0, second=0, microsecond=0)
    day_end = candidate.replace(hour=SCHEDULER_DAY_END_HOUR, minute=0, second=0, microsecond=0)

    if candidate < day_start:
        return day_start
    if candidate + timedelta(minutes=duration_minutes) > day_end:
        return (candidate + timedelta(days=1)).replace(
            hour=SCHEDULER_DEFAULT_HOUR,
            minute=0,
            second=0,
            microsecond=0,
        )
    return candidate


def find_best_slot(task_data: Dict[str, Any], search_days: int = 7) -> Dict[str, datetime]:
    requested_start = task_data.get("start_datetime")
    duration = task_data.get("duration_minutes", 60)
    if requested_start is None:
        requested_start = _next_schedulable_slot(datetime.now(), duration)

    target_start = requested_start
    target_end = target_start + timedelta(minutes=duration)

    if not _within_working_hours(target_start, duration):
        target_start = _next_schedulable_slot(target_start, duration)
        target_end = target_start + timedelta(minutes=duration)

    try:
        busy = list_busy_slots(target_start, target_start + timedelta(days=search_days))
    except Exception as exc:
        LOGGER.warning("Could not read calendar busy slots, using requested time directly: %s", exc)
        return {"start": target_start, "end": target_end}

    busy = sorted(busy, key=lambda event: event["start"])
    candidate = _next_schedulable_slot(max(target_start, datetime.now()), duration)

    for event in busy:
        if not _within_working_hours(candidate, duration):
            candidate = _next_schedulable_slot(candidate, duration)
        if candidate + timedelta(minutes=duration) <= event["start"]:
            return {"start": candidate, "end": candidate + timedelta(minutes=duration)}
        if event["end"] > candidate:
            candidate = _next_schedulable_slot(event["end"], duration)

    return {"start": candidate, "end": candidate + timedelta(minutes=duration)}


def propose_slots(task_data: Dict[str, Any], count: int | None = None, search_days: int = 14) -> List[Dict[str, datetime]]:
    duration = task_data.get("duration_minutes", 60)
    target_count = count or task_data.get("frequency_days_per_week") or 1
    target_count = max(1, min(14, int(target_count)))
    requested_start = task_data.get("start_datetime") or _next_schedulable_slot(datetime.now(), duration)

    try:
        busy = list_busy_slots(requested_start, requested_start + timedelta(days=search_days))
    except Exception as exc:
        LOGGER.warning("Could not read calendar busy slots for proposal: %s", exc)
        busy = []

    busy = sorted(busy, key=lambda event: event["start"])
    proposals = []
    candidate = _next_schedulable_slot(max(requested_start, datetime.now()), duration)

    while len(proposals) < target_count and candidate < requested_start + timedelta(days=search_days):
        candidate = _next_schedulable_slot(candidate, duration)
        candidate_end = candidate + timedelta(minutes=duration)

        conflicting_event = None
        for event in busy:
            if candidate < event["end"] and candidate_end > event["start"]:
                conflicting_event = event
                break

        if conflicting_event:
            candidate = _next_schedulable_slot(conflicting_event["end"], duration)
            continue

        if _violates_constraints(candidate, duration):
            candidate = _next_schedulable_slot(candidate + timedelta(hours=1), duration)
flicting_event:
            candidate = _next_schedulable_slot(conflicting_event["end"], duration)
            continue

        proposals.append({"start": candidate, "end": candidate_end})
        candidate = _next_schedulable_slot(candidate + timedelta(days=1), duration)

    return proposals
date = _next_default_slot(event["end"])

            candidate = event["end"]

    return {"start": candidate, "end": candidate + timedelta(minutes=duration)}
