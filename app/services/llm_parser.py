import json
import logging
import os
import re
import threading
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import dateparser
from config import (
    LLAMA_CPP_MODEL_PATH,
    MISTRAL_API_KEY,
    MISTRAL_API_URL,
    MISTRAL_MIN_SECONDS_BETWEEN_REQUESTS,
    MISTRAL_MODEL,
    MODEL_DEVICE,
    MODEL_FALLBACK_PROVIDER,
    MODEL_MAX_TOKENS,
    MODEL_NAME,
    MODEL_PROVIDER,
    MODEL_TEMPERATURE,
    OUTBOUND_HTTP_TRUST_ENV,
    TIMEZONE,
)

LOGGER = logging.getLogger(__name__)
_MODEL_CLIENTS: Dict[str, Any] = {}
_MODEL_LOAD_ERRORS: Dict[str, str] = {}
_MISTRAL_LAST_REQUEST_AT = 0.0
_MISTRAL_LOCK = threading.Lock()

_PARSE_PROMPT = """
You are a scheduling assistant.
Extract a JSON object from the user request with the following fields:
- title: short task name
- description: optional task details
- start_datetime: ISO 8601 timestamp in the user's timezone, or null if not explicit
- end_datetime: ISO 8601 timestamp in the user's timezone, or null if not explicit
- duration_minutes: integer task duration in minutes, or null if not explicit
- frequency_days_per_week: integer 1-7 if the user asks for a weekly recurring habit, or null
Return only valid JSON.
User instruction: {instruction}
"""


def _model_provider() -> str:
    return os.getenv("MODEL_PROVIDER", MODEL_PROVIDER).lower()


def _model_fallback_provider() -> str:
    return os.getenv("MODEL_FALLBACK_PROVIDER", MODEL_FALLBACK_PROVIDER).lower()


def _provider_chain() -> List[str]:
    primary = _model_provider()
    if primary in ("fallback", "none", ""):
        return []

    providers = [primary]
    fallback = _model_fallback_provider()
    if fallback not in ("fallback", "none", "", primary):
        providers.append(fallback)
    return providers


def _model_name() -> str:
    return os.getenv("OPEN_SOURCE_MODEL", MODEL_NAME)


def _model_max_tokens() -> int:
    return int(os.getenv("MODEL_MAX_TOKENS", str(MODEL_MAX_TOKENS)))


def _model_temperature() -> float:
    return float(os.getenv("MODEL_TEMPERATURE", str(MODEL_TEMPERATURE)))


def _model_device() -> str:
    return os.getenv("MODEL_DEVICE", MODEL_DEVICE)


def _mistral_model() -> str:
    return os.getenv("MISTRAL_MODEL", MISTRAL_MODEL)


def _mistral_api_key() -> str:
    return os.getenv("MISTRAL_API_KEY", MISTRAL_API_KEY)


def _extract_json(text: str) -> Optional[str]:
    decoder = json.JSONDecoder()
    for matcher in re.finditer(r"\{", text):
        candidate = text[matcher.start() :]
        try:
            _, end = decoder.raw_decode(candidate)
            return candidate[:end]
        except json.JSONDecodeError:
            continue
    return None


