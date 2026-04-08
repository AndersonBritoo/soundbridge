#!/usr/bin/env python3
# =============================================================
#  SoundBridge – FastAPI Backend
#  Path: api/main.py
#  Main application entry point
#
#  Run
#  ---
#  uvicorn api.main:app --reload --port 8000
#  – or –
#  python api/main.py
#
#  Endpoints
#  ---------
#  POST /morse          Accept event or legacy word payload
#  GET  /morse          List all stored messages
#  GET  /morse/{id}     Retrieve a single message
#  GET  /health         Liveness probe
#
#  Stop with Ctrl-C.
# =============================================================

from fastapi import FastAPI

# Initialize dotenv
from dotenv import load_dotenv
load_dotenv()

from api.core.config import setup_logging, AppConfig
from api.db.connection import lifespan
from api.routes.morse import router as morse_router


# Initialize logging
setup_logging()


# Create FastAPI application
app = FastAPI(
    title=AppConfig.TITLE,
    description=AppConfig.DESCRIPTION,
    version=AppConfig.VERSION,
    lifespan=lifespan,
)


# Register routers
app.include_router(morse_router, tags=["morse"])


# =============================================================
#  Development runner
# =============================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)