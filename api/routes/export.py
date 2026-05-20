"""
api/routes/export.py
GET /export  — download a previously-parsed result as CSV or JSON.

The frontend posts to /parse first, stores the result in memory,
then calls /export/{session_id} to download.
"""

from __future__ import annotations

import csv
import io
import json
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response, StreamingResponse

router = APIRouter(prefix="/export", tags=["export"])

# In-memory session store: { session_id: parsed_result_dict }
# Simple enough for a local tool; no persistence needed.
_store: dict[str, Any] = {}


@router.post("/session")
def store_session(data: dict) -> dict:
    """Store a parsed result and return a session_id for later export."""
    session_id = str(uuid.uuid4())
    _store[session_id] = data
    return {"session_id": session_id}


@router.get("/{session_id}/json")
def export_json(session_id: str) -> Response:
    """Download the full parsed result as JSON."""
    data = _store.get(session_id)
    if not data:
        raise HTTPException(status_code=404, detail="Session not found.")
    filename = data.get("source_filename", "export").replace(".txt", "")
    return Response(
        content=json.dumps(data, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}.json"'},
    )


@router.get("/{session_id}/csv")
def export_csv(session_id: str, data_type: str = "received_messages") -> StreamingResponse:
    """
    Download a specific data slice as CSV.
    data_type options: received_messages | system_samples | ble_fail_events | tx_events
    """
    session = _store.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    rows = session.get(data_type)
    if rows is None:
        raise HTTPException(status_code=400, detail=f"Unknown data_type '{data_type}'.")
    if not rows:
        raise HTTPException(status_code=404, detail="No data for this type.")

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)

    filename = f"{session.get('source_filename','export').replace('.txt','')}_{data_type}.csv"
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode()),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.delete("/{session_id}")
def clear_session(session_id: str) -> dict:
    """Remove a stored session to free memory."""
    _store.pop(session_id, None)
    return {"deleted": session_id}
