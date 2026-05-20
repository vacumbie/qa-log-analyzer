"""
api/main.py
FastAPI application entry point.

Start with:
    uvicorn main:app --reload --port 8000
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routes.parse import router as parse_router
from routes.export import router as export_router

app = FastAPI(
    title="goTenna Log Analyzer API",
    description="Parse and analyze goTenna diagnostic and RSDK log files.",
    version="0.1.0",
)

# Allow the Vite dev server to call the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(parse_router)
app.include_router(export_router)


@app.get("/health")
def health():
    return {"status": "ok", "version": "0.1.0"}
