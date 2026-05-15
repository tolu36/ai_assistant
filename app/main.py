import hmac
import os

import config
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from app.routes import schedule, brief, llm, notifications, preferences, status, tts

app = FastAPI(title="Personal AI Assistant")
app.mount("/static", StaticFiles(directory="app/static"), name="static")

PRIVATE_API_PREFIXES = (
    "/brief",
    "/llm",
    "/preferences",
    "/schedule",
    "/status",
    "/tts",
    "/notifications",
)


def _app_access_token() -> str:
    value = os.getenv("APP_ACCESS_TOKEN")
    if value is not None:
        return value.strip()
    return config.APP_ACCESS_TOKEN.strip()


@app.middleware("http")
async def require_app_access_token(request: Request, call_next):
    expected = _app_access_token()
    if not expected or request.method == "OPTIONS":
        return await call_next(request)

    path = request.url.path
    if not any(path == prefix or path.startswith(f"{prefix}/") for prefix in PRIVATE_API_PREFIXES):
        return await call_next(request)

    supplied = request.headers.get("X-App-Token", "")
    authorization = request.headers.get("Authorization", "")
    if authorization.lower().startswith("bearer "):
        supplied = authorization[7:].strip()

    if hmac.compare_digest(supplied, expected):
        return await call_next(request)

    return JSONResponse(
        {"detail": "App access token is required."},
        status_code=401,
        headers={"WWW-Authenticate": "Bearer"},
    )

# Include routers for different features
app.include_router(schedule.router, prefix="/schedule", tags=["Scheduler"])
app.include_router(brief.router, prefix="/brief", tags=["Brief Generator"])
app.include_router(llm.router, prefix="/llm", tags=["LLM"])
app.include_router(tts.router, prefix="/tts", tags=["Text to Speech"])
app.include_router(notifications.router, prefix="/notifications", tags=["Notifications"])
app.include_router(preferences.router, prefix="/preferences", tags=["Preferences"])
app.include_router(status.router, prefix="/status", tags=["Status"])


@app.get("/")
def read_root():
    return FileResponse("app/static/index.html")


@app.get("/manifest.webmanifest", include_in_schema=False)
def read_manifest():
    return FileResponse(
        "app/static/manifest.webmanifest",
        media_type="application/manifest+json",
    )


@app.get("/service-worker.js", include_in_schema=False)
def read_service_worker():
    return FileResponse(
        "app/static/service-worker.js",
        media_type="application/javascript",
        headers={"Cache-Control": "no-cache"},
    )
