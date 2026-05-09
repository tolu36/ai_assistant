from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from app.routes import schedule, brief, llm, preferences, status
from config import APP_ACCESS_TOKEN

app = FastAPI(title="Personal AI Assistant")
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Include routers for different features
app.include_router(schedule.router, prefix="/schedule", tags=["Scheduler"])
app.include_router(brief.router, prefix="/brief", tags=["Brief Generator"])
app.include_router(llm.router, prefix="/llm", tags=["LLM"])
app.include_router(preferences.router, prefix="/preferences", tags=["Preferences"])
app.include_router(status.router, prefix="/status", tags=["Status"])


@app.middleware("http")
async def require_app_access_token(request, call_next):
    if not APP_ACCESS_TOKEN:
        return await call_next(request)

    public_paths = ("/", "/static")
    if request.url.path == "/" or request.url.path.startswith(public_paths[1]):
        return await call_next(request)

    token = request.headers.get("x-app-token", "")
    if token != APP_ACCESS_TOKEN:
        return JSONResponse(
            status_code=401,
            content={"detail": "Missing or invalid app access token."},
        )

    return await call_next(request)


@app.get("/")
def read_root():
    return FileResponse("app/static/index.html")
