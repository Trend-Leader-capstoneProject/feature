from fastapi import FastAPI
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    debug=settings.debug,
)

@app.get("/")
async def root():
    return {
        "success": True,
        "message": "Trend Leader API is running",    
    }