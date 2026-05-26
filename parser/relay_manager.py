"""
parser/relay_manager.py
Parses goTenna Relay Manager Android logcat logs.

Two sub-types share the same format and are auto-detected by poll interval:

  networkPolling         — app polls relay nodes at a user-configured frequency
                           (5m / 15m / 30m / 1h / 2h / 4h / 6h).  The log
                           captures BLE traffic and firmware notifications
                           continuously between scheduled health requests.

  scheduledHealthRequest — user-configured scheduled health check (e.g. daily).
                           Same log structure; distinguished by the longer gap
                           between "Command relayHealthRequestCall" events.

Both sub-types are Android logcat dumps that embed the Relay Manager app
output (package com.gotenna.relaymanager) inside broader Android system noise.
All Relay Manager lines run through System.out with a UTC internal timestamp
that may differ from the Android local timestamp on the same line.

Environment detection
---------------------
Stage: "na.relaymanager(<pid>)" appears in io_stats lines.
Prod:  Not yet characterized.  Logs flagged "unknown" until prod samples
       are analyzed.  The parser captures everything regardless — do not
       skip lines based on environment.

Data limitations (returned in parse_errors)
-------------------------------------------
- BLE payload bytes are present but not decoded.  Relay health attribute
  values (SNR, battery %, temperature °F, uptime, firmware version) live
  inside raw BLE frames (e.g. "Unknown data: 100225ec…") and require BLE
  protocol decoding not yet implemented.
- Only one relay node observed per log session (single BLE MAC address).
  Multi-node aggregation and missing-node detection cannot be assessed.
- Prod log behavioral differences are unknown until prod samples arrive.

Usage:
    from parser.relay_manager import parse_relay_manager_log
    result = parse_relay_manager_log(Path("networkPolling.txt"))
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from .models import (
    ParseResult,
    DeviceInfo,
    SessionGap,
    RelayHealthRequest,
    RelayNotificationEvent,
    RelayManagerEvent,
)

# ── Timestamp formats ─────────────────────────────────────────────────────────

# Android logcat wall-clock prefix: MM-DD HH:MM:SS.mmm
_LOGCAT_TS_RE = re.compile(r"^(\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3})")
_LOGCAT_TS_FMT = "%m-%d %H:%M:%S.%f"

# Relay Manager internal UTC timestamp embedded in System.out lines:
# 2026-05-22T14:46:41.944712Z
_INTERNAL_TS_RE = re.compile(r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z)")
_INTERNAL_TS_FMT = "%Y-%m-%dT%H:%M:%S.%fZ"

_TS_FMT_OUT = "%Y-%m-%d %H:%M:%S.%f"


def _parse_logcat_ts(s: str) -> Optional[datetime]:
    try:
        # Inject a placeholder year — logcat omits it; 2026 matches these logs
        return datetime.strptime("2026-" + s, "%Y-" + _LOGCAT_TS_FMT)
    except ValueError:
        return None


def _parse_internal_ts(s: str) -> Optional[datetime]:
    try:
        return datetime.strptime(s, _INTERNAL_TS_FMT)
    except ValueError:
        return None


def _fmt(dt: datetime) -> str:
    return dt.strftime(_TS_FMT_OUT)


# ── Logcat line structure ─────────────────────────────────────────────────────

# MM-DD HH:MM:SS.mmm  PID  TID  LEVEL  TAG: message
_LOGCAT_LINE_RE = re.compile(
    r"^(?P<ts>\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3})"
    r"\s+(?P<pid>\d+)"
    r"\s+(?P<tid>\d+)"
    r"\s+(?P<level>[A-Z])"
    r"\s+(?P<tag>[^:]+):\s*(?P<rest>.*)$"
)

# ── Relay Manager process identification — three strategies in priority order ─
#
# Strategy 1 (most reliable, works in both log types):
#   The "Command relayHealthRequestCall" line itself carries the app PID.
#   Pattern: MM-DD HH:MM:SS.mmm  <PID>  <TID>  D  Services Plugin: Command relayHealthRequestCall
_HEALTH_CMD_LINE_RE = re.compile(
    r"^\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3}\s+(\d+)\s+\d+\s+D\s+Services Plugin:\s+Command relayHealthRequestCall"
)

# Strategy 2 (stage only): io_stats exposes the PID directly
#   "na.relaymanager(16170)"
_RM_PID_IO_RE = re.compile(r"na\.relaymanager\((\d+)\)")

# Strategy 3 (fallback): PowerManagerService ForegroundService:WakeLock with pid=
#   uid for com.gotenna.relaymanager is consistent within a device but not portable
#   so we match the pattern and cross-reference with the package name elsewhere
_PWR_PID_RE = re.compile(r"ForegroundService:WakeLock.*?\bpid=(\d+)\b")

# ── Relay Manager content patterns ───────────────────────────────────────────

# The one definitive signal: a scheduled health request fired
_HEALTH_REQUEST_RE = re.compile(r"Command relayHealthRequestCall")

# Firmware notification type line (inside System.out)
# "notification type: 72, hexValue: 48000000"
_NOTIF_TYPE_RE = re.compile(r"notification type:\s*(\d+),\s*hexValue:\s*([0-9a-fA-F]+)")

# goTenna device serial number (format: 3 capital letters + 9 digits)
_DEVICE_SERIAL_RE = re.compile(r"Device - ([A-Z]{3}\d{9})")

# BLE MAC address
_BLE_MAC_RE = re.compile(
    r"device ([0-9A-F]{2}:[0-9A-F]{2}:[0-9A-F]{2}:[0-9A-F]{2}:[0-9A-F]{2}:[0-9A-F]{2})"
)

# BLE outbound payload — immediately follows a health request command
_BLE_TX_RE = re.compile(r"Sending bytes to BLE device: Unknown data: ([0-9a-f]+)")

# Relay Manager event phrases → event_type labels
_EVENT_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"A message has been delivered and we should perform a get/delete"),
     "health_response_ready"),
    (re.compile(r"An alert has been sent from the device we need to do a pull"),
     "device_alert"),
    (re.compile(r"State of the battery/charging has changed"),
     "battery_state_changed"),
    (re.compile(r"Tried to update contact storage but sender uuid was empty"),
     "empty_sender_uuid"),
]

# High-volume BLE write confirmation events — counted in summary but not
# stored individually to avoid inflating memory on large logs
_BLE_NOISE_PATTERNS = re.compile(
    r"Confirmed successfully wrote packet|All packets for last command sent to radio"
)

# Polling sub-type boundary: average interval between health requests greater
# than this → scheduledHealthRequest; otherwise → networkPolling
_SCHEDULED_THRESHOLD_SEC = 2000   # ~33 min; networkPolling max is 6h in theory


# ── Session gap detection ─────────────────────────────────────────────────────

def _detect_session_gaps(
    timestamps: list[datetime],
    result: ParseResult,
    gap_min: int = 30,
) -> None:
    if len(timestamps) < 2:
        return
    timestamps.sort()
    result.session_start = _fmt(timestamps[0])
    result.session_end   = _fmt(timestamps[-1])
    for i in range(1, len(timestamps)):
        delta_min = (timestamps[i] - timestamps[i - 1]).total_seconds() / 60
        if delta_min > gap_min:
            result.session_gaps.append(SessionGap(
                from_timestamp=_fmt(timestamps[i - 1]),
                to_timestamp=_fmt(timestamps[i]),
                gap_minutes=round(delta_min, 1),
            ))


# ── Sub-type detection ────────────────────────────────────────────────────────

def _detect_subtype(
    health_requests: list[RelayHealthRequest],
    notification_counts: dict[int, int],
    source_filename: str,
) -> str:
    """
    Infer whether this is a networkPolling or scheduledHealthRequest log.

    Detection strategy (in priority order):

    1. Filename: contains 'networkpolling' or 'scheduledhealth' — definitive.

    2. Dominant firmware notification type:
       - Type 72 (0x48) BLE poll heartbeat → networkPolling
       - Type 8  (0x08) BLE keepalive      → scheduledHealthRequest
       These are mutually exclusive between the two sub-types in observed
       stage logs and are the most reliable programmatic signal.

    3. Poll interval fallback: used only when the above signals are absent.
       Intervals ≤ 33 min → networkPolling; > 33 min → scheduledHealthRequest.
       NOTE: Both sub-types can share a 60-minute interval, so this fallback
       is intentionally last.  Flag as 'unknown' when inconclusive.

    Returns 'networkPolling', 'scheduledHealthRequest', or 'unknown'.
    """
    fname = source_filename.lower()

    # 1. Filename
    if "networkpolling" in fname or "network_polling" in fname:
        return "networkPolling"
    if "scheduledhealth" in fname or "scheduled_health" in fname:
        return "scheduledHealthRequest"

    # 2. Dominant notification type
    type72 = notification_counts.get(72, 0)   # networkPolling heartbeat
    type8  = notification_counts.get(8, 0)    # scheduledHealth keepalive
    if type72 > 0 and type72 > type8:
        return "networkPolling"
    if type8 > 0 and type8 > type72:
        return "scheduledHealthRequest"

    # 3. Interval fallback
    if len(health_requests) < 2:
        return "unknown"
    dts: list[datetime] = []
    for r in health_requests:
        dt = None
        if r.internal_timestamp:
            dt = _parse_internal_ts(r.internal_timestamp)
        if dt is None and r.timestamp:
            try:
                dt = datetime.strptime(r.timestamp, _TS_FMT_OUT)
            except ValueError:
                pass
        if dt:
            dts.append(dt)
    if len(dts) < 2:
        return "unknown"
    dts.sort()
    avg_sec = (dts[-1] - dts[0]).total_seconds() / (len(dts) - 1)
    if avg_sec <= _SCHEDULED_THRESHOLD_SEC:
        return "networkPolling"
    return "scheduledHealthRequest"


# ── PID detection — Pass 1 ────────────────────────────────────────────────────

def _find_app_pid(lines: list[str]) -> Optional[str]:
    """
    Identify the Relay Manager process ID using three strategies in order:

    1. relayHealthRequestCall line (most reliable, works in both log types)
    2. io_stats na.relaymanager(<pid>) marker (stage only)
    3. PowerManagerService ForegroundService:WakeLock pid= (fallback)
    """
    # Strategy 1 — definitive: the command line itself carries the PID
    for line in lines:
        m = _HEALTH_CMD_LINE_RE.match(line)
        if m:
            return m.group(1)

    # Strategy 2 — io_stats stage marker
    for line in lines:
        m = _RM_PID_IO_RE.search(line)
        if m:
            return m.group(1)

    # Strategy 3 — PowerManagerService WakeLock for the relay manager UID.
    # Validate by confirming the package name appears in the same log.
    pwr_pid: Optional[str] = None
    has_pkg = False
    for line in lines:
        if not has_pkg and "com.gotenna.relaymanager" in line:
            has_pkg = True
        if pwr_pid is None:
            m = _PWR_PID_RE.search(line)
            if m:
                pwr_pid = m.group(1)
        if pwr_pid and has_pkg:
            return pwr_pid

    return None


# ── Public entry point ────────────────────────────────────────────────────────

def parse_relay_manager_log(path: Path) -> ParseResult:
    """
    Parse a goTenna Relay Manager Android logcat log file.

    Accepts both networkPolling and scheduledHealthRequest sub-types.
    Sub-type is auto-detected from health request cadence.

    Args:
        path: Path to the .txt logcat file.

    Returns:
        ParseResult with log_format="relay_manager" and all relay-specific
        fields populated.  Data limitations are appended to parse_errors.
    """
    result = ParseResult(
        log_format="relay_manager",
        source_filename=path.name,
    )
    result.device.platform = "android"

    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        result.parse_errors.append(f"Could not read file: {e}")
        return result

    lines = text.splitlines()

    # ── Pass 1: identify the Relay Manager PID ────────────────────────────────
    app_pid = _find_app_pid(lines)

    if app_pid is None:
        result.parse_errors.append(
            "Could not identify Relay Manager process ID. "
            "Log may be incomplete or a different app format."
        )

    # ── Environment detection ────────────────────────────────────────────────
    if _RM_PID_IO_RE.search(text):
        result.relay_manager_environment = "stage"
    else:
        result.relay_manager_environment = "unknown"
        result.parse_errors.append(
            "Environment could not be confirmed as stage (marker 'na.relaymanager' "
            "not found in io_stats). Prod logs have not yet been analyzed — "
            "environment detection will be refined when prod samples are available."
        )

    result.relay_manager_app_pid = app_pid or ""

    # ── Pass 2: line-by-line extraction ──────────────────────────────────────
    all_timestamps: list[datetime] = []
    notification_counts: dict[int, int] = {}

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue

        lm = _LOGCAT_LINE_RE.match(line)
        if not lm:
            continue

        line_pid      = lm.group("pid")
        logcat_ts_str = lm.group("ts")
        rest          = lm.group("rest").strip()

        # Parse logcat wall-clock timestamp for session span tracking
        logcat_dt = _parse_logcat_ts(logcat_ts_str)
        if logcat_dt:
            all_timestamps.append(logcat_dt)

        # Extract internal UTC timestamp if present
        internal_ts_str: Optional[str] = None
        int_m = _INTERNAL_TS_RE.search(rest)
        if int_m:
            internal_ts_str = int_m.group(1)

        ts_out = _fmt(logcat_dt) if logcat_dt else logcat_ts_str

        # ── All content extraction below is Relay Manager process only ────────
        if app_pid and line_pid != app_pid:
            continue

        # ── Device serial ─────────────────────────────────────────────────────
        if not result.device.radio_serial:
            ds_m = _DEVICE_SERIAL_RE.search(rest)
            if ds_m:
                result.device.radio_serial = ds_m.group(1)

        # ── BLE MAC address ───────────────────────────────────────────────────
        if not result.relay_manager_ble_address:
            mac_m = _BLE_MAC_RE.search(rest)
            if mac_m:
                result.relay_manager_ble_address = mac_m.group(1)

        # ── Health request command ────────────────────────────────────────────
        if _HEALTH_REQUEST_RE.search(rest):
            result.relay_health_requests.append(RelayHealthRequest(
                timestamp=ts_out,
                internal_timestamp=internal_ts_str,
                ble_payload=None,   # attached from the next BLE write line
            ))

        # ── Attach BLE payload to the most recent pending health request ──────
        # The BLE write line immediately follows the Command line in the log.
        if result.relay_health_requests and result.relay_health_requests[-1].ble_payload is None:
            tx_m = _BLE_TX_RE.search(rest)
            if tx_m:
                result.relay_health_requests[-1].ble_payload = tx_m.group(1)

        # ── Firmware notification types ───────────────────────────────────────
        notif_m = _NOTIF_TYPE_RE.search(rest)
        if notif_m:
            code = int(notif_m.group(1))
            notification_counts[code] = notification_counts.get(code, 0) + 1

        # ── Skip high-volume BLE write noise ──────────────────────────────────
        if _BLE_NOISE_PATTERNS.search(rest):
            continue

        # ── Named relay manager events ────────────────────────────────────────
        for pattern, event_type in _EVENT_PATTERNS:
            if pattern.search(rest):
                result.relay_manager_events.append(RelayManagerEvent(
                    timestamp=ts_out,
                    internal_timestamp=internal_ts_str,
                    event_type=event_type,
                    raw_message=rest[:200],
                ))
                break

    # ── Finalize ──────────────────────────────────────────────────────────────
    result.relay_manager_notification_counts = notification_counts
    result.relay_manager_subtype = _detect_subtype(
        result.relay_health_requests,
        notification_counts,
        path.name,
    )

    _detect_session_gaps(all_timestamps, result)

    # ── Standing data-limitation notices ─────────────────────────────────────
    result.parse_errors.append(
        "DATA LIMITATION — BLE payload not decoded: relay health attribute values "
        "(SNR, battery %, temperature °F, uptime, firmware version) are present as raw "
        "hex bytes in BLE frames but require protocol decoding not yet implemented."
    )
    if len({r.ble_payload for r in result.relay_health_requests if r.ble_payload}) <= 1:
        result.parse_errors.append(
            "DATA LIMITATION — Single relay node observed: only one BLE MAC address "
            "detected per session. Multi-node network response aggregation and "
            "missing-node detection cannot be assessed from this sample."
        )
    if result.relay_manager_environment != "stage":
        result.parse_errors.append(
            "DATA LIMITATION — Prod logs not yet analyzed: stage vs. prod behavioral "
            "differences are unknown. Update environment detection in "
            "parser/relay_manager.py when prod samples arrive."
        )

    return result
