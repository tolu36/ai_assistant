import json
import logging
import os
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import urlsplit, urlunsplit

from app.services.tts import TextToSpeechError, generate_mistral_speech, tts_status
from config import (
    BRIEF_AUDIO_DIR,
    BRIEF_AUDIO_OBJECT_ACCESS_KEY_ID,
    BRIEF_AUDIO_OBJECT_BUCKET,
    BRIEF_AUDIO_OBJECT_ENDPOINT_URL,
    BRIEF_AUDIO_OBJECT_PREFIX,
    BRIEF_AUDIO_OBJECT_REGION,
    BRIEF_AUDIO_OBJECT_SECRET_ACCESS_KEY,
    BRIEF_AUDIO_RETENTION_DAYS,
    MISTRAL_TTS_MAX_CHARS,
    MORNING_BRIEF_PREGENERATE_AUDIO,
    OUTBOUND_HTTP_TRUST_ENV,
)

LOGGER = logging.getLogger(__name__)

SECTION_ORDER = ("daily_quote", "news", "sports", "finance")
SECTION_LABELS = {
    "daily_quote": "Daily Note",
    "news": "News",
    "sports": "Sports",
    "finance": "Finance",
}


class BriefAudioError(RuntimeError):
    pass


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    return value.lower() in ("1", "true", "yes")


def prebuild_audio_enabled() -> bool:
    return _env_bool("MORNING_BRIEF_PREGENERATE_AUDIO", MORNING_BRIEF_PREGENERATE_AUDIO)


def _base_dir() -> Path:
    return Path(os.getenv("BRIEF_AUDIO_DIR", BRIEF_AUDIO_DIR))


def _object_bucket() -> str:
    return os.getenv("BRIEF_AUDIO_OBJECT_BUCKET", BRIEF_AUDIO_OBJECT_BUCKET).strip()


def _object_prefix() -> str:
    return os.getenv("BRIEF_AUDIO_OBJECT_PREFIX", BRIEF_AUDIO_OBJECT_PREFIX).strip("/")


def _object_endpoint_url() -> str:
    value = os.getenv(
        "BRIEF_AUDIO_OBJECT_ENDPOINT_URL",
        BRIEF_AUDIO_OBJECT_ENDPOINT_URL,
    ).strip()
    parsed = urlsplit(value)
    if parsed.scheme and parsed.netloc:
        return urlunsplit((parsed.scheme, parsed.netloc, "", "", ""))
    return value


def _object_region() -> str:
    return os.getenv("BRIEF_AUDIO_OBJECT_REGION", BRIEF_AUDIO_OBJECT_REGION).strip()


def _object_access_key_id() -> str:
    return os.getenv(
        "BRIEF_AUDIO_OBJECT_ACCESS_KEY_ID",
        BRIEF_AUDIO_OBJECT_ACCESS_KEY_ID,
    ).strip()


def _object_secret_access_key() -> str:
    return os.getenv(
        "BRIEF_AUDIO_OBJECT_SECRET_ACCESS_KEY",
        BRIEF_AUDIO_OBJECT_SECRET_ACCESS_KEY,
    ).strip()


def _use_object_storage() -> bool:
    return bool(_object_bucket())


def _object_client():
    import boto3
    from botocore.config import Config

    options: Dict[str, Any] = {
        "service_name": "s3",
        "config": Config(
            signature_version="s3v4",
            proxies=None if OUTBOUND_HTTP_TRUST_ENV else {},
        ),
    }
    endpoint_url = _object_endpoint_url()
    region = _object_region()
    access_key_id = _object_access_key_id()
    secret_access_key = _object_secret_access_key()

    if endpoint_url:
        options["endpoint_url"] = endpoint_url
    if region:
        options["region_name"] = region
    if access_key_id:
        options["aws_access_key_id"] = access_key_id
    if secret_access_key:
        options["aws_secret_access_key"] = secret_access_key

    return boto3.client(**options)


def _object_key(brief_id: int | str, filename: str = "") -> str:
    parts = [_object_prefix(), _safe_id(brief_id), filename.strip("/")]
    return "/".join(part for part in parts if part)


def _retention_days() -> int:
    value = os.getenv("BRIEF_AUDIO_RETENTION_DAYS", str(BRIEF_AUDIO_RETENTION_DAYS))
    try:
        return max(1, int(value))
    except ValueError:
        return BRIEF_AUDIO_RETENTION_DAYS