def _coerce_datetime(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        parsed = dateparser.parse(
            value,
            settings={
                "TIMEZONE": TIMEZONE,
                "RETURN_AS_TIMEZONE_AWARE": True,
                "PREFER_DATES_FROM": "future",
            },
        )
        return parsed
    return None


def _parse_duration_text(text: str) -> Optional[int]:
    text = text.lower().strip()

    patterns = [
        (r"(\d+(?:\.\d+)?)\s*hours?", 60),
        (r"(\d+(?:\.\d+)?)\s*hrs?", 60),
        (r"(\d+(?:\.\d+)?)\s*h\b", 60),
        (r"(\d+(?:\.\d+)?)\s*minutes?", 1),
        (r"(\d+(?:\.\d+)?)\s*mins?", 1),
        (r"(\d+(?:\.\d+)?)\s*m\b", 1),
    ]

    for pattern, multiplier in patterns:
        match = re.search(pattern, text)
        if match:
            value = float(match.group(1))
            return int(value * multiplier)

    if "half hour" in text or "half an hour" in text or "30 minutes" in text:
        return 30

    return None


def _parse_frequency_days_per_week(text: str) -> Optional[int]:
    lowered = text.lower().strip()
    match = re.search(r"(\d+)\s*(?:days?|times?)\s*(?:a|per)?\s*week", lowered)
    if match:
        return max(1, min(7, int(match.group(1))))

    word_numbers = {
        "once": 1,
        "twice": 2,
        "one": 1,
        "two": 2,
        "three": 3,
        "four": 4,
        "five": 5,
        "six": 6,
        "seven": 7,
    }
    for word, value in word_numbers.items():
        if re.search(rf"\b{word}\b\s*(?:days?|times?)\s*(?:a|per)?\s*week", lowered):
            return value

    if "daily" in lowered or "every day" in lowered:
        return 7

    return None


def _has_datetime_signal(text: str) -> bool:
    lowered = text.lower()
    keywords = [
        "today",
        "tonight",
        "tomorrow",
        "morning",
        "afternoon",
        "evening",
        "night",
        "after work",
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
        "saturday",
        "sunday",
    ]
    if any(keyword in lowered for keyword in keywords):
        return True
    if re.search(r"\bat\s+\d{1,2}(?::\d{2})?\s*(?:am|pm)?\b", lowered):
        return True
    if re.search(r"\b\d{1,2}/\d{1,2}(?:/\d{2,4})?\b", lowered):
        return True
    return False


def _parse_time_of_day_hint(text: str, base: datetime) -> Optional[datetime]:
    lowered = text.lower()
    candidate = None

    if "tonight" in lowered:
        candidate = base.replace(hour=19, minute=0, second=0, microsecond=0)
        if candidate <= base:
            candidate = candidate + timedelta(days=1)
    elif "tomorrow morning" in lowered:
        candidate = (base + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
    elif "tomorrow afternoon" in lowered:
        candidate = (base + timedelta(days=1)).replace(hour=13, minute=0, second=0, microsecond=0)
    elif "tomorrow evening" in lowered or "tomorrow night" in lowered:
        candidate = (base + timedelta(days=1)).replace(hour=18, minute=0, second=0, microsecond=0)
    elif "tomorrow" in lowered:
        candidate = (base + timedelta(days=1)).replace(hour=18, minute=0, second=0, microsecond=0)
    elif "after work" in lowered:
        candidate = base.replace(hour=17, minute=30, second=0, microsecond=0)
        if candidate <= base:
            candidate = candidate + timedelta(days=1)
    elif "morning" in lowered:
        candidate = base.replace(hour=9, minute=0, second=0, microsecond=0)
        if candidate <= base:
            candidate = candidate + timedelta(days=1)
    elif "afternoon" in lowered:
        candidate = base.replace(hour=13, minute=0, second=0, microsecond=0)
        if candidate <= base:
            candidate = candidate + timedelta(days=1)
    elif "evening" in lowered:
        candidate = base.replace(hour=18, minute=0, second=0, microsecond=0)
        if candidate <= base:
            candidate = candidate + timedelta(days=1)

    return candidate


def _parse_datetime_text(text: str) -> Optional[datetime]:
    base = datetime.now()
    hinted = _parse_time_of_day_hint(text, base)
    if hinted is not None:
        return hinted

    parsed = dateparser.parse(
        text,
        settings={
            "TIMEZONE": TIMEZONE,
            "RETURN_AS_TIMEZONE_AWARE": True,
            "PREFER_DATES_FROM": "future",
            "RELATIVE_BASE": base,
        },
    )
    return parsed


def _ambiguity_flags(text: str, start: Optional[datetime], duration: Optional[int]) -> List[str]:
    flags = []
    lowered = text.lower()

    if duration is None:
        flags.append("missing_duration")
    if start is None:
        flags.append("missing_start")
    if any(phrase in lowered for phrase in ("sometime", "later", "soon", "when i can")):
        flags.append("vague_time")

    return flags


def _default_start() -> datetime:
    now = datetime.now()
    candidate = now + timedelta(minutes=15)
    candidate = candidate.replace(second=0, microsecond=0)
    if candidate.hour >= 22:
        candidate = candidate + timedelta(days=1)
        candidate = candidate.replace(hour=18, minute=0)
    return candidate


def _fallback_parse_task(text: str) -> Dict[str, Any]:
    parsed_duration = _parse_duration_text(text)
    duration = parsed_duration or 60
    frequency_days_per_week = _parse_frequency_days_per_week(text)
    start = _parse_datetime_text(text)
    flags = _ambiguity_flags(text, start, parsed_duration)
    if start is None:
        start = _default_start()
    end = start + timedelta(minutes=duration)
    return {
        "title": text.strip(),
        "description": text.strip(),
        "start_datetime": start,
        "end_datetime": end,
        "duration_minutes": duration,
        "frequency_days_per_week": frequency_days_per_week,
        "ambiguity_flags": flags,
        "parser_provider": "fallback",
    }


def _load_model(provider: Optional[str] = None) -> Any:
    provider = provider or _model_provider()
    if provider in _MODEL_CLIENTS:
        return _MODEL_CLIENTS[provider]

    _MODEL_LOAD_ERRORS.pop(provider, None)

    if provider == "llama_cpp":
        try:
            from llama_cpp import Llama

            model_path = os.getenv("LLAMA_CPP_MODEL_PATH", LLAMA_CPP_MODEL_PATH) or _model_name()
            client = Llama(model_path=model_path, n_ctx=2048)
            _MODEL_CLIENTS[provider] = client
            return client
        except Exception as exc:
            _MODEL_LOAD_ERRORS[provider] = str(exc)
            LOGGER.warning("llama_cpp could not be loaded: %s", exc)
            return None

    if provider == "transformers":
        try:
            from transformers import AutoModelForCausalLM, AutoTokenizer
            import torch

            tokenizer = AutoTokenizer.from_pretrained(_model_name(), trust_remote_code=True)
            device = _model_device()
            if device == "auto":
                device = "cuda" if torch.cuda.is_available() else "cpu"
            torch_dtype = torch.float16 if device == "cuda" else torch.float32
            model = AutoModelForCausalLM.from_pretrained(
                _model_name(),
                dtype=torch_dtype,
                trust_remote_code=True,
            )
            model.to(device)
            model.eval()
            client = {"tokenizer": tokenizer, "model": model, "device": device}
            _MODEL_CLIENTS[provider] = client
            return client
        except Exception as exc:
            _MODEL_LOAD_ERRORS[provider] = str(exc)
            LOGGER.warning("Transformers model could not be loaded: %s", exc)
            return None

    if provider == "mistral":
        if not _mistral_api_key():
            _MODEL_LOAD_ERRORS[provider] = "MISTRAL_API_KEY is not configured."
            return None
        client = {"provider": "mistral"}
        _MODEL_CLIENTS[provider] = client
        return client

    return None


def _generate_text(prompt: str, provider: Optional[str] = None) -> str:
    provider = provider or _model_provider()
    client = _load_model(provider)
    if client is None:
        raise RuntimeError(f"{provider} backend is not configured or available.")

    if provider == "llama_cpp":
        result = client.create(
            prompt=prompt,
            max_tokens=_model_max_tokens(),
            temperature=_model_temperature(),
        )
        if isinstance(result, dict):
            return result["choices"][0]["text"]
        return result.choices[0].text

    if provider == "transformers":
        import torch

        tokenizer = client["tokenizer"]
        model = client["model"]
        device = client["device"]
        messages = [{"role": "user", "content": prompt}]
        model_input = tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )
        inputs = tokenizer([model_input], return_tensors="pt").to(device)
        temperature = _model_temperature()
        with torch.no_grad():
            generated = model.generate(
                **inputs,
                max_new_tokens=_model_max_tokens(),
                temperature=temperature,
                do_sample=temperature > 0,
                pad_token_id=tokenizer.eos_token_id,
            )
        output_ids = generated[0][inputs.input_ids.shape[-1] :]
        return tokenizer.decode(output_ids, skip_special_tokens=True)

    if provider == "mistral":
        return _generate_mistral_text(prompt)

    raise RuntimeError(f"Unsupported model provider: {provider}")


def _generate_mistral_text(prompt: str) -> str:
    global _MISTRAL_LAST_REQUEST_AT

    import httpx

    api_key = _mistral_api_key()
    if not api_key:
        raise RuntimeError("MISTRAL_API_KEY is not configured.")

    with _MISTRAL_LOCK:
        elapsed = time.monotonic() - _MISTRAL_LAST_REQUEST_AT
        wait_seconds = MISTRAL_MIN_SECONDS_BETWEEN_REQUESTS - elapsed
        if wait_seconds > 0:
            time.sleep(wait_seconds)
        _MISTRAL_LAST_REQUEST_AT = time.monotonic()

    with httpx.Client(timeout=30, trust_env=OUTBOUND_HTTP_TRUST_ENV) as client:
        response = client.post(
            os.getenv("MISTRAL_API_URL", MISTRAL_API_URL),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": _mistral_model(),
                "messages": [{"role": "user", "content": prompt}],
                "temperature": _model_temperature(),
                "max_tokens": _model_max_tokens(),
            },
        )
    response.raise_for_status()
    content = response.json()["choices"][0]["message"]["content"]
    if isinstance(content, list):
        return "".join(chunk.get("text", "") for chunk in content if isinstance(chunk, dict))
    return content


