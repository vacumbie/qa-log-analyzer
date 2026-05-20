"""
parser/rsdk.py
Parses the goTenna RSDK log format (iOS and Android SDK logs).

Unlike the diagnostic format, RSDK logs are line-by-line structured text with
timestamp, log level, device serial, component, and message fields.

Usage:
    from parser.rsdk import parse_rsdk_log
    result = parse_rsdk_log(Path("rsdk_log_Ellis_iOS1.txt"))
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from .models import (
    ParseResult, DeviceInfo, SystemSample, BleFailEvent,
    TxEvent, SessionGap,
)

# ── Line pattern ──────────────────────────────────────────────────────────────
# Format: 2026-03-03T15:16:13.515351Z LEVEL Device - SERIAL Component: message
_LINE_RE = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z)"
    r"\s+(?P<level>\w+)"
    r"\s+Device - (?P<serial>\w+)"
    r"\s+(?P<rest>.+)$"
)

_TS_FMT_IN  = "%Y-%m-%dT%H:%M:%S.%fZ"
_TS_FMT_OUT = "%Y-%m-%d %H:%M:%S.%f"

def _parse_ts(s: str) -> Optional[datetime]:
    try:
        return datetime.strptime(s.strip(), _TS_FMT_IN)
    except ValueError:
        return None

def _fmt(dt: datetime) -> str:
    return dt.strftime(_TS_FMT_OUT)


# ── Patterns for specific log lines ──────────────────────────────────────────

# BLE reconnection failure (iOS only)
_BLE_FAIL_RE = re.compile(r"IosBleRadio: BLE reconnection failed, retrying in 2000ms")

# Device info from DeviceInfo(...) blocks
_DEV_INFO_RE = re.compile(r"DeviceInfo\(.*?deviceSerial=(\w+).*?firmwareVersion=([^\s,)]+)")

# Battery level: "BATTERY_LEVEL: 98" or "battery: 98%"
_BATTERY_RE = re.compile(r"(?:BATTERY_LEVEL|battery)[:\s]+(\d+\.?\d*)\s*%?", re.I)

# PA temperature: "POWER_AMP_TEMP: 31" (Celsius)
_TEMP_RE = re.compile(r"POWER_AMP_TEMP[:\s]+(\d+)", re.I)

# Firmware version in log lines
_FW_RE = re.compile(r"firmwareVersion=([^\s,)]+)")

# Unicast TX outcomes in SendMessageResponse
_FINAL_ACK_RE  = re.compile(r"SendMessageResponse.*?FINAL_ACK.*?id=(\w+)", re.I)
_NACK_RE       = re.compile(r"SendMessageResponse.*?NACK.*?id=(\w+)", re.I)
_TIMEOUT_RE    = re.compile(r"SendMessageResponse.*?TIMEOUT.*?id=(\w+)", re.I)
_KEEPALIVE_RE  = re.compile(r"SendMessageResponse.*?KEEPALIVE_ACK.*?id=(\w+)", re.I)

# Battery/temp from system poll lines
_SYS_BATT_RE  = re.compile(r"batteryLevel[=:\s]+(\d+\.?\d*)")
_SYS_TEMP_RE  = re.compile(r"powerAmpTemp[=:\s]+(\d+)")


# ── Line-by-line processing ───────────────────────────────────────────────────

def _process_line(
    raw_line: str,
    seen_lines: set,
    result: ParseResult,
    pending_samples: dict,     # serial -> {ts, battery, temp}
) -> None:
    """Process one deduplicated log line, updating result in place."""
    line = raw_line.strip()

    # Deduplicate exact duplicate lines (iOS log quirk)
    key = line[:120]
    if key in seen_lines:
        return
    seen_lines.add(key)

    m = _LINE_RE.match(line)
    if not m:
        return

    ts_str = m.group("ts")
    serial = m.group("serial")
    rest   = m.group("rest")
    dt     = _parse_ts(ts_str)
    if not dt:
        return

    ts_out = _fmt(dt)
    hour   = dt.hour

    # ── DeviceInfo ────────────────────────────────────────────────────────────
    di = _DEV_INFO_RE.search(rest)
    if di:
        detected_serial = di.group(1)
        fw = di.group(2)
        if not result.device.radio_firmware:
            result.device.radio_firmware = fw
        if not result.device.radio_serial:
            result.device.radio_serial = detected_serial

    # ── Firmware from any line ────────────────────────────────────────────────
    if not result.device.radio_firmware:
        fw_m = _FW_RE.search(rest)
        if fw_m:
            result.device.radio_firmware = fw_m.group(1)

    # ── BLE failure (iOS only) ────────────────────────────────────────────────
    if _BLE_FAIL_RE.search(rest):
        result.ble_fail_events.append(BleFailEvent(
            timestamp=ts_out,
            radio_serial=serial,
            hour=hour,
        ))

    # ── Battery ───────────────────────────────────────────────────────────────
    batt_m = _SYS_BATT_RE.search(rest) or _BATTERY_RE.search(rest)
    if batt_m:
        try:
            pending_samples.setdefault(serial, {})["ts"]      = ts_out
            pending_samples[serial]["battery"] = float(batt_m.group(1))
        except ValueError:
            pass

    # ── PA Temperature ────────────────────────────────────────────────────────
    temp_m = _SYS_TEMP_RE.search(rest) or _TEMP_RE.search(rest)
    if temp_m:
        try:
            pending_samples.setdefault(serial, {})["ts"]   = ts_out
            pending_samples[serial]["temp_c"] = int(temp_m.group(1))
        except ValueError:
            pass

    # Flush a complete sample when both battery and temp are present
    ps = pending_samples.get(serial, {})
    if "battery" in ps and "temp_c" in ps and "ts" in ps:
        result.system_samples.append(SystemSample(
            timestamp=ps["ts"],
            battery_pct=round(ps["battery"]),
            pa_temp_c=ps["temp_c"],
            firmware=result.device.radio_firmware,
        ))
        pending_samples[serial] = {}

    # ── Unicast TX outcomes ───────────────────────────────────────────────────
    for pattern, outcome in (
        (_FINAL_ACK_RE, "final_ack"),
        (_NACK_RE,       "nack"),
        (_TIMEOUT_RE,    "timeout"),
        (_KEEPALIVE_RE,  "keepalive_ack"),
    ):
        tx_m = pattern.search(rest)
        if tx_m:
            result.tx_events.append(TxEvent(
                timestamp=ts_out,
                message_id=tx_m.group(1),
                outcome=outcome,
                radio_serial=serial,
            ))


# ── Session gap detection ─────────────────────────────────────────────────────

def _detect_session_gaps(result: ParseResult, gap_min: int = 30) -> None:
    all_ts: list[datetime] = []
    for s in result.system_samples:
        dt = datetime.strptime(s.timestamp, _TS_FMT_OUT) if s.timestamp else None
        if dt:
            all_ts.append(dt)
    for b in result.ble_fail_events:
        dt = datetime.strptime(b.timestamp, _TS_FMT_OUT) if b.timestamp else None
        if dt:
            all_ts.append(dt)
    for t in result.tx_events:
        dt = datetime.strptime(t.timestamp, _TS_FMT_OUT) if t.timestamp else None
        if dt:
            all_ts.append(dt)

    if not all_ts:
        return

    all_ts.sort()
    result.session_start = all_ts[0].strftime(_TS_FMT_OUT)
    result.session_end   = all_ts[-1].strftime(_TS_FMT_OUT)

    for i in range(1, len(all_ts)):
        delta = (all_ts[i] - all_ts[i - 1]).total_seconds() / 60
        if delta > gap_min:
            result.session_gaps.append(SessionGap(
                from_timestamp=all_ts[i - 1].strftime(_TS_FMT_OUT),
                to_timestamp=all_ts[i].strftime(_TS_FMT_OUT),
                gap_minutes=round(delta, 1),
            ))


# ── Infer platform from log content ──────────────────────────────────────────

def _infer_platform(text: str) -> str:
    if "IosBleRadio" in text:
        return "ios"
    if "AndroidBleRadio" in text or "BluetoothGatt" in text:
        return "android"
    return "unknown"


# ── Public entry point ────────────────────────────────────────────────────────

def parse_rsdk_log(path: Path) -> ParseResult:
    """
    Parse a goTenna RSDK log file (iOS or Android).

    Args:
        path: Path to the RSDK .txt log file.

    Returns:
        ParseResult populated with all extracted data.
    """
    result = ParseResult(
        log_format="rsdk",
        source_filename=path.name,
    )

    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        result.parse_errors.append(f"Could not read file: {e}")
        return result

    result.device.platform = _infer_platform(text)

    seen_lines: set = set()
    pending_samples: dict = {}   # serial -> partial SystemSample data

    for raw_line in text.splitlines():
        try:
            _process_line(raw_line, seen_lines, result, pending_samples)
        except Exception as e:
            result.parse_errors.append(f"Line parse error: {e} — {raw_line[:80]}")

    _detect_session_gaps(result)
    return result
