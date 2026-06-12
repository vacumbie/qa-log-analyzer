"""
parser/diagnostic.py
Parses the goTenna Pro+ diagnostic log format (v1).

Record format: blank-line-delimited text blocks.
Each block starts with a timestamp, then a record type on the second line,
followed by key: value fields.

Usage:
    from parser.diagnostic import parse_diagnostic_log
    result = parse_diagnostic_log(Path("RSO_HagenM.txt"))
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from .models import (
    ParseResult, DeviceInfo, SystemSample, ReceivedMessage,
    MessageCountSnapshot, RadioStatSnapshot, FrequencySet,
    SessionGap,
)

# ── Timestamp parsing ─────────────────────────────────────────────────────────

_TS_FMT = "%Y-%m-%d %H:%M:%S.%f"
_TS_RE  = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}")

def _parse_ts(s: str) -> Optional[datetime]:
    try:
        return datetime.strptime(s.strip(), _TS_FMT)
    except ValueError:
        return None


# ── Block splitting ───────────────────────────────────────────────────────────

def _split_blocks(text: str) -> list[dict]:
    """
    Split raw log text into a list of dicts.
    Each dict has '_timestamp', '_type', and one key per field line.
    """
    blocks = re.split(r"\n{2,}", text.strip())
    parsed = []
    for block in blocks:
        lines = [l.strip() for l in block.strip().splitlines() if l.strip()]
        if len(lines) < 2:
            continue
        record: dict = {"_timestamp": lines[0], "_type": lines[1]}
        for line in lines[2:]:
            if ": " in line:
                k, v = line.split(": ", 1)
                record[k.strip()] = v.strip()
        parsed.append(record)
    return parsed


# ── Per-type handlers ─────────────────────────────────────────────────────────

def _handle_device_info(block: dict, result: ParseResult) -> None:
    d = result.device
    d.app_version   = block.get("app version", "")
    d.build_number  = block.get("build number", "")
    d.log_version   = block.get("log version", "")
    d.device_model  = block.get("device", "")
    d.platform      = "ios"  # diagnostic format is iOS-only


def _handle_system_info(block: dict, result: ParseResult) -> None:
    ts = block.get("_timestamp", "")
    batt = block.get("BATTERY LEVEL")
    temp = block.get("POWER AMP TEMP")
    fw   = block.get("FIRMWARE VERSION", "")

    # Capture radio firmware and serial on first system info block
    if not result.device.radio_firmware and fw:
        result.device.radio_firmware = fw
    serial = block.get("SERIAL NUMBER", "")
    if not result.device.radio_serial and serial:
        result.device.radio_serial = serial

    result.system_samples.append(SystemSample(
        timestamp=ts,
        battery_pct=int(batt) if batt and batt.isdigit() else None,
        pa_temp_c=int(temp) if temp and temp.lstrip("-").isdigit() else None,
        firmware=fw,
    ))


def _handle_received_message(block: dict, result: ParseResult) -> None:
    def _int(val: Optional[str]) -> Optional[int]:
        if val is None:
            return None
        try:
            return int(val.replace(" dBm", "").strip())
        except ValueError:
            return None

    # Capture receiver identity from first message that has it
    rcv_cs  = block.get("receiver callsign", "")
    rcv_gid = block.get("receiver gid", "")
    if rcv_cs and not result.device.callsign:
        result.device.callsign = rcv_cs
    if rcv_gid and not result.device.gid:
        result.device.gid = rcv_gid

    result.received_messages.append(ReceivedMessage(
        timestamp=block.get("receiver timestamp", block.get("_timestamp", "")),
        message_id=block.get("id", ""),
        data_type=block.get("data type", ""),
        message_type=block.get("message type", ""),
        hop_count=_int(block.get("hop count")),
        rssi_raw=_int(block.get("rssi")),
        frequency_set=block.get("frequency set", ""),
        frames_used=_int(block.get("frames used")),
        originator_callsign=block.get("originator callsign", ""),
        originator_gid=block.get("originator gid", ""),
        originator_location=block.get("originator location", ""),
        originator_pli_interval=block.get("originator pli interval", ""),
        originator_timestamp=block.get("originator timestamp", ""),
        receiver_callsign=rcv_cs,
        receiver_gid=rcv_gid,
        receiver_location=block.get("receiver location", ""),
        receiver_pli_interval=block.get("receiver pli interval", ""),
        receiver_timestamp=block.get("receiver timestamp", ""),
    ))


def _handle_message_counts(block: dict, result: ParseResult) -> None:
    def _i(key: str) -> int:
        v = block.get(key, "0")
        try:
            return int(v)
        except ValueError:
            return 0

    result.message_count_snapshots.append(MessageCountSnapshot(
        timestamp=block.get("_timestamp", ""),
        pli_sent=_i("pli messages sent"),
        pli_received=_i("pli messages received"),
        chat_sent=_i("chat and map messages sent"),
        chat_received=_i("chat and map messages received"),
    ))


def _handle_frequency_set(block: dict, result: ParseResult) -> None:
    result.frequency_sets.append(FrequencySet(
        timestamp=block.get("_timestamp", ""),
        name=block.get("name", ""),
        power_watts=block.get("power level", ""),
        bandwidth_khz=block.get("bandwidth", ""),
        control_channels=block.get("control channels", ""),
        data_channels=block.get("data channels", ""),
    ))


def _handle_stat_block(block: dict, result: ParseResult) -> None:
    """
    The radio lifetime stat block. The block type line itself encodes one value
    (e.g. 'total number of messages received: 687931392') so we parse it too.
    """
    def _i(key: str) -> Optional[int]:
        v = block.get(key)
        if v is None:
            return None
        try:
            return int(v)
        except ValueError:
            return None

    # The block type line encodes 'total number of messages received: N'
    lifetime_recv: Optional[int] = None
    m = re.search(r"total number of messages received:\s*(\d+)", block["_type"])
    if m:
        lifetime_recv = int(m.group(1))

    # Approximate timestamp: use the timestamp of the next block recorded
    # (stat blocks don't have their own valid timestamp line)
    snap = RadioStatSnapshot(
        timestamp=block.get("_timestamp", ""),
        lifetime_uptime_tenths_hrs=_i("total uptime in one tenth of hours"),
        lifetime_msgs_originated=_i("total number of messages orginated"),
        lifetime_msgs_received=lifetime_recv,
        lifetime_msgs_relayed=_i("total number of messages relayed"),
        lifetime_msgs_rejected=_i("total number of messages rejected"),
        lifetime_uhf_tx_5w_sec=_i("total UHF transmit time in seconds at 5.0W"),
        lifetime_uhf_rx_sec=_i("total UHF received time in seconds"),
        commands_errored=_i("number of commands errored"),
        temp_threshold_events=_i("number of events exceeding allowable temparature threshold"),
        avg_uhf_rssi_db=_i("average UHF RF RSSI, in dB"),
        avg_uhf_ant_quality_db=_i("average UHF RF antenna quality, in dB"),
        avg_ble_rssi=_i("average BLE RSSI"),
        session_msgs_sent=_i("number of messages sent"),
        session_msgs_received=_i("number of messages received"),
        session_msgs_relayed=_i("number of messages relayed"),
        session_msgs_rejected=_i("number of messages rejected"),
    )
    result.radio_stat_snapshots.append(snap)


# ── Session gap detection ─────────────────────────────────────────────────────

def _detect_session_gaps(result: ParseResult, gap_threshold_min: int = 30) -> None:
    """Find breaks > gap_threshold_min between consecutive timestamps."""
    all_ts: list[datetime] = []
    for m in result.received_messages:
        dt = _parse_ts(m.timestamp)
        if dt:
            all_ts.append(dt)
    for s in result.system_samples:
        dt = _parse_ts(s.timestamp)
        if dt:
            all_ts.append(dt)

    if not all_ts:
        return

    all_ts.sort()
    result.session_start = all_ts[0].strftime(_TS_FMT)
    result.session_end   = all_ts[-1].strftime(_TS_FMT)

    for i in range(1, len(all_ts)):
        delta_min = (all_ts[i] - all_ts[i - 1]).total_seconds() / 60
        if delta_min > gap_threshold_min:
            result.session_gaps.append(SessionGap(
                from_timestamp=all_ts[i - 1].strftime(_TS_FMT),
                to_timestamp=all_ts[i].strftime(_TS_FMT),
                gap_minutes=round(delta_min, 1),
            ))


# ── Public entry point ────────────────────────────────────────────────────────

def parse_diagnostic_log(path: Path) -> ParseResult:
    """
    Parse a goTenna Pro+ diagnostic log file.

    Args:
        path: Path to the .txt diagnostic log file.

    Returns:
        ParseResult populated with all extracted data.
    """
    result = ParseResult(
        log_format="diagnostic",
        source_filename=path.name,
    )

    try:
        text = path.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n")
    except OSError as e:
        result.parse_errors.append(f"Could not read file: {e}")
        return result

    blocks = _split_blocks(text)

    for block in blocks:
        btype = block.get("_type", "")
        try:
            if btype == "Device & Application Info":
                _handle_device_info(block, result)
            elif btype == "System Information":
                _handle_system_info(block, result)
            elif btype == "Received Message":
                _handle_received_message(block, result)
            elif btype == "Message Count Details":
                _handle_message_counts(block, result)
            elif btype == "Frequency Set":
                _handle_frequency_set(block, result)
            elif btype.startswith("total number of messages"):
                _handle_stat_block(block, result)
            # "Tester Location" blocks are skipped — location data not yet used
        except Exception as e:
            result.parse_errors.append(f"Error in block type '{btype}': {e}")

    _detect_session_gaps(result)

    # DATA LIMITATION — firmware 3.1.11 is known to omit the originator callsign
    # and GID from Received Message blocks, so the sender of those messages cannot
    # be identified. Surface this only when it actually manifests: a received
    # message carrying neither originator identity field. Logs that include the
    # fields (later firmware, or 3.1.11 blocks that happen to have them) emit nothing.
    missing_identity = sum(
        1 for m in result.received_messages
        if not m.originator_callsign and not m.originator_gid
    )
    if missing_identity:
        result.parse_errors.append(
            "DATA LIMITATION — Firmware 3.1.11 omits originator callsign and GID from "
            f"Received Message blocks ({missing_identity} of {len(result.received_messages)} "
            "received messages affected): the sender cannot be identified for those messages."
        )

    return result
