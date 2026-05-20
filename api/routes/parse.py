"""
api/routes/parse.py
POST /parse  — upload one or more log files, get back structured JSON.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, HTTPException, UploadFile

# Add project root to path so the parser package is importable
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from parser.diagnostic import parse_diagnostic_log
from parser.rsdk import parse_rsdk_log
from parser.models import ParseResult

router = APIRouter(prefix="/parse", tags=["parse"])


def _detect_format(filename: str, content: str) -> str:
    """
    Heuristically detect log format from filename and content.
    Returns 'diagnostic' or 'rsdk'.
    """
    name = filename.lower()
    # RSDK logs contain ISO-8601 timestamps with T separator
    if "rsdk" in name or "rsdk_log" in name:
        return "rsdk"
    # Diagnostic format uses space-separated datetime
    if "diagnostic" in name or "2026-04-" in content[:200] or "2026-03-" in content[:200]:
        # RSDK lines start with ISO timestamp
        if "T" in content[:50] and "Device -" in content[:500]:
            return "rsdk"
        return "diagnostic"
    # Content-based fallback
    if "Device & Application Info" in content or "Message Count Details" in content:
        return "diagnostic"
    if "IosBleRadio" in content or "GRIP_SENDER" in content:
        return "rsdk"
    return "diagnostic"


def _result_to_dict(r: ParseResult) -> dict[str, Any]:
    """Serialize a ParseResult to a JSON-safe dict."""
    return {
        "log_format":     r.log_format,
        "source_filename": r.source_filename,
        "parse_errors":   r.parse_errors,
        "device": {
            "callsign":       r.device.callsign,
            "gid":            r.device.gid,
            "device_model":   r.device.device_model,
            "app_version":    r.device.app_version,
            "build_number":   r.device.build_number,
            "log_version":    r.device.log_version,
            "radio_firmware": r.device.radio_firmware,
            "radio_serial":   r.device.radio_serial,
            "platform":       r.device.platform,
        },
        "session_start": r.session_start,
        "session_end":   r.session_end,
        "session_gaps": [
            {
                "from": g.from_timestamp,
                "to":   g.to_timestamp,
                "gap_minutes": g.gap_minutes,
                "note": g.note,
            }
            for g in r.session_gaps
        ],
        "system_samples": [
            {
                "timestamp":   s.timestamp,
                "battery_pct": s.battery_pct,
                "pa_temp_c":   s.pa_temp_c,
                "pa_temp_f":   round(s.pa_temp_c * 9 / 5 + 32) if s.pa_temp_c is not None else None,
                "firmware":    s.firmware,
            }
            for s in r.system_samples
        ],
        "received_messages": [
            {
                "timestamp":             m.timestamp,
                "message_id":            m.message_id,
                "data_type":             m.data_type,
                "message_type":          m.message_type,
                "hop_count":             m.hop_count,
                "rssi_raw":              m.rssi_raw,
                "rssi_dbm":              m.rssi_dbm,
                "frequency_set":         m.frequency_set,
                "frames_used":           m.frames_used,
                "originator_callsign":   m.originator_callsign,
                "originator_gid":        m.originator_gid,
                "originator_location":   m.originator_location,
                "originator_pli_interval": m.originator_pli_interval,
                "originator_timestamp":  m.originator_timestamp,
                "receiver_callsign":     m.receiver_callsign,
                "receiver_gid":          m.receiver_gid,
                "receiver_pli_interval": m.receiver_pli_interval,
            }
            for m in r.received_messages
        ],
        "message_count_snapshots": [
            {
                "timestamp":    s.timestamp,
                "pli_sent":     s.pli_sent,
                "pli_received": s.pli_received,
                "chat_sent":    s.chat_sent,
                "chat_received": s.chat_received,
            }
            for s in r.message_count_snapshots
        ],
        "radio_stat_snapshots": [
            {
                "timestamp":                  s.timestamp,
                "lifetime_uptime_hours":      s.lifetime_uptime_hours,
                "lifetime_msgs_received":     s.lifetime_msgs_received,
                "lifetime_msgs_rejected":     s.lifetime_msgs_rejected,
                "commands_errored":           s.commands_errored,
                "temp_threshold_events":      s.temp_threshold_events,
                "avg_uhf_rssi_db":            s.avg_uhf_rssi_db,
                "avg_ble_rssi":               s.avg_ble_rssi,
                "session_msgs_sent":          s.session_msgs_sent,
                "session_msgs_received":      s.session_msgs_received,
            }
            for s in r.radio_stat_snapshots
        ],
        "frequency_sets": [
            {
                "timestamp":       f.timestamp,
                "name":            f.name,
                "power_watts":     f.power_watts,
                "bandwidth_khz":   f.bandwidth_khz,
                "control_channels": f.control_channels,
                "data_channels":   f.data_channels,
            }
            for f in r.frequency_sets
        ],
        "ble_fail_events": [
            {
                "timestamp":    b.timestamp,
                "radio_serial": b.radio_serial,
                "hour":         b.hour,
            }
            for b in r.ble_fail_events
        ],
        "tx_events": [
            {
                "timestamp":   t.timestamp,
                "message_id":  t.message_id,
                "outcome":     t.outcome,
                "radio_serial": t.radio_serial,
            }
            for t in r.tx_events
        ],
        # Computed summaries for the UI
        "summary": {
            "total_messages":    len(r.received_messages),
            "pli_count":         len(r.pli_messages),
            "chat_count":        len(r.chat_messages),
            "unique_originators": len(r.unique_originators),
            "avg_hop_count":     round(sum(r.hop_counts) / len(r.hop_counts), 2) if r.hop_counts else None,
            "max_hop_count":     max(r.hop_counts) if r.hop_counts else None,
            "peak_temp_c":       max((s.pa_temp_c for s in r.system_samples if s.pa_temp_c), default=None),
            "peak_temp_f":       round(max((s.pa_temp_c for s in r.system_samples if s.pa_temp_c), default=0) * 9 / 5 + 32) if any(s.pa_temp_c for s in r.system_samples) else None,
            "min_battery_pct":   min((s.battery_pct for s in r.system_samples if s.battery_pct), default=None),
            "ble_fail_count":    len(r.ble_fail_events),
            "session_count":     len(r.session_gaps) + 1,
            "final_chat_sent":   r.final_message_counts.chat_sent if r.final_message_counts else None,
            "final_chat_recv":   r.final_message_counts.chat_received if r.final_message_counts else None,
        },
    }


@router.post("/")
async def parse_logs(files: list[UploadFile] = File(...)) -> dict:
    """
    Upload one or more log files. Returns an array of parsed results.

    Supports both diagnostic (.txt from goTenna Pro+) and RSDK (.txt from SDK).
    Format is auto-detected from filename and content.
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded.")
    if len(files) > 20:
        raise HTTPException(status_code=400, detail="Maximum 20 files per request.")

    results = []
    for upload in files:
        content = await upload.read()
        text = content.decode("utf-8", errors="replace")

        fmt = _detect_format(upload.filename or "", text)

        # Write to a temp file so the parsers can use Path
        with tempfile.NamedTemporaryFile(
            suffix=".txt", delete=False, mode="w", encoding="utf-8"
        ) as tmp:
            tmp.write(text)
            tmp_path = Path(tmp.name)

        try:
            if fmt == "rsdk":
                result = parse_rsdk_log(tmp_path)
            else:
                result = parse_diagnostic_log(tmp_path)
            result.source_filename = upload.filename or result.source_filename
        finally:
            tmp_path.unlink(missing_ok=True)

        results.append(_result_to_dict(result))

    return {"results": results, "count": len(results)}
