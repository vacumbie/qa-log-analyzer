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
    TxEvent, SessionGap, GripMessage, GripTransfer,
)

# ── Line pattern ──────────────────────────────────────────────────────────────
# Format: 2026-03-03T15:16:13.515351Z LEVEL Device - SERIAL Component: message
_LINE_RE = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z)"
    r"\s+(?P<level>\w+)"
    r"\s+Device - (?P<serial>\w+)"
    r"\s+(?P<component>\w+):\s*(?P<rest>.+)$"
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
_BLE_FAIL_RE = re.compile(r"BLE reconnection failed, retrying in 2000ms")

# Device info from DeviceInfo(...) blocks
_DEV_INFO_RE = re.compile(r"DeviceInfo\(.*?deviceSerial=(\w+).*?firmwareVersion=([^\s,)]+)")

# Battery level: "BATTERY_LEVEL: 98" or "battery: 98%"
_BATTERY_RE = re.compile(r"(?:BATTERY_LEVEL|battery)[:\s]+(\d+\.?\d*)\s*%?", re.I)

# PA temperature: "POWER_AMP_TEMP: 31" (Celsius) — legacy/fallback pattern
_TEMP_RE = re.compile(r"POWER_AMP_TEMP[:\s]+(\d+)", re.I)

# Firmware version in log lines
_FW_RE = re.compile(r"firmwareVersion=([^\s,)]+)")

# Unicast TX outcomes in GRIP_Receiver lines
# "SRC: Final ACK received, message fully delivered"
_GRIP_FINAL_ACK_RE = re.compile(r"SRC:\s*Final ACK received,\s*message fully delivered", re.I)
# "SRC: Keep-alive ACK received. Segment ID: N msgId: N"
_GRIP_KEEPALIVE_RE = re.compile(r"SRC:\s*Keep-alive ACK received.*?msgId:\s*(\d+)", re.I)

# ContactManager: "Created contact for user <name>  with UUID <uuid>"
_CONTACT_RE = re.compile(r'Created contact for user (.+?) {1,3}with UUID (\S+)')

# Battery/temp from DeviceInfo system poll lines
_SYS_BATT_RE = re.compile(r"batteryLevel[=:\s]+(\d+\.?\d*)")

# BUG FIX: was r"powerAmpTemp[=:\s]+(\d+)" — missed field name "powerAmpTemperature"
_SYS_TEMP_RE = re.compile(r"powerAmpTemperature[=:\s]+(\d+)")

# Android NACK component patterns (Android only — component tag is "NACK")
_AND_NACK_MSGID_RE = re.compile(r"missing segments \[[\d,\s]+\] for msgId:\s*(\d+)", re.I)
_AND_NACK_FRAME_RE = re.compile(r"nack triggered.*?messageId=(\d+)", re.I)

# ── GRIP structured message fields ────────────────────────────────────────────
#
# Both GRIP_SENDER (outgoing) and GRIP_Receiver (incoming) emit a structured
# fields line. Incoming lines additionally include hops and rssi before
# segment size.
#
# Outgoing: "...reservedByte: N segment size: N"
# Incoming: "...reservedByte: N hops: N rssi: N segment size: N"
_GRIP_FIELDS_RE = re.compile(
    r"(?P<direction>Outgoing|Incoming) message fields:\s*"
    r"MsgType:\s*(?P<msg_type>-?\d+);\s*"
    r"SRC:\s*(?P<src>-?\d+);\s*"
    r"DST:\s*(?P<dst>-?\d+);\s*"
    r"appId:\s*(?P<app_id>\d+);\s*"
    r"msgId:\s*(?P<msg_id>\d+);\s*"
    r"seqNo:\s*(?P<seq_no>\d+);\s*"
    r"isFirstPacket:\s*(?P<is_first_packet>\d+);\s*"
    r"segReserved:\s*(?P<seg_reserved>\d+);\s*"
    r"isAck:\s*(?P<is_ack>\d+);\s*"
    r"requiresAck:\s*(?P<requires_ack>\d+);\s*"
    r"agOriginated:\s*(?P<ag_originated>\d+);\s*"
    r"isPeriodic:\s*(?P<is_periodic>\d+);\s*"
    r"repCounter:\s*(?P<rep_counter>\d+);\s*"
    r"reservedByte:\s*(?P<reserved_byte>\d+)\s*"
    r"(?:hops:\s*(?P<hops>\d+)\s+rssi:\s*(?P<rssi>-?\d+)\s+)?"
    r"segment size:\s*(?P<segment_size>\d+)"
)

# MsgType values
# 0 = PRIVATE (unicast)
# 2 = BROADCAST
_MSG_TYPE_LABELS = {0: "private", 2: "broadcast"}

# ── GRIP transfer lifecycle patterns ─────────────────────────────────────────
# "File transmission started, file id: 3196"
_FILE_START_RE = re.compile(r"File transmission started,\s*file id:\s*(\d+)", re.I)