def _safe_id(value: int | str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value)).strip("._-")
    return safe or "brief"


def _brief_dir(brief_id: int | str) -> Path:
    return _base_dir() / _safe_id(brief_id)


def _manifest_path(brief_id: int | str) -> Path:
    return _brief_dir(brief_id) / "manifest.json"


def _parse_created_at(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _brief_audio_created_at(path: Path) -> datetime:
    manifest_path = path / "manifest.json"
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            created_at = _parse_created_at(manifest.get("created_at"))
            if created_at:
                return created_at
        except (OSError, json.JSONDecodeError):
            pass
    return datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)


def cleanup_expired_brief_audio(retention_days: int | None = None) -> Dict[str, int]:
    days = retention_days if retention_days is not None else _retention_days()
    cutoff_seconds = max(1, int(days)) * 86400
    now = datetime.now(timezone.utc)

    if _use_object_storage():
        prefix = _object_prefix()
        if prefix:
            prefix = f"{prefix.rstrip('/')}/"
        deleted = 0
        kept = 0
        continuation_token = None
        client = _object_client()

        while True:
            kwargs = {"Bucket": _object_bucket(), "Prefix": prefix}
            if continuation_token:
                kwargs["ContinuationToken"] = continuation_token
            response = client.list_objects_v2(**kwargs)
            for item in response.get("Contents", []):
                last_modified = item.get("LastModified")
                if not last_modified:
                    kept += 1
                    continue
                if last_modified.tzinfo is None:
                    last_modified = last_modified.replace(tzinfo=timezone.utc)
                age_seconds = (now - last_modified.astimezone(timezone.utc)).total_seconds()
                if age_seconds >= cutoff_seconds:
                    client.delete_object(Bucket=_object_bucket(), Key=item["Key"])
                    deleted += 1
                else:
                    kept += 1
            if not response.get("IsTruncated"):
                break
            continuation_token = response.get("NextContinuationToken")
        return {"deleted": deleted, "kept": kept}

    root = _base_dir()
    if not root.exists():
        return {"deleted": 0, "kept": 0}

    deleted = 0
    kept = 0

    for child in root.iterdir():
        if not child.is_dir():
            continue
        try:
            age_seconds = (now - _brief_audio_created_at(child)).total_seconds()
            if age_seconds >= cutoff_seconds:
                shutil.rmtree(child)
                deleted += 1
            else:
                kept += 1
        except OSError as exc:
            LOGGER.warning("Could not inspect cached brief audio at %s: %s", child, exc)

    return {"deleted": deleted, "kept": kept}


