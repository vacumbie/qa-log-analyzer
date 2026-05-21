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
from parser.atak import parse_atak_log
from parser.models import ParseResult

router = APIRouter(prefix="/parse", tags=["parse"])


def _detect_format(filename: str, content: str) -> str:
    """
    Heuristically detect log format from filename and content.
    Returns 'atak', 'diagnostic', or 'rsdk'.

    Detection order:
      1. ATAK  — filename starts with 'diagnostic_ATAK_' or content is JSON
         with ATAK-specific fields (logId, connectionState, appVersion)
      2. RSDK  — filename contains 'rsdk' or content has RSDK line markers
      3. Diagnostic — fallback (goTenna Pro+ block format)
    """
    name = filename.lower()
    snippet = content[:500]

    # ── ATAK detection ────────────────────────────────────────────────────────
    # Filename convention: diagnostic_ATAK_<CALLSIGN>_<GID>_<DATE>.log
    if "diagnostic_atak_" in name:
        return "atak"
    # Content: ATAK logs are JSON arrays/objects with these distinctive fields
    if (
        '"logId"' in snippet
        or '"connectionState"' in snippet
        or '"atakVersion"' in snippet
        or '"deliveryStatus"' in snippet
    ):
        return "atak"

    # ── RSDK detection ────────────────────────────────────────────────────────
    if "rsdk" in name or "rsdk_log" in name:
        return "rsdk"
    if "Device -" in snippet and "T" in snippet[:50]:
        return "rsdk"
    if "IosBleRadio" in content or "AndroidBleRadio" in content or "GRIP_SENDER" in content:
        return "rsdk"

    # ── Diagnostic detection (goTenna Pro+ block format) ─────────────────────
    if "Device & Application Info" in content or "Message Count Details" in content:
        return "diagnostic"

    # Default fallback
    return "diagnostic"


