from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import asyncio
from monitor import monitor
from config import settings
from database import init_db, get_recent_outages

app = FastAPI(title="Connectivity Monitor")

# Mount static files (if any)
app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")

@app.on_event("startup")
async def startup_event():
    # Initialize DB
    await init_db()
    # Start the background monitoring task
    asyncio.create_task(monitor.start_polling())

@app.get("/", response_class=HTMLResponse)
async def get_index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "settings": settings})

@app.get("/components/outages", response_class=HTMLResponse)
async def get_outages_component(request: Request):
    outages = await get_recent_outages(10)
    return templates.TemplateResponse("partials/outages_panel.html", {
        "request": request,
        "outages": outages
    })

@app.get("/api/stats")
async def get_stats():
    if not monitor.history:
        return {"status": "no data", "history": []}
    
    latest = monitor.history[-1]
    return {
        "latest": latest,
        "history": list(monitor.history)[-60:] # Return last 60 seconds for the chart
    }

@app.get("/components/status", response_class=HTMLResponse)
async def get_status_component(request: Request):
    """HTMX component for real-time status updates."""
    latest = monitor.history[-1] if monitor.history else None
    return templates.TemplateResponse("partials/status_grid.html", {
        "request": request, 
        "latest": latest
    })

@app.get("/components/connection", response_class=HTMLResponse)
async def get_connection_component(request: Request):
    """HTMX component for WiFi connection details."""
    return templates.TemplateResponse("partials/connection_details.html", {
        "request": request,
        "wifi_info": monitor.wifi_info
    })