def generate_llm_text(prompt: str) -> str:
    last_error = None
    for provider in _provider_chain():
        try:
            return _generate_text(prompt, provider)
        except Exception as exc:
            last_error = exc
            LOGGER.warning("LLM provider %s failed, trying next fallback: %s", provider, exc)

    raise RuntimeError(f"No LLM provider succeeded: {last_error}")


def _parse_with_model(text: str, provider: str) -> Optional[Dict[str, Any]]:
    try:
        prompt = _PARSE_PROMPT.format(instruction=text)
        raw = _generate_text(prompt, provider)
        json_text = _extract_json(raw)
        if not json_text:
            return None
        parsed = json.loads(json_text)
        title = parsed.get("title") or text.strip()
        description = parsed.get("description") or text.strip()
        start = _coerce_datetime(parsed.get("start_datetime"))
        end = _coerce_datetime(parsed.get("end_datetime"))
        duration_from_text = _parse_duration_text(text)
        frequency_from_text = _parse_frequency_days_per_week(text)
        duration = duration_from_text or parsed.get("duration_minutes")
        frequency_days_per_week = frequency_from_text or parsed.get("frequency_days_per_week")
        if not _has_datetime_signal(text):
            start = None
            end = None
        explicit_start = start
        if duration is None and start and end:
            duration = int((end - start).total_seconds() / 60)
        if duration is None:
            duration = _parse_duration_text(text)
        if start is None and duration is not None:
            start = _parse_datetime_text(text)
        if start is None:
            start = _default_start()
        if end is None and duration is not None:
            end = start + timedelta(minutes=int(duration))

        return {
            "title": title,
            "description": description,
            "start_datetime": start,
            "end_datetime": end,
            "duration_minutes": int(duration) if duration is not None else 60,
            "frequency_days_per_week": int(frequency_days_per_week) if frequency_days_per_week else None,
            "ambiguity_flags": _ambiguity_flags(text, explicit_start, duration_from_text),
            "parser_provider": provider,
        }
    except Exception as exc:
        LOGGER.warning("LLM parse failed with %s, trying next fallback: %s", provider, exc)
        return None


