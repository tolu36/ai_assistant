from fastapi import APIRouter, HTTPExceptionfrom pydantic import BaseModel, Field

from app.services.calendar import create_event
from app.services.llm_parser import parse_task
from app.services.scheduler import find_best_slot, propose_slots
from app.services.schedule_feedback import remember_feedback_constraint
from app.services.schedule_store import (
    create_proposal,
    get_proposal,
    mark_proposal_confirmed,
    proposal_slots_as_datetimes,
    update_proposal_slots,
)

router = APIRouter()


class ScheduleRequest(BaseModel):
    task: str


class ConfirmProposalRequest(BaseModel):
    slot_indexes: list[int] | None = None


class ReviseProposalRequest(BaseModel):
    feedback: str = Field(min_length=1)


@router.post("/task")
async def schedule_task(request: ScheduleRequest):
    task_text = request.task.strip()
    if not task_text:
        raise HTTPException(status_code=400, detail="Task text must not be empty.")

    parsed = parse_task(task_text)
    slot = find_best_slot(parsed)

    created_event = create_event(
        title=parsed["title"],
        start=slot["start"],
        end=slot["end"],
        description=parsed["description"],
    )

    return {
        "status": "scheduled",
        "task": parsed["title"],
        "duration_minutes": parsed["duration_minutes"],
        "scheduled_start": slot["start"].isoformat(),
        "scheduled_end": slot["end"].isoformat(),
        "event": created_event,
    }


@router.post("/propose")
async def propose_schedule(request: ScheduleRequest):
    task_text = request.task.strip()
    if not task_text:
        raise HTTPException(status_code=400, detail="Task text must not be empty.")

    parsed = parse_task(task_text)
    slots = propose_slots(parsed)
    proposal = create_proposal(task_text, parsed, slots)

    return {
        "status": "proposal",
        "proposal_id": proposal["id"],
        "task": parsed["title"],
        "duration_minutes": parsed["duration_minutes"],
        "frequency_days_per_week": parsed.get("frequency_days_per_week"),
        "ambiguity_flags": parsed.get("ambiguity_flags", []),
        "suggested_slots": [
            {
                "start": slot["start"].isoformat(),
                "end": slot["end"].isoformat(),
            }
            for slot in slots
        ],
        "next_step": "Review these times. If any are bad, explain why and ask for a revised proposal.",
    }


@router.post("/proposal/{proposal_id}/confirm")
async def confirm_schedule_proposal(proposal_id: str, request: ConfirmProposalRequest):
    proposal = get_proposal(proposal_id)
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found.")

    slots = proposal_slots_as_datetimes(proposal)
    selected_indexes = request.slot_indexes if request.slot_indexes is not None else list(range(len(slots)))
    selected_slots = []
    for index in selected_indexes:
        if index < 0 or index >= len(slots):
            raise HTTPException(status_code=400, detail=f"Invalid slot index: {index}")
        selected_slots.append(slots[index])

    parsed = proposal["parsed"]
    created_events = []
    for slot in selected_slots:
        created_events.append(
            create_event(
                title=parsed["title"],
                start=slot["start"],
                end=slot["end"],
                description=parsed.get("description", parsed["title"]),
            )
        )

    mark_proposal_confirmed(proposal_id)
    return {
        "status": "confirmed",
        "proposal_id": proposal_id,
        "created_events": created_events,
    }


@router.post("/proposal/{proposal_id}/revise")
async def revise_schedule_proposal(proposal_id: str, request: ReviseProposalRequest):
    proposal = get_proposal(proposal_id)
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found.")

    learned_constraint = remember_feedback_constraint(request.feedback)
    parsed = proposal["parsed"]
    revised_slots = propose_slots(parsed)
    updated = update_proposal_slots(proposal_id, revised_slots, feedback=request.feedback)

    return {
        "status": "revised",
        "proposal_id": proposal_id,
        "learned_constraint": learned_constraint,
        "suggested_slots": updated["slots"] if updated else [],
        "next_step": "Review the revised times. Confirm the proposal if these work.",
y are bad, explain why and ask for a revised proposal.",
),
        "event": created_event,
    }
