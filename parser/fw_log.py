"""
parser/fw_log.py
Parser for goTenna relay radio firmware (UART/USB debug) logs.

Format: [timestamp_abs-delta_ms, MODULE, LEVEL] message
        bucket[N] HH - HH hours ago: X messages rx'd Y messages relayed Z messages tx'd

Key characteristics:
- Timestamps are relative milliseconds from boot — NOT wall clock UTC
- Device identity is the origin hash (e.g. 0f07) — serial/firmware version
  are in binary RHC payload, not plaintext
- Only INFO / ERROR / WARN lines are parsed — DEBUG is skipped (52% of lines)
- Bucket lines are raw text outside the bracket pattern, parsed separately
- Battery stabilization errors are a known firmware quirk, not hardware failure
- RHC bucket history appears multiple times per log (once per health poll);
  the parser keeps the last (most current) snapshot only
"""

from __future__ import annotations
import re
from pathlib import Path

from .models import (
    ParseResult, DeviceInfo,
    FwBucket, FwRssiSample, FwRoutingDecision, FwRfConfig, FwLogResult,
)

# ── Regex patterns ────────────────────────────────────────────────────────────

_LINE_RE   = re.compile(r'^\[(\d+)-(\d+),\s*(\w+),\s*(\w+)\]\s*(.*)')
_BUCKET_RE = re.compile(
    r"bucket\[(\d+)\]\s+(\d+)\s+-\s+(\d+)\s+hours ago:\s+"
    r"(\d+)\s+messages rx'd\s+(\d+)\s+messages relayed\s+(\d+)\s+messages tx'd"
)
_ENERGY_RE  = re.compile(r'Energy on chn=(\d+): last_rssi=(-?\d+)dBm > avg_rssi=(-?\d+)dBm \(cnt=(\d+)\)')
# RSSI[] detailed samples are DEBUG-level in every log observed so far, and DEBUG
# is skipped by the level guard below — so _RSSI_RE currently never matches and
# fw.rssi_samples stays empty. The matcher is kept wired ahead of a firmware build
# that emits RSSI[] at INFO; until then, energy_samples (TRX INFO, 40K+ per
# session) are the RSSI proxy and are what the UI surfaces. See FwRssiSample.
_RSSI_RE    = re.compile(r'RSSI\[(\d+)\]: avg=(-?\d+) dBm, last=(-?\d+) \[min=(-?\d+), max=(-?\d+)\], num=(\d+)')
_RELAY_RX_RE = re.compile(
    r'Rx: TTL=(\d+), TTL#=(\d+), prevSdr=([0-9a-f]+), currSdr=([0-9a-f]+), '
    r'isCN=(\d+), isVul=(\d+), FF=(\d+)'
)
_ROUTING_RE = re.compile(
    r'Msg-\d+ cmd=\d+: transmitMsg=(\d+), flooding=(\d+), echo=(\d+), vine=(\d+)'
    r' - rxActivity=(\d+), txActivity=(\d+), queue=(\d+)'
)
_NEIGHBOR_RE = re.compile(r'neighborAdd\[\d+\]: update hash=([0-9a-f]+), critical=(\d+), vulnerable=(\d+)')
_FREQ_RE     = re.compile(r'(\d{9})Hz')   # 9-digit Hz values = radio frequencies
_RHC_ORIGIN_RE = re.compile(r'rhc_build_resp: using origin hash (0x[0-9a-f]+)')
_ORIGIN_SHORT_RE = re.compile(r'prevSdr=([0-9a-f]+)')


# Fw* dataclasses live in parser/models.py (single source of truth) and are
# imported above. Field-level docs for each live there.


# ── Detection ─────────────────────────────────────────────────────────────────

def is_fw_log(content: str) -> bool:
    """
    Detect firmware log by bracket pattern on first non-empty lines.
    Checks for [digits-digits, MODULE, LEVEL] with known FW modules.
    """
    fw_modules = {"TRX", "RELAY", "TPORT", "FLSH", "MAIN", "PRNT", "USB", "DEBUG"}
    matches = 0
    for line in content.splitlines()[:30]:
        m = _LINE_RE.match(line.strip())
        if m and m.group(3) in fw_modules:
            matches += 1
            if matches >= 3:
                return True
    return False


# ── Main parser ───────────────────────────────────────────────────────────────