# "File has been successfully delivered to destination, file id: 3196"
_FILE_DONE_RE = re.compile(r"File has been successfully delivered to destination,\s*file id:\s*(\d+)", re.I)

# "sent file msgId: 2640 stopped with true in 2006ms earlyCancel: false"
_SENT_STOP_RE = re.compile(
    r"sent file msgId:\s*(\d+)\s+stopped with\s+(\w+)\s+in\s+(\d+)ms\s+earlyCancel:\s*(\w+)",
    re.I
)

# "Full grip file received! id: 3196 number of segments: 1"
_GRIP_RECV_DONE_RE = re.compile(r"Full grip file received!\s*id:\s*(\d+)\s+number of segments:\s*(\d+)", re.I)


# ── Line-by-line processing ───────────────────────────────────────────────────

def _process_line(
    raw_line: str,
    seen_lines: set,
    result: ParseResult,
    pending_samples: dict,      # serial -> {ts, battery, temp}
    open_transfers: dict,       # (serial, msg_id) -> {start_ts, max_rep, segment_count}
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

    ts_str    = m.group("ts")
    serial    = m.group("serial")
    component = m.group("component")
    rest      = m.group("rest")
    dt        = _parse_ts(ts_str)
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
    if component == "IosBleRadio" and _BLE_FAIL_RE.search(rest):
        result.ble_fail_events.append(BleFailEvent(
            timestamp=ts_out,
            radio_serial=serial,
            hour=hour,
        ))

    # ── Contact discovery ─────────────────────────────────────────────────────
    contact_m = _CONTACT_RE.search(rest)
    if contact_m:
        name = contact_m.group(1).strip()
        uuid = contact_m.group(2).strip()
        if uuid and name:
            result.contacts[uuid] = name

    # ── Battery ───────────────────────────────────────────────────────────────
    batt_m = _SYS_BATT_RE.search(rest) or _BATTERY_RE.search(rest)
    if batt_m:
        try:
            batt_val = float(batt_m.group(1))
            if batt_val >= 0:   # sentinel: -1 = not yet valid on first connect
                pending_samples.setdefault(serial, {})["ts"]      = ts_out
                pending_samples[serial]["battery"] = batt_val
        except ValueError:
            pass

    # ── PA Temperature ────────────────────────────────────────────────────────
    temp_m = _SYS_TEMP_RE.search(rest) or _TEMP_RE.search(rest)
    if temp_m:
        try:
            temp_val = int(temp_m.group(1))
            if temp_val >= 0:   # sentinel: -1 = not yet valid on first connect
                pending_samples.setdefault(serial, {})["ts"]      = ts_out
                pending_samples[serial]["temp_c"] = temp_val
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

    # ── GRIP structured message fields ────────────────────────────────────────
    # Parsed from both GRIP_SENDER (outgoing) and GRIP_Receiver (incoming).
    # Incoming lines carry hops and rssi — genuine RF routing data.
    if component in ("GRIP_SENDER", "GRIP_Receiver"):
        gf = _GRIP_FIELDS_RE.search(rest)
        if gf:
            gd = gf.groupdict()
            msg_type_int = int(gd["msg_type"])
            grip_msg = GripMessage(
                timestamp=ts_out,
                direction="outgoing" if gd["direction"] == "Outgoing" else "incoming",
                msg_type=msg_type_int,
                msg_type_label=_MSG_TYPE_LABELS.get(msg_type_int, f"unknown({msg_type_int})"),
                msg_id=int(gd["msg_id"]),
                src_gid=int(gd["src"]),
                dst_gid=int(gd["dst"]),
                app_id=int(gd["app_id"]),
                seq_no=int(gd["seq_no"]),
                is_first_packet=gd["is_first_packet"] == "1",
                is_ack=gd["is_ack"] == "1",
                requires_ack=gd["requires_ack"] == "1",
                is_periodic=gd["is_periodic"] == "1",
                rep_counter=int(gd["rep_counter"]),
                segment_size=int(gd["segment_size"]),
                hops=int(gd["hops"]) if gd["hops"] is not None else None,
                rssi=int(gd["rssi"]) if gd["rssi"] is not None else None,
                radio_serial=serial,
            )
            result.grip_messages.append(grip_msg)

            # Track max rep_counter per open transfer for retransmit detection
            key = (serial, int(gd["msg_id"]))
            if key in open_transfers:
                open_transfers[key]["max_rep"] = max(
                    open_transfers[key].get("max_rep", 0),
                    int(gd["rep_counter"])
                )

    # ── GRIP transfer lifecycle — start ───────────────────────────────────────
    if component == "COMMANDHANDLER":
        start_m = _FILE_START_RE.search(rest)
        if start_m:
            msg_id = int(start_m.group(1))
            open_transfers[(serial, msg_id)] = {
                "start_ts": ts_out,
                "start_dt": dt,
                "radio_serial": serial,
                "max_rep": 0,
                "segment_count": None,
            }

        # Sender-side completion
        done_m = _FILE_DONE_RE.search(rest)
        if done_m:
            msg_id = int(done_m.group(1))
            key = (serial, msg_id)
            if key in open_transfers:
                ot = open_transfers.pop(key)
                delivery_ms = int((dt - ot["start_dt"]).total_seconds() * 1000)
                result.grip_transfers.append(GripTransfer(
                    msg_id=msg_id,
                    radio_serial=serial,
                    start_timestamp=ot["start_ts"],
                    end_timestamp=ts_out,
                    delivery_ms=delivery_ms,
                    outcome="delivered",
                    max_rep_counter=ot.get("max_rep", 0),
                    segment_count=ot.get("segment_count"),
                ))

        # Receiver-side completion (full grip file received)
        recv_m = _GRIP_RECV_DONE_RE.search(rest)
        if recv_m:
            msg_id = int(recv_m.group(1))
            seg_count = int(recv_m.group(2))
            key = (serial, msg_id)
            if key in open_transfers:
                open_transfers[key]["segment_count"] = seg_count

    # ── GRIP_SENDER stop line (delivery duration + earlyCancel) ──────────────
    if component == "GRIP_SENDER":
        stop_m = _SENT_STOP_RE.search(rest)
        if stop_m:
            msg_id     = int(stop_m.group(1))
            success    = stop_m.group(2).lower() == "true"
            duration_ms = int(stop_m.group(3))
            early_cancel = stop_m.group(4).lower() == "true"
            key = (serial, msg_id)
            if key in open_transfers:
                open_transfers[key]["duration_ms"]   = duration_ms
                open_transfers[key]["early_cancel"]  = early_cancel
                open_transfers[key]["sender_success"] = success

    # ── Unicast TX outcomes (GRIP_Receiver) ───────────────────────────────────
    if component == "GRIP_Receiver":
        if _GRIP_FINAL_ACK_RE.search(rest):
            result.tx_events.append(TxEvent(
                timestamp=ts_out,
                message_id="",   # not in this log line; correlate via grip_transfers
                outcome="final_ack",
                radio_serial=serial,
            ))
        ka_m = _GRIP_KEEPALIVE_RE.search(rest)
        if ka_m:
            result.tx_events.append(TxEvent(
                timestamp=ts_out,
                message_id=ka_m.group(1),
                outcome="keepalive_ack",
                radio_serial=serial,
            ))

    # ── Android: NACKs surface as a dedicated "NACK" component tag ────────────
    if component == "NACK":
        nack_m = _AND_NACK_MSGID_RE.search(rest) or _AND_NACK_FRAME_RE.search(rest)
        if nack_m:
            result.tx_events.append(TxEvent(
                timestamp=ts_out,
                message_id=nack_m.group(1),
                outcome="nack",
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
    for g in result.grip_transfers:
        dt = datetime.strptime(g.start_timestamp, _TS_FMT_OUT) if g.start_timestamp else None
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

    seen_lines: set  = set()
    pending_samples: dict = {}   # serial -> partial SystemSample data
    open_transfers: dict  = {}   # (serial, msg_id) -> transfer state

    for raw_line in text.splitlines():
        try:
            _process_line(raw_line, seen_lines, result, pending_samples, open_transfers)
        except Exception as e:
            result.parse_errors.append(f"Line parse error: {e} — {raw_line[:80]}")

    # Any transfers still open at EOF had no completion log — mark as incomplete
    for (serial, msg_id), ot in open_transfers.items():
        result.grip_transfers.append(GripTransfer(
            msg_id=msg_id,
            radio_serial=serial,
            start_timestamp=ot.get("start_ts", ""),
            end_timestamp="",
            delivery_ms=None,
            outcome="incomplete",
            max_rep_counter=ot.get("max_rep", 0),
            segment_count=ot.get("segment_count"),
        ))

    _detect_session_gaps(result)

    # DATA LIMITATION — GRIP hop count and RSSI are only carried on GRIP_Receiver
    # incoming message-fields lines. The old SendMessageResponse hop count was an
    # SDK sequence counter (not RF data) and is excluded. When a session has no
    # incoming GRIP fields lines, hop count and RSSI are unavailable for the whole
    # log — surface that honestly rather than implying the radio reported no hops.
    has_grip_rf = any(
        g.direction == "incoming" and (g.hops is not None or g.rssi is not None)
        for g in result.grip_messages
    )
    if not has_grip_rf:
        result.parse_errors.append(
            "DATA LIMITATION — GRIP hop count and RSSI are only available from "
            "GRIP_Receiver incoming message-fields lines; none are present in this "
            "log, so hop count and RSSI are unavailable for this session."
        )

    return result
