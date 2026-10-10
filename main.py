"""FestivalFlow AI - Predictive Festival Crowd and Bus Reallocation System.
Main FastAPI application entrypoint.
Reload trigger: 2026-10-11T02:27:45.
"""

import os
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from app.api.routes import router as api_router
from app.database import init_db

# Load environment configuration
load_dotenv()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Ensure SQLite database and seed records exist on startup."""
    init_db()
    yield

app = FastAPI(
    title="FestivalFlow AI",
    description="Predictive Festival Crowd and Bus Reallocation System Prototype",
    version="1.0.0",
    lifespan=lifespan
)

# CORS configuration supporting localhost & 127.0.0.1 ports
allowed_origins_env = os.environ.get("ALLOWED_ORIGINS") or os.environ.get("CORS_ORIGINS")
if allowed_origins_env:
    allowed_origins = [o.strip() for o in allowed_origins_env.split(",") if o.strip()]
else:
    allowed_origins = []

default_origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5174",
    "http://localhost:5175",
    "http://127.0.0.1:5175",
    "http://localhost:4173",
    "http://127.0.0.1:4173",
    "http://localhost:8081",
    "http://127.0.0.1:8081",
]
for origin in default_origins:
    if origin not in allowed_origins:
        allowed_origins.append(origin)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Security headers middleware
@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response

# Include all modular API routes
app.include_router(api_router)

STATIC_DIR = os.path.join(os.path.dirname(__file__), "app", "static")
ASSETS_DIR = os.path.join(STATIC_DIR, "assets")

from fastapi.staticfiles import StaticFiles
if os.path.exists(ASSETS_DIR):
    app.mount("/assets", StaticFiles(directory=ASSETS_DIR), name="assets")

@app.get("/dashboard", response_class=HTMLResponse)
@app.get("/admin", response_class=HTMLResponse)
@app.get("/admin/{path:path}", response_class=HTMLResponse)
@app.get("/driver", response_class=HTMLResponse)
@app.get("/driver/{path:path}", response_class=HTMLResponse)
def serve_dashboard(path: str = ""):
    """Serve the interactive React dashboard."""
    index_path = os.path.join(STATIC_DIR, "index.html")
    with open(index_path, "r", encoding="utf-8") as f:
        return f.read()



if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8081, reload=True)
# reload ping