def _clean_speech_text(value: Any) -> str:
    cleaned = re.sub(r"https?://\S+", " ", str(value or ""))
    replacements = {
        r"\bETFs\b": "E.T.F.s",
        r"\bETF\b": "E.T.F.",
        r"\bLLMs\b": "L.L.M.s",
        r"\bLLM\b": "L.L.M.",
        r"\bRSS\b": "R.S.S.",
        r"\bAI\b": "A.I.",
        r"\bGDP\b": "G.D.P.",
        r"\bCPI\b": "C.P.I.",
        r"\bTSX\b": "T.S.X.",
        r"\bS&P\b": "S and P",
        r"\bCAD/USD\b": "Canadian dollar to U.S. dollar",
    }
    for pattern, replacement in replacements.items():
        cleaned = re.sub(pattern, replacement, cleaned)
    cleaned = re.sub(r"[*_`#>]+", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def _item_speech_text(item: Any) -> str:
    if not item:
        return ""
    if not isinstance(item, dict):
        return _clean_speech_text(item)

    parts: List[str] = []
    title = item.get("title")
    if title and title != "Daily Quote":
        parts.append(str(title))
    if item.get("summary"):
        parts.append(str(item["summary"]))
    reflection = item.get("reflection") or item.get("prompt")
    if reflection:
        parts.append(f"Reflection. {reflection}")
    if item.get("why_it_matters"):
        parts.append(f"Why it matters. {item['why_it_matters']}")
    if item.get("watch_for"):
        parts.append(f"Watch for. {item['watch_for']}")
    return ". ".join(filter(None, (_clean_speech_text(part) for part in parts)))


def _section_speech_text(title: str, items: List[Any]) -> str:
    lines = [_item_speech_text(item) for item in items or []]
    lines = [line for line in lines if line]
    if not lines:
        return ""
    return _clean_speech_text(f"{title}. {' '.join(lines)}")


def _daily_note_speech_text(items: List[Any]) -> str:
    item = next((entry for entry in items or [] if isinstance(entry, dict)), None)
    if not item:
        return ""

    parts: List[str] = []
    if item.get("summary"):
        parts.append(f"Daily note. {item['summary']}")
    reflection = item.get("reflection") or item.get("prompt")
    if reflection:
        parts.append(f"Reflection. {reflection}")
    return " ".join(filter(None, (_clean_speech_text(part) for part in parts)))


def _finance_groups(items: List[Any]) -> Dict[str, List[Any]]:
    groups: Dict[str, List[Any]] = {
        "context": [],
        "financial_news": [],
        "market_watch": [],
    }
    for item in items or []:
        if not isinstance(item, dict):
            groups["context"].append(item)
        elif item.get("section") == "financial_news":
            groups["financial_news"].append(item)
        elif item.get("section") == "market_watch":
            groups["market_watch"].append(item)
        elif item.get("category") == "Financial news" or item.get("impact_area"):
            groups["financial_news"].append(item)
        else:
            groups["market_watch"].append(item)
    return groups


def _finance_speech_text(items: List[Any]) -> str:
    groups = _finance_groups(items or [])
    parts = [
        _section_speech_text("Finance context", groups["context"]),
        _section_speech_text("Financial news and macro trends", groups["financial_news"]),
        _section_speech_text("Companies, stocks, and E.T.F.s to watch", groups["market_watch"]),
    ]
    parts = [part for part in parts if part]
    if not parts:
        return ""
    return _clean_speech_text(f"Finance. {' '.join(parts)}")


def brief_speech_sections(brief: Dict[str, Any]) -> Dict[str, str]:
    return {
        "daily_quote": _daily_note_speech_text(brief.get("daily_quote") or []),
        "news": _section_speech_text("News", brief.get("news") or []),
        "sports": _section_speech_text("Sports", brief.get("sports") or []),
        "finance": _finance_speech_text(brief.get("finance") or []),
    }


def split_speech_text(text: str, max_chars: int | None = None) -> List[str]:
    configured_limit = int(os.getenv("MISTRAL_TTS_MAX_CHARS", str(MISTRAL_TTS_MAX_CHARS)))
    limit = max_chars or min(1100, configured_limit)
    limit = max(200, limit)
    clean = _clean_speech_text(text)
    sentences = re.findall(r"[^.!?]+[.!?]*", clean) or [clean]
    chunks: List[str] = []
    current = ""

    for sentence in sentences:
        trimmed = sentence.strip()
        if not trimmed:
            continue

        if len(trimmed) > limit:
            word_chunk = ""
            for word in trimmed.split():
                candidate = f"{word_chunk} {word}".strip()
                if len(candidate) > limit and word_chunk:
                    chunks.append(word_chunk)
                    word_chunk = word
                else:
                    word_chunk = candidate
            if word_chunk:
                chunks.append(word_chunk)
            continue

        candidate = f"{current} {trimmed}".strip()
        if len(candidate) > limit and current:
            chunks.append(current)
            current = trimmed
        else:
            current = candidate

    if current:
        chunks.append(current)
    return chunks


def load_brief_audio_manifest(brief_id: int | str) -> Dict[str, Any] | None:
    if _use_object_storage():
        try:
            response = _object_client().get_object(
                Bucket=_object_bucket(),
                Key=_object_key(brief_id, "manifest.json"),
            )
            return json.loads(response["Body"].read().decode("utf-8"))
        except Exception as exc:
            response = getattr(exc, "response", {})
            error_code = ""
            if isinstance(response, dict):
                error_code = response.get("Error", {}).get("Code", "")
            if error_code in ("NoSuchKey", "404", "NotFound"):
                return None
            LOGGER.warning("Could not load brief audio manifest from object storage: %s", exc)
            return None

    path = _manifest_path(brief_id)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def get_brief_audio_chunk(
    brief_id: int | str,
    section: str,
    chunk_index: int,
) -> Dict[str, Any] | None:
    manifest = load_brief_audio_manifest(brief_id)
    if not manifest:
        return None
    track = (manifest.get("tracks") or {}).get(section)
    if not track:
        return None
    for chunk in track.get("chunks") or []:
        if int(chunk.get("index", 0)) == int(chunk_index):
            if _use_object_storage():
                try:
                    response = _object_client().get_object(
                        Bucket=_object_bucket(),
                        Key=_object_key(brief_id, str(chunk.get("filename", ""))),
                    )
                    return {
                        "audio": response["Body"].read(),
                        "metadata": chunk,
                    }
                except Exception as exc:
                    LOGGER.warning("Could not load brief audio chunk from object storage: %s", exc)
                    return None

            path = _brief_dir(brief_id) / str(chunk.get("filename", ""))
            if path.exists() and path.is_file():
                return {"path": path, "metadata": chunk}
    return None


def generate_brief_audio(
    brief: Dict[str, Any],
    brief_id: int | str,
    overwrite: bool = False,
) -> Dict[str, Any]:
    status = tts_status()
    if not status["enabled"]:
        raise BriefAudioError("Mistral API key is not configured.")

    existing = load_brief_audio_manifest(brief_id)
    if existing and not overwrite:
        return existing

    brief_dir = _brief_dir(brief_id)
    if not _use_object_storage():
        brief_dir.mkdir(parents=True, exist_ok=True)

    manifest: Dict[str, Any] = {
        "version": 1,
        "brief_id": str(brief_id),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "provider": "mistral",
        "model": status["model"],
        "response_format": status["response_format"],
        "media_type": status["media_type"],
        "tracks": {},
    }

    speech_sections = brief_speech_sections(brief)
    for section in SECTION_ORDER:
        text = speech_sections.get(section, "")
        chunks = split_speech_text(text)
        if not chunks:
            continue

        track = {
            "label": SECTION_LABELS[section],
            "chunks": [],
        }
        for index, chunk_text in enumerate(chunks, start=1):
            try:
                audio = generate_mistral_speech(chunk_text)
            except TextToSpeechError as exc:
                raise BriefAudioError(str(exc)) from exc

            response_format = str(audio["response_format"])
            filename = f"{section}-{index:03d}.{response_format}"
            audio_bytes = bytes(audio["audio"])
            if _use_object_storage():
                _object_client().put_object(
                    Bucket=_object_bucket(),
                    Key=_object_key(brief_id, filename),
                    Body=audio_bytes,
                    ContentType=str(audio["media_type"]),
                )
            else:
                target = brief_dir / filename
                temporary = brief_dir / f"{filename}.tmp"
                temporary.write_bytes(audio_bytes)
                temporary.replace(target)
            track["chunks"].append(
                {
                    "index": index,
                    "filename": filename,
                    "bytes": len(audio_bytes),
                    "media_type": audio["media_type"],
                    "response_format": response_format,
                }
            )
        manifest["tracks"][section] = track

    if not manifest["tracks"]:
        raise BriefAudioError("Morning brief did not contain speech-ready text.")

    manifest_json = json.dumps(manifest, indent=2, sort_keys=True)
    if _use_object_storage():
        _object_client().put_object(
            Bucket=_object_bucket(),
            Key=_object_key(brief_id, "manifest.json"),
            Body=manifest_json.encode("utf-8"),
            ContentType="application/json",
        )
    else:
        manifest_file = _manifest_path(brief_id)
        temporary_manifest = manifest_file.with_suffix(".json.tmp")
        temporary_manifest.write_text(manifest_json, encoding="utf-8")
        temporary_manifest.replace(manifest_file)
    return manifest


def ensure_brief_audio(
    brief: Dict[str, Any],
    brief_id: int | str,
    overwrite: bool = False,
) -> Dict[str, Any]:
    if not prebuild_audio_enabled():
        return {"available": False, "status": "disabled"}
    if not tts_status()["enabled"]:
        return {"available": False, "status": "not_configured"}

    cleanup_expired_brief_audio()

    try:
        manifest = generate_brief_audio(brief, brief_id, overwrite=overwrite)
    except Exception as exc:
        LOGGER.warning("Could not prebuild morning brief audio: %s", exc)
        return {"available": False, "status": "error", "error": str(exc)}

    return {"available": True, "status": "ready", "manifest": manifest}


def brief_audio_status(brief_id: int | str) -> Dict[str, Any]:
    manifest = load_brief_audio_manifest(brief_id)
    if not manifest:
        return {"available": False, "status": "missing"}
    tracks = manifest.get("tracks") or {}
    chunk_count = sum(len(track.get("chunks") or []) for track in tracks.values())
    return {
        "available": chunk_count > 0,
        "status": "ready" if chunk_count > 0 else "missing",
        "track_count": len(tracks),
        "chunk_count": chunk_count,
    }
