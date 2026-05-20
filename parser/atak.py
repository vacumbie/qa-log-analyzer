"""
parser/atak.py
Parses the goTenna Android ATAK plug-in log format.

Both regular (user) and enhanced (debug) logs share the same JSON structure:
newline-delimited JSON objects, one per line, optionally wrapped in [ ].

Regular logs accumulate across multiple app launches without being cleared.
Enhanced logs typically cover a single session.

Usage:
    from parser.atak import parse_atak_log
    result = parse_atak_log(Path("diagnostic_ATAK_HOTEL_90215634664458_2026-03-04.log"))
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .models import (
    ParseResult, DeviceInfo, SystemSample, SessionGap,
    AtakMessage, AtakDeviceHealth, AtakEvent, AtakAppInfo,
)

_TS_FMT_OUT = "%Y-%m-%d %H:%M:%S.%f"

# Filename pattern: diagnostic_ATAK_<CALLSIGN>_<GID>_<YYYY-MM-DD>_<HH_MM_SS_mmm>.log
_FILENAME_RE = re.compile(
    r"diagnostic_ATAK_(?P<callsign>[^_]+)_(?P<gid>\d+)_"
    r"(?P<date>\d{4}-\d{2}-\d{2})_(?P<time>\d{2}_\d{2}_\d{2}_\d+)\.log"
)


# ── Timestamp helpers ─────────────────────────────────────────────────────────

def _ms_to_str(ms: int) -> str:
    """Convert Unix epoch milliseconds to output timestamp string."""
    dt = datetime.fromtimestamp(ms / 1000, tz=timezone.utc).replace(tzinfo=None)
    return dt.strftime(_TS_FMT_OUT)


# ── Record type detection ─────────────────────────────────────────────────────

def _record_type(record: dict) -> str:
    """Identify which of the 4 ATAK record types this record is."""
    if "appVersion" in record:
        return "app_info"
    if "connectionState" in record:
        return "device_health"
    if "logId" in record:
        return "message"
    if "event" in record:
        return "event"
    return "unknown"


# ── Per-type handlers ─────────────────────────────────────────────────────────

def _handle_app_info(record: dict, result: ParseResult) -> None:
    launch_ts = record.get("launchTimeInMillis")
    app_info = AtakAppInfo(
        launch_timestamp=_ms_to_str(launch_ts) if launch_ts else "",
        app_version=record.get("appVersion", ""),
        build_number=record.get("buildNumber"),
        atak_version=record.get("atakVersion", ""),
        device_model=record.get("deviceInfo", {}).get("deviceModel", ""),
        android_api_version=record.get("deviceInfo", {}).get("apiVersion"),
    )
    result.atak_app_launches.append(app_info)

    # Populate DeviceInfo from first launch record
    if not result.device.app_version:
        result.device.app_version = app_info.app_version
        result.device.build_number = str(app_info.build_number or "")
        result.device.device_model = app_info.device_model
        result.device.platform = "android"


def _handle_device_health(record: dict, result: ParseResult) -> None:
    ts = record.get("timestampInMillis")
    if not ts:
        return

    # Sentinel guards:
    # transmitPowerDifferential=255 → not yet valid
    # systemTemperature=0 during CONNECTING → placeholder
    conn_state = record.get("connectionState", "")
    raw_tpd = record.get("transmitPowerDifferential")
    tpd = None if raw_tpd == 255 else raw_tpd

    raw_sys_temp = record.get("systemTemperature")
    sys_temp = None if (raw_sys_temp == 0 and conn_state == "CONNECTING") else raw_sys_temp

    battery = record.get("batteryLevel")
    pa_temp = record.get("powerAmpTemperature")

    health = AtakDeviceHealth(
        timestamp=_ms_to_str(ts),
        serial_number=record.get("serialNumber", ""),
        connection_state=conn_state,
        battery_pct=battery if battery is not None and battery >= 0 else None,
        is_charging=record.get("isCharging", False),
        connection_type=record.get("connectionType", ""),
        mode=record.get("mode", ""),
        firmware_version=record.get("firmwareVersion", ""),
        stored_messages=record.get("storedMessages", 0),
        pa_temp_c=pa_temp if pa_temp is not None and pa_temp >= 0 else None,
        system_temp_c=sys_temp if sys_temp is not None and sys_temp >= 0 else None,
        transmit_power_differential=tpd,
        hardware_version=record.get("hardwareVersion"),
        bootloader_version=record.get("bootloaderVersion"),
        chip_architecture=record.get("chipArchitecture", ""),
        error_code=record.get("errorCode", ""),
        gid=record.get("gid"),
    )
    result.atak_health_samples.append(health)

    # Also emit a SystemSample for cross-format compatibility
    if health.battery_pct is not None and health.pa_temp_c is not None:
        result.system_samples.append(SystemSample(
            timestamp=health.timestamp,
            battery_pct=health.battery_pct,
            pa_temp_c=health.pa_temp_c,
            firmware=health.firmware_version,
        ))

    # Capture radio identity from first health record
    if not result.device.radio_serial and health.serial_number:
        result.device.radio_serial = health.serial_number
    if not result.device.radio_firmware and health.firmware_version:
        result.device.radio_firmware = health.firmware_version
    if not result.device.gid and health.gid:
        result.device.gid = str(health.gid)


def _handle_message(record: dict, result: ParseResult) -> None:
    ts = record.get("timestampInMillis")
    msg_ts = record.get("messageTimestampInMillis")
    if not ts:
        return

    msg = record.get("message", {})
    msg_type = msg.get("type", "")
    obj_type = msg.get("objectType", "")

    # delivery_time_ms can legitimately be negative (clock skew between devices)
    delivery_ms = record.get("deliveryTimeInMillis")

    atak_msg = AtakMessage(
        timestamp=_ms_to_str(ts),
        log_id=record.get("logId"),
        message_timestamp=_ms_to_str(msg_ts) if msg_ts else "",
        is_sender=record.get("isSender", False),
        sender_gid=record.get("senderGid"),
        delivery_status=record.get("deliveryStatus", ""),
        segment_count=record.get("segmentCount", 1),
        open_segments=record.get("numberOfOpenSegments", 0),
        retry_count=record.get("retryCount", 0),
        delivery_time_ms=delivery_ms,
        message_protocol=record.get("messageProtocol", ""),
        message_type=msg_type,
        message_object_type=obj_type,
        pli_interval=msg.get("interval", "") if msg_type == "pli" else "",
        file_name=msg.get("fileName", "") if msg_type == "fileTransfer" else "",
        receiver_gid=record.get("receiverGid"),
        hop_count=record.get("hopCount"),
        rssi=record.get("rssi"),
    )
    result.atak_messages.append(atak_msg)

    # Capture device GID from first sent message
    if not result.device.gid and atak_msg.is_sender and atak_msg.sender_gid:
        result.device.gid = str(atak_msg.sender_gid)


def _handle_event(record: dict, result: ParseResult) -> None:
    ts = record.get("timestampInMillis")
    event = record.get("event", {})
    event_type = event.get("type", "")
    if not ts or not event_type:
        return

    atak_event = AtakEvent(
        timestamp=_ms_to_str(ts),
        event_type=event_type,
    )

    if event_type == "deviceConnected":
        atak_event.serial_number = event.get("serialNumber", "")
        atak_event.connection_type = event.get("connectionType", "")

    elif event_type == "deviceDisconnected":
        atak_event.connection_type = event.get("connectionType", "")

    elif event_type == "powerLevelUpdated":
        atak_event.power_watts = event.get("power")

    elif event_type == "pliSettingUpdated":
        atak_event.pli_interval_sec = event.get("interval")
        atak_event.pli_is_distance = event.get("isDistance")
        atak_event.pli_auto_send = event.get("isAutoSend")

    elif event_type == "frequencyUpdated":
        atak_event.power_watts = event.get("power")
        atak_event.bandwidth_khz = event.get("bandwidth")
        atak_event.channels = event.get("channels", [])

    result.atak_events.append(atak_event)


# ── Filename parsing ──────────────────────────────────────────────────────────

def _parse_filename(filename: str, result: ParseResult) -> None:
    """Extract callsign and GID from the standard ATAK log filename."""
    m = _FILENAME_RE.match(filename)
    if m:
        if not result.device.callsign:
            result.device.callsign = m.group("callsign")
        if not result.device.gid:
            result.device.gid = m.group("gid")


# ── Session gap detection ─────────────────────────────────────────────────────

def _detect_session_gaps(result: ParseResult, gap_threshold_min: int = 30) -> None:
    """Find breaks > gap_threshold_min between consecutive message timestamps."""
    all_ts: list[datetime] = []

    for m in result.atak_messages:
        try:
            all_ts.append(datetime.strptime(m.timestamp, _TS_FMT_OUT))
        except ValueError:
            pass
    for h in result.atak_health_samples:
        try:
            all_ts.append(datetime.strptime(h.timestamp, _TS_FMT_OUT))
        except ValueError:
            pass

    if not all_ts:
        return

    all_ts.sort()
    result.session_start = all_ts[0].strftime(_TS_FMT_OUT)
    result.session_end = all_ts[-1].strftime(_TS_FMT_OUT)

    for i in range(1, len(all_ts)):
        delta_min = (all_ts[i] - all_ts[i - 1]).total_seconds() / 60
        if delta_min > gap_threshold_min:
            result.session_gaps.append(SessionGap(
                from_timestamp=all_ts[i - 1].strftime(_TS_FMT_OUT),
                to_timestamp=all_ts[i].strftime(_TS_FMT_OUT),
                gap_minutes=round(delta_min, 1),
            ))


# ── JSON loading ──────────────────────────────────────────────────────────────

def _load_records(text: str, result: ParseResult) -> list[dict]:
    """
    Parse newline-delimited JSON records from log text.
    Handles both bare JSON lines and [ ]-wrapped arrays.
    Skips malformed lines and logs them as parse errors.
    """
    records = []
    text = text.strip()

    # Strip outer [ ] if present
    if text.startswith("["):
        text = text[1:]
    if text.endswith("]"):
        text = text[:-1]

    for i, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip().rstrip(",")
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as e:
            result.parse_errors.append(f"Line {i}: JSON parse error — {e}")

    return records


# ── Public entry point ────────────────────────────────────────────────────────

def parse_atak_log(path: Path) -> ParseResult:
    """
    Parse a goTenna ATAK plug-in log file (regular or enhanced).

    Both log types share the same JSON format. Regular logs accumulate
    across multiple app launches; enhanced logs are typically single-session.

    Args:
        path: Path to the ATAK .log file.

    Returns:
        ParseResult populated with all extracted data.
    """
    result = ParseResult(
        log_format="atak",
        source_filename=path.name,
    )

    # Extract callsign and GID from filename before reading content
    _parse_filename(path.name, result)

    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        result.parse_errors.append(f"Could not read file: {e}")
        return result

    records = _load_records(text, result)

    for record in records:
        rtype = _record_type(record)
        try:
            if rtype == "app_info":
                _handle_app_info(record, result)
            elif rtype == "device_health":
                _handle_device_health(record, result)
            elif rtype == "message":
                _handle_message(record, result)
            elif rtype == "event":
                _handle_event(record, result)
            # "unknown" records are silently skipped
        except Exception as e:
            result.parse_errors.append(
                f"Error processing {rtype} record at ts="
                f"{record.get('timestampInMillis', '?')}: {e}"
            )

    _detect_session_gaps(result)
    return result
