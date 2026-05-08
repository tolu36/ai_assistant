from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from app.routes import schedule, brief, llm, preferences

app = FastAPI(title="Personal AI Assistant")
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Include routers for different features
app.include_router(schedule.router, prefix="/schedule", tags=["Scheduler"])
app.include_router(brief.router, prefix="/brief", tags=["Brief Generator"])
app.include_router(llm.router, prefix="/llm", tags=["LLM"])
app.include_router(preferences.router, prefix="/preferences", tags=["Preferences"])


@app.get("/")
def read_root():
    return FileResponse("app/static/index.html")
