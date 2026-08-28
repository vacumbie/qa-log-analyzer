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

# Valid CSV export types per log format.
# relay_manager and fw_log are intentionally JSON-only: their data is nested
# summary/health structure (relay health requests, RHC buckets, RF config) rather
# than the flat per-row tables CSV expects. Use /export/{id}/json for those.
_CSV_TYPES = {
    "diagnostic": {"received_messages", "system_samples", "tx_events", "ble_fail_events"},
    "rsdk":       {"system_samples", "tx_events", "ble_fail_events"},
    "atak":       {"atak_messages", "atak_health_samples", "atak_events", "atak_app_launches", "system_samples"},
    # tak_events is a flat per-row table (one CoT event per row), so unlike
    # relay_manager and fw_log it is a natural CSV export. raw_cot is not
    # serialized by the API, so the XML column is absent by design.
    "tak":        {"tak_events"},
    # Next-gen radio. Both formats are per-row tables rather than the nested
    # summary structure that makes relay_manager and fw_log JSON-only, so they
    # get entries — but two tables carry one nested column each, and
    # csv.DictWriter stringifies those into a single unusable cell:
    #   tx_packets.transmissions      — list of RF confirmations per packet
    #   stat_snapshots.output_overhead / .output_xmit_completion
    #                                 — RouterHistogramBucket objects
    # They are still exported, because dropping the two headline tables to
    # avoid one awkward column each would be the worse trade. Use
    # /export/{id}/json when you need those columns structured.
    "htmodem":    {"tx_packets", "temp_samples_f", "freq_changes", "power_changes"},
    "htrouter":   {"stat_snapshots", "protocol_messages", "forward_events", "transmissions"},
}


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
    filename = data.get("source_filename", "export").replace(".txt", "").replace(".log", "")
    return Response(
        content=json.dumps(data, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}.json"'},
    )


@router.get("/{session_id}/csv")
def export_csv(session_id: str, data_type: str = "received_messages") -> StreamingResponse:
    """
    Download a specific data slice as CSV.

    Valid data_type values by log format:
      diagnostic : received_messages | system_samples | tx_events | ble_fail_events
      rsdk       : system_samples | tx_events | ble_fail_events
      atak       : atak_messages | atak_health_samples | atak_events |
                   atak_app_launches | system_samples
      tak        : tak_events
      htmodem    : tx_packets | temp_samples_f | freq_changes | power_changes
      htrouter   : stat_snapshots | protocol_messages | forward_events |
                   transmissions

    relay_manager and fw_log are JSON-only — see the note on _CSV_TYPES, which
    also lists the two next-gen tables carrying a nested column.
    """
    session = _store.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    log_format = session.get("log_format", "diagnostic")
    valid_types = _CSV_TYPES.get(log_format, set())

    if data_type not in valid_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid data_type '{data_type}' for {log_format} log. "
                   f"Valid options: {sorted(valid_types)}",
        )

    # Most formats serialize their tables at the top level of the result, but
    # htmodem and htrouter nest theirs under a per-format block
    # (base["htmodem"], base["htrouter"]) — see _result_to_dict(). Looking only
    # at the top level made every next-gen entry below 400 while /types happily
    # advertised all eight. Checking the nested block second keeps the payload
    # as-is rather than duplicating 2,585-row tables to satisfy the lookup.
    rows = session.get(data_type)
    if rows is None:
        nested = session.get(log_format)
        if isinstance(nested, dict):
            rows = nested.get(data_type)
    if rows is None:
        raise HTTPException(status_code=400, detail=f"Unknown data_type '{data_type}'.")
    if not rows:
        raise HTTPException(status_code=404, detail=f"No data for type '{data_type}'.")

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)

    source = session.get("source_filename", "export").replace(".txt", "").replace(".log", "")
    filename = f"{source}_{data_type}.csv"
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode()),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{session_id}/types")
def export_types(session_id: str) -> dict:
    """Return the valid CSV export types for this session's log format."""
    session = _store.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    log_format = session.get("log_format", "diagnostic")
    return {
        "log_format":  log_format,
        "valid_types": sorted(_CSV_TYPES.get(log_format, set())),
    }


@router.delete("/{session_id}")
def clear_session(session_id: str) -> dict:
    """Remove a stored session to free memory."""
    _store.pop(session_id, None)
    return {"deleted": session_id}