def _result_to_dict(r: ParseResult) -> dict[str, Any]:
    """Serialize a ParseResult to a JSON-safe dict."""
    base = {
        "log_format":      r.log_format,
        "source_filename": r.source_filename,
        "parse_errors":    r.parse_errors,
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
                "from":        g.from_timestamp,
                "to":          g.to_timestamp,
                "gap_minutes": g.gap_minutes,
                "note":        g.note,
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
                "timestamp":               m.timestamp,
                "message_id":              m.message_id,
                "data_type":               m.data_type,
                "message_type":            m.message_type,
                "hop_count":               m.hop_count,
                "rssi_raw":                m.rssi_raw,
                "rssi_dbm":                m.rssi_dbm,
                "frequency_set":           m.frequency_set,
                "frames_used":             m.frames_used,
                "originator_callsign":     m.originator_callsign,
                "originator_gid":          m.originator_gid,
                "originator_location":     m.originator_location,
                "originator_pli_interval": m.originator_pli_interval,
                "originator_timestamp":    m.originator_timestamp,
                "receiver_callsign":       m.receiver_callsign,
                "receiver_gid":            m.receiver_gid,
                "receiver_pli_interval":   m.receiver_pli_interval,
            }
            for m in r.received_messages
        ],
        "message_count_snapshots": [
            {
                "timestamp":     s.timestamp,
                "pli_sent":      s.pli_sent,
                "pli_received":  s.pli_received,
                "chat_sent":     s.chat_sent,
                "chat_received": s.chat_received,
            }
            for s in r.message_count_snapshots
        ],
        "radio_stat_snapshots": [
            {
                "timestamp":              s.timestamp,
                "lifetime_uptime_hours":  s.lifetime_uptime_hours,
                "lifetime_msgs_received": s.lifetime_msgs_received,
                "lifetime_msgs_rejected": s.lifetime_msgs_rejected,
                "commands_errored":       s.commands_errored,
                "temp_threshold_events":  s.temp_threshold_events,
                "avg_uhf_rssi_db":        s.avg_uhf_rssi_db,
                "avg_ble_rssi":           s.avg_ble_rssi,
                "session_msgs_sent":      s.session_msgs_sent,
                "session_msgs_received":  s.session_msgs_received,
            }
            for s in r.radio_stat_snapshots
        ],
        "frequency_sets": [
            {
                "timestamp":        f.timestamp,
                "name":             f.name,
                "power_watts":      f.power_watts,
                "bandwidth_khz":    f.bandwidth_khz,
                "control_channels": f.control_channels,
                "data_channels":    f.data_channels,
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
                "timestamp":    t.timestamp,
                "message_id":   t.message_id,
                "outcome":      t.outcome,
                "radio_serial": t.radio_serial,
            }
            for t in r.tx_events
        ],
    }

    # ── ATAK-specific fields ──────────────────────────────────────────────────
    if r.log_format == "atak":
        base["atak_app_launches"] = [
            {
                "launch_timestamp":    a.launch_timestamp,
                "app_version":         a.app_version,
                "build_number":        a.build_number,
                "atak_version":        a.atak_version,
                "device_model":        a.device_model,
                "android_api_version": a.android_api_version,
            }
            for a in r.atak_app_launches
        ]
        base["atak_health_samples"] = [
            {
                "timestamp":                    h.timestamp,
                "serial_number":                h.serial_number,
                "connection_state":             h.connection_state,
                "battery_pct":                  h.battery_pct,
                "is_charging":                  h.is_charging,
                "connection_type":              h.connection_type,
                "mode":                         h.mode,
                "firmware_version":             h.firmware_version,
                "stored_messages":              h.stored_messages,
                "pa_temp_c":                    h.pa_temp_c,
                "pa_temp_f":                    round(h.pa_temp_c * 9 / 5 + 32) if h.pa_temp_c is not None else None,
                "system_temp_c":                h.system_temp_c,
                "system_temp_f":                round(h.system_temp_c * 9 / 5 + 32) if h.system_temp_c is not None else None,
                "transmit_power_differential":  h.transmit_power_differential,
                "hardware_version":             h.hardware_version,
                "bootloader_version":           h.bootloader_version,
                "chip_architecture":            h.chip_architecture,
                "error_code":                   h.error_code,
                "gid":                          h.gid,
            }
            for h in r.atak_health_samples
        ]
        base["atak_messages"] = [
            {
                "timestamp":          m.timestamp,
                "log_id":             m.log_id,
                "message_timestamp":  m.message_timestamp,
                "is_sender":          m.is_sender,
                "sender_gid":         m.sender_gid,
                "delivery_status":    m.delivery_status,
                "segment_count":      m.segment_count,
                "open_segments":      m.open_segments,
                "retry_count":        m.retry_count,
                "delivery_time_ms":   m.delivery_time_ms,
                "message_protocol":   m.message_protocol,
                "message_type":       m.message_type,
                "message_object_type": m.message_object_type,
                "pli_interval":       m.pli_interval,
                "file_name":          m.file_name,
                "receiver_gid":       m.receiver_gid,
                "hop_count":          m.hop_count,
                "rssi":               m.rssi,
                "rssi_is_valid":      m.rssi_is_valid,
            }
            for m in r.atak_messages
        ]
        base["atak_events"] = [
            {
                "timestamp":       e.timestamp,
                "event_type":      e.event_type,
                "serial_number":   e.serial_number,
                "connection_type": e.connection_type,
                "power_watts":     e.power_watts,
                "pli_interval_sec": e.pli_interval_sec,
                "pli_is_distance": e.pli_is_distance,
                "pli_auto_send":   e.pli_auto_send,
                "bandwidth_khz":   e.bandwidth_khz,
                "channels":        e.channels,
            }
            for e in r.atak_events
        ]

    # ── Computed summaries for the UI ─────────────────────────────────────────
    if r.log_format == "atak":
        atak_received = r.atak_received_messages
        hop_counts = [m.hop_count for m in atak_received if m.hop_count]
        rssi_vals   = [m.rssi for m in atak_received if m.rssi_is_valid]
        base["summary"] = {
            "total_messages":     len(r.atak_messages),
            "pli_count":          len(r.atak_pli_messages),
            "chat_count":         len(r.atak_chat_messages),
            "sent_count":         len(r.atak_sent_messages),
            "received_count":     len(atak_received),
            "unique_sender_gids": len(r.atak_unique_sender_gids),
            "avg_hop_count":      round(sum(hop_counts) / len(hop_counts), 2) if hop_counts else None,
            "max_hop_count":      max(hop_counts) if hop_counts else None,
            "avg_rssi":           round(sum(rssi_vals) / len(rssi_vals), 1) if rssi_vals else None,
            "peak_temp_c":        max((s.pa_temp_c for s in r.system_samples if s.pa_temp_c), default=None),
            "peak_temp_f":        round(max((s.pa_temp_c for s in r.system_samples if s.pa_temp_c), default=0) * 9 / 5 + 32) if any(s.pa_temp_c for s in r.system_samples) else None,
            "min_battery_pct":    min((h.battery_pct for h in r.atak_health_samples if h.battery_pct is not None), default=None),
            "session_count":      len(r.atak_app_launches),
            "partially_received": sum(1 for m in r.atak_messages if m.delivery_status == "PARTIALLY_RECEIVED"),
            "negative_delivery_time_count": sum(1 for m in r.atak_messages if m.delivery_time_ms is not None and m.delivery_time_ms < 0),
        }
    else:
        base["summary"] = {
            "total_messages":     len(r.received_messages),
            "pli_count":          len(r.pli_messages),
            "chat_count":         len(r.chat_messages),
            "unique_originators": len(r.unique_originators),
            "avg_hop_count":      round(sum(r.hop_counts) / len(r.hop_counts), 2) if r.hop_counts else None,
            "max_hop_count":      max(r.hop_counts) if r.hop_counts else None,
            "peak_temp_c":        max((s.pa_temp_c for s in r.system_samples if s.pa_temp_c), default=None),
            "peak_temp_f":        round(max((s.pa_temp_c for s in r.system_samples if s.pa_temp_c), default=0) * 9 / 5 + 32) if any(s.pa_temp_c for s in r.system_samples) else None,
            "min_battery_pct":    min((s.battery_pct for s in r.system_samples if s.battery_pct), default=None),
            "ble_fail_count":     len(r.ble_fail_events),
            "session_count":      len(r.session_gaps) + 1,
            "final_chat_sent":    r.final_message_counts.chat_sent if r.final_message_counts else None,
            "final_chat_recv":    r.final_message_counts.chat_received if r.final_message_counts else None,
        }

    return base


@router.post("/")
async def parse_logs(files: list[UploadFile] = File(...)) -> dict:
    """
    Upload one or more log files. Returns an array of parsed results.

    Supports goTenna Pro+ diagnostic logs, RSDK iOS/Android logs,
    and ATAK plug-in logs (regular and enhanced).
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
        suffix = ".log" if fmt == "atak" else ".txt"
        with tempfile.NamedTemporaryFile(
            suffix=suffix, delete=False, mode="w", encoding="utf-8"
        ) as tmp:
            tmp.write(text)
            tmp_path = Path(tmp.name)

        try:
            if fmt == "rsdk":
                result = parse_rsdk_log(tmp_path)
            elif fmt == "atak":
                result = parse_atak_log(tmp_path)
            else:
                result = parse_diagnostic_log(tmp_path)
            result.source_filename = upload.filename or result.source_filename
        finally:
            tmp_path.unlink(missing_ok=True)

        results.append(_result_to_dict(result))

    return {"results": results, "count": len(results)}
