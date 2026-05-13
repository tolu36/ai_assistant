from copy import deepcopy
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.services.brief_audio import (
    BriefAudioError,
    generate_brief_audio,
    get_brief_audio_chunk,
    load_brief_audio_manifest,
)
from app.services.brief_history import get_morning_brief as get_saved_morning_brief
from app.services.tts import TextToSpeechError, generate_mistral_speech, tts_status

router = APIRouter()


class SpeechRequest(BaseModel):
    text: str = Field(min_length=1)


@router.get("/status")
def get_tts_status():
    return tts_status()


def _manifest_with_urls(brief_id: str, manifest: dict) -> dict:
    response = deepcopy(manifest)
    safe_brief_id = quote(str(brief_id), safe="")
    for section, track in (response.get("tracks") or {}).items():
        safe_section = quote(str(section), safe="")
        for chunk in track.get("chunks") or []:
            chunk["url"] = (
                f"/tts/brief/{safe_brief_id}/{safe_section}/{int(chunk['index'])}"
            )
    return response


@router.get("/brief/{brief_id}")
def get_saved_brief_audio_manifest(brief_id: str):
    manifest = load_brief_audio_manifest(brief_id)
    if not manifest:
        raise HTTPException(status_code=404, detail="Saved audio is not available yet.")
    return _manifest_with_urls(brief_id, manifest)


@router.post("/brief/{brief_id}")
def create_saved_brief_audio(brief_id: str):
    saved = get_saved_morning_brief(brief_id)
    if not saved:
        raise HTTPException(status_code=404, detail="Morning brief not found.")
    try:
        manifest = generate_brief_audio(saved.get("brief") or {}, brief_id)
    except BriefAudioError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return _manifest_with_urls(brief_id, manifest)


@router.get("/brief/{brief_id}/{section}/{chunk_index}")
def get_saved_brief_audio_chunk(brief_id: str, section: str, chunk_index: int):
    result = get_brief_audio_chunk(brief_id, section, chunk_index)
    if not result:
        raise HTTPException(status_code=404, detail="Saved audio chunk not found.")
    chunk = result["metadata"]
    headers = {
        "Cache-Control": "private, max-age=86400",
        "X-Audio-Format": str(chunk.get("response_format", "mp3")),
    }
    if "audio" in result:
        return Response(
            content=result["audio"],
            media_type=str(chunk.get("media_type", "audio/mpeg")),
            headers=headers,
        )

    return FileResponse(
        result["path"],
        media_type=str(chunk.get("media_type", "audio/mpeg")),
        headers=headers,
    )


@router.post("/speech")
def create_speech(request: SpeechRequest):
    try:
        result = generate_mistral_speech(request.text)
    except TextToSpeechError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return Response(
        content=result["audio"],
        media_type=result["media_type"],
        headers={
            "Cache-Control": "no-store",
            "X-Audio-Format": str(result["response_format"]),
        },
    )