def parse_fw_log(path: Path) -> ParseResult:
    """
    Parse a goTenna relay firmware (UART/USB debug) log.

    Only INFO, ERROR, and WARN lines are processed — DEBUG is skipped.
    Bucket lines are raw text outside the bracket pattern and parsed separately.
    Timestamps are relative ms from boot, not wall clock UTC.
    """
    result = ParseResult(log_format="fw_log", source_filename=path.name)

    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        result.parse_errors.append(f"Cannot read file: {e}")
        return result

    fw = FwLogResult()
    result.fw_log_result = fw

    routing = FwRoutingDecision()
    fw.routing = routing

    rf = FwRfConfig()
    fw.rf_config = rf

    # Bucket tracking — collect all snapshots, keep last per bucket index
    bucket_last_rx: dict[int, FwBucket] = {}       # bucket_idx -> latest FwBucket

    neighbors_seen: set = set()
    timestamps: list = []

    # ── Two-pass approach:
    # Pass 1: bracket lines (INFO/ERROR/WARN only)
    # Pass 2: raw bucket lines (outside bracket pattern)

    lines = content.splitlines()
    fw.total_lines = len(lines)

    in_rf_config = False

    for line in lines:
        raw = line.strip()

        # ── Bucket lines (raw text, outside brackets) ─────────────────────────
        bm = _BUCKET_RE.search(raw)
        if bm:
            b = FwBucket(
                bucket_index=int(bm.group(1)),
                hrs_start=int(bm.group(2)),
                hrs_end=int(bm.group(3)),
                rx=int(bm.group(4)),
                relayed=int(bm.group(5)),
                tx=int(bm.group(6)),
            )
            # RHC bucket history repeats once per health poll. Counts grow
            # monotonically across polls, so the snapshot with the highest rx
            # for a given index is the one from the most recent poll.
            existing = bucket_last_rx.get(b.bucket_index)
            if existing is None or b.rx >= existing.rx:
                bucket_last_rx[b.bucket_index] = b
            continue

        # ── Bracket lines ─────────────────────────────────────────────────────
        m = _LINE_RE.match(raw)
        if not m:
            continue

        ts_abs_str, _ts_delta, module, level, msg = m.groups()
        msg = msg.strip()

        # Skip DEBUG
        if level == "DEBUG":
            fw.skipped_debug += 1
            continue

        fw.parsed_lines += 1
        ts_abs = int(ts_abs_str)
        timestamps.append(ts_abs)

        # ── Origin hash ───────────────────────────────────────────────────────
        if not fw.origin_hash:
            oh = _RHC_ORIGIN_RE.search(msg)
            if oh:
                fw.origin_hash = oh.group(1).replace("0x", "")

        # Best-effort fallback when no RHC origin line is present: the first
        # RELAY Rx prevSdr. prevSdr is the *previous sender*, so on a log whose
        # first RELAY line was relayed from a neighbor this may be that
        # neighbor's hash, not this radio's. The RHC origin above is
        # authoritative; this only fills the gap when it never appears.
        if not fw.origin_hash and module == "RELAY" and "prevSdr=" in msg:
            ps = _ORIGIN_SHORT_RE.search(msg)
            if ps:
                fw.origin_hash = ps.group(1)

        # ── RHC version ───────────────────────────────────────────────────────
        if "rhc_build_resp: version" in msg and not fw.fw_format_version:
            vm = re.search(r'version (0x[0-9a-f]+)', msg)
            if vm:
                fw.fw_format_version = vm.group(1)

        # ── RHC poll count ────────────────────────────────────────────────────
        if "rhc_build_resp: enter" in msg:
            fw.rhc_poll_count += 1

        # ── RF configuration ──────────────────────────────────────────────────
        if module == "TRX" and level == "INFO":
            if "RF Configuration for" in msg:
                in_rf_config = True
                device = re.search(r'RF Configuration for (.+)', msg)
                if device:
                    rf.device_type = device.group(1).strip()

            if in_rf_config:
                if "Tx power:" in msg:
                    tp = re.search(r'Tx power:\s*(\d+)', msg)
                    if tp: rf.tx_power = int(tp.group(1))
                if "bit_rate=" in msg:
                    br = re.search(r'bit_rate=(\d+)', msg)
                    if br:
                        rf.bit_rate = int(br.group(1))
                        in_rf_config = False  # end of config block
                if "Region" in msg:
                    rg = re.search(r'Region (\d+)', msg)
                    if rg: rf.region = int(rg.group(1))
                if "Hz" in msg:
                    freqs = [int(f) for f in _FREQ_RE.findall(msg)]
                    for f in freqs:
                        if f not in rf.frequencies_hz:
                            rf.frequencies_hz.append(f)
                if "Control channels" in msg:
                    cc = re.search(r'Control channels \(\d+\):\s*([\d ]+)', msg)
                    if cc:
                        rf.control_channels = [int(x) for x in cc.group(1).split()]
                if "Data channels" in msg:
                    dc = re.search(r'Data channels \(\d+\):\s*([\d ]+)', msg)
                    if dc:
                        rf.data_channels = [int(x) for x in dc.group(1).split()]

        # ── TRX RSSI and energy ───────────────────────────────────────────────
        if module == "TRX" and level == "INFO":
            em = _ENERGY_RE.search(msg)
            if em:
                fw.energy_samples.append(int(em.group(2)))  # last_rssi

            rm = _RSSI_RE.search(msg)
            if rm:
                fw.rssi_samples.append(FwRssiSample(
                    channel=int(rm.group(1)),
                    avg_dbm=int(rm.group(2)),
                    last_dbm=int(rm.group(3)),
                    min_dbm=int(rm.group(4)),
                    max_dbm=int(rm.group(5)),
                    num=int(rm.group(6)),
                ))

        # ── Relay routing ─────────────────────────────────────────────────────
        if module == "RELAY" and level == "INFO":
            rtm = _ROUTING_RE.search(msg)
            if rtm:
                tx, flood, echo, vine, rx_act, tx_act, queue = rtm.groups()
                if tx == "1":    routing.transmit += 1
                if echo == "1":  routing.echo += 1
                if vine == "1":  routing.vine += 1
                if flood == "1": routing.flood += 1

            if "msg already Rx" in msg:  routing.skip_rx += 1
            if "msg already TX" in msg:  routing.skip_tx += 1

            # Neighbors
            nm = _NEIGHBOR_RE.search(msg)
            if nm:
                h = nm.group(1)
                if h not in neighbors_seen:
                    neighbors_seen.add(h)
                    fw.neighbor_hashes.append(h)

        # ── Errors ────────────────────────────────────────────────────────────
        if level == "ERROR":
            if "Battery stabilization" in msg:
                fw.battery_error_count += 1
            else:
                fw.error_counts[module] = fw.error_counts.get(module, 0) + 1
                if msg not in fw.error_messages and len(fw.error_messages) < 20:
                    fw.error_messages.append(msg)

        # ── Warnings ──────────────────────────────────────────────────────────
        if level == "WARN":
            fw.warn_counts[module] = fw.warn_counts.get(module, 0) + 1
            if msg not in fw.warn_messages and len(fw.warn_messages) < 20:
                fw.warn_messages.append(msg)

    # ── Post-loop assembly ────────────────────────────────────────────────────

    # Buckets — keep latest snapshot, sort by bucket index descending
    fw.buckets = sorted(bucket_last_rx.values(), key=lambda b: b.bucket_index, reverse=True)

    # Timestamps
    if timestamps:
        fw.first_ts_ms = min(timestamps)
        fw.last_ts_ms  = max(timestamps)
        fw.duration_ms = fw.last_ts_ms - fw.first_ts_ms

    # Populate ParseResult.device with what we know
    result.device = DeviceInfo(
        platform="relay_fw",
        callsign=fw.origin_hash or "unknown",
        radio_serial="",   # binary payload — not available in plaintext
        radio_firmware="", # binary payload — not available in plaintext
    )

    # Session timestamps — relative ms, expressed as strings for consistency
    result.session_start = str(fw.first_ts_ms)
    result.session_end   = str(fw.last_ts_ms)

    # DATA LIMITATIONS
    result.parse_errors.append(
        "DATA LIMITATION: Firmware log timestamps are relative ms from boot, "
        "not wall clock UTC — session cannot be pinned to absolute time without "
        "a reference point from a correlated Relay Manager log."
    )
    result.parse_errors.append(
        "DATA LIMITATION: Device serial number and firmware version are in the "
        "binary RHC response payload — not available as plaintext in this log. "
        "Identity shown as origin hash only."
    )
    result.parse_errors.append(
        "DATA LIMITATION: Battery stabilization errors "
        f"({fw.battery_error_count:,} occurrences) are a known firmware quirk "
        "where the stabilization routine fires even when battery is already stable. "
        "Not indicative of hardware failure — pending field validation to confirm."
    )

    return result