def parse_task(text: str) -> Dict[str, Any]:
    text = text.strip()
    if not text:
        raise ValueError("Task text is required")

    task = None
    for provider in _provider_chain():
        task = _parse_with_model(text, provider)
        if task:
            break
    if not task:
        task = _fallback_parse_task(text)

    if task["start_datetime"] and task["end_datetime"]:
        if task["start_datetime"] >= task["end_datetime"]:
            task["end_datetime"] = task["start_datetime"] + timedelta(minutes=task["duration_minutes"])

    return task


def get_llm_status(check: bool = False) -> Dict[str, Any]:
    provider = _model_provider()
    providers = _provider_chain()
    provider_statuses = []
    for item in providers:
        if check:
            _load_model(item)
        provider_statuses.append(
            {
                "provider": item,
                "model_name": _mistral_model() if item == "mistral" else _model_name(),
                "device": "api" if item == "mistral" else _model_device(),
                "loaded": item in _MODEL_CLIENTS,
                "last_error": _MODEL_LOAD_ERRORS.get(item),
            }
        )

    status = {
        "provider": provider,
        "enabled": provider != "fallback",
        "model_name": _mistral_model() if provider == "mistral" else _model_name(),
        "max_tokens": _model_max_tokens(),
        "temperature": _model_temperature(),
        "device": "api" if provider == "mistral" else _model_device(),
        "loaded": provider in _MODEL_CLIENTS,
        "last_error": _MODEL_LOAD_ERRORS.get(provider),
        "fallback_provider": _model_fallback_provider(),
        "provider_chain": providers + ["deterministic"],
        "providers": provider_statuses,
    }

    return status
