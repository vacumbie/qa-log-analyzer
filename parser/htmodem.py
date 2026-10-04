"""
parser/htmodem.py
Parser for the next-gen radio platform's ht-modem process log (SDR/RF layer:
AD936X transceiver via LIBIIO, Zynq FPGA/PL fabric).

Format: <ctime timestamp> : <message>
        e.g. "Wed Aug 12 05:13:23 2026 : FPGA Version is correct"

Key characteristics:
- Timestamps are wall-clock ctime() format, second precision, no timezone —
  a distinct style from every other supported format (fw_log uses relative
  ms; everything else uses ISO8601).
- A hardware-fault cascade (AD936X PHY device not found) produces ~20
  near-duplicate ERROR lines for one root cause. Collapsed to a single count,
  same pattern fw_log.py already uses for repeated error/warn lines.
- "Found <N> devices" appears twice per session with no distinguishing text
  of its own — once for IIO device enumeration, once for AD5592 device
  enumeration (after "Starting AD5592 init"). Disambiguated by tracking
  whether the AD5592 init line has been seen yet.
- "CSMA QUEUE is Full, dropping packet" carries no packetID of its own — it
  is attributed to the most recently seen TX packet block. A drop line with
  no preceding packet in the session is counted separately as orphaned
  rather than fabricating a packet record.
- Temperatures are Celsius in the raw log; converted to Fahrenheit is a
  display-time concern (this parser stores the raw Celsius values, same
  convention as fw_log/other formats storing raw units).

See docs/parsing-requirements.md "Next-Gen Radio — Modem (ht-modem) Log" and
docs/log-field-definitions.md Format 5 for the full spec.
"""

from __future__ import annotations
import re
from datetime import datetime
from pathlib import Path

from .models import (
    ParseResult, DeviceInfo,
    HtModemResult, HtModemTxPacket, HtModemFreqChange, HtModemPowerChange, HtModemTempSample,
    HtModemTransmitConfirmation,
)

# ── Regex patterns ────────────────────────────────────────────────────────────

# "Wed Aug 12 05:13:23 2026 : <message>"
_LINE_RE = re.compile(r'^(\w{3} \w{3}\s+\d{1,2} \d{2}:\d{2}:\d{2} \d{4})\s*:\s*(.*)$')
_CTIME_FMT = "%a %b %d %H:%M:%S %Y"

_START_OF_LOG_RE  = re.compile(r'^Start of log (.+)$')
_LIBIIO_RE        = re.compile(r'LIBIIO\s*:\s*version\s+(\S+)\s+detected')
_FILTER_BANK_RE   = re.compile(r'Setting filter bank to\s+(\S+)\s+([\d.]+-[\d.]+MHZ)', re.IGNORECASE)
_FOUND_DEVICES_RE = re.compile(r'Found\s+(\d+)\s+devices')
_AD5592_INIT_RE   = re.compile(r'Starting AD5592 init')
_AD936X_MISSING_RE = re.compile(r'Could not find the AD936X PHY device')
_CLOCK_CAL_RE     = re.compile(r'Setting clock calibration offset to\s+(-?\d+)')
_SI4460_CAL_RE    = re.compile(r'Read an SI4460 calibration offset of\s+(-?\d+)')
_GPSD_ERROR_RE    = re.compile(r'Error connecting to gpsd')
_FREQ_RE          = re.compile(r'Setting (RX|TX) freq = (\d+)\.\d+')
_POWER_RE         = re.compile(r'Setting TX power level mode to fixed, Xmit level to\s+([\d.]+)')
_TX_PACKET_RE     = re.compile(
    r'Received packet for encoding\s*:\s*packetID\s*=\s*(\d+)\s+chdesc\s*=\s*(\d+)\s+'
    r'modMode\s*=\s*(\d+)\s+FECMode\s*=\s*(\d+)\s+priority\s*=\s*(\d+)\s+'
    r'localFlag\s*=\s*(\d+)\s+dataLength\s*=\s*(\d+)\s+bytes'
)
_SYMBOL_COUNT_RE  = re.compile(
    r'symbol count \(I/Q Pairs\) after postamble = (\d+), sample count = (\d+), '
    r'encoded Len = (\d+), BCH Val = (0x[0-9a-fA-F]+)'
)
_PAYLOAD_EXT_RE   = re.compile(r'Extended the payload length from\s+(\d+)\s+to\s+(\d+)')
_QUEUED_RE        = re.compile(r'Added packet to xmit queue numinqueue\s*=\s*(\d+)')
_DROPPED_RE       = re.compile(r'CSMA QUEUE is Full,\s*dropping packet')
_TRANSMITTED_RE   = re.compile(
    r'Packet Transmitted\s*:\s*Rev Val\s*=\s*(-?\d+)\s*:\s*Fwd Val\s*=\s*(-?\d+)\s*'
    r'S11\s*=\s*(-?\d+)\s*dB\s*:\s*Temp Val\s*=\s*(-?\d+)'
)
_TEMP_RE          = re.compile(
    r'LPD Temp\s*=\s*([\d.]+)\s+FPD Temp\s*=\s*([\d.]+)\s+PL Temp\s*=\s*([\d.]+)'
)
_FPGA_OK_RE       = re.compile(r'FPGA Version is correct')

_MODEM_MARKERS = ("FPGA Version", "AD936X", "LIBIIO", "ht-modem")


def _fmt_ts(ctime_str: str) -> str:
    """Parse a ctime()-format timestamp and re-emit it in the project's
    standard output format, matching other parsers' timestamp strings."""
    try:
        dt = datetime.strptime(ctime_str.strip(), _CTIME_FMT)
        return dt.strftime("%Y-%m-%d %H:%M:%S.%f")
    except ValueError:
        return ctime_str.strip()


# ── Detection ─────────────────────────────────────────────────────────────────

def is_htmodem_log(content: str) -> bool:
    """
    Detect a next-gen radio ht-modem log: the `<ctime> : ` line prefix
    combined with at least one modem-specific marker in the first 30
    non-empty lines. The prefix alone is too generic (loosely resembles
    other free-text formats), so a marker is required to avoid false
    positives.
    """
    prefix_matches = 0
    saw_marker = False
    for line in content.splitlines()[:30]:
        line = line.strip()
        if not line:
            continue
        m = _LINE_RE.match(line)
        if m:
            prefix_matches += 1
            if any(marker in line for marker in _MODEM_MARKERS):
                saw_marker = True
    return prefix_matches >= 3 and saw_marker


# ── Main parser ───────────────────────────────────────────────────────────────

def parse_htmodem_log(path: Path) -> ParseResult:
    """
    Parse a next-gen radio ht-modem (SDR/RF layer) log.

    Timestamps are wall-clock ctime() format, second precision.
    """
    result = ParseResult(log_format="htmodem", source_filename=path.name)

    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        result.parse_errors.append(f"Cannot read file: {e}")
        return result

    hm = HtModemResult()
    result.htmodem_result = hm

    lines = content.splitlines()
    hm.total_lines = len(lines)

    timestamps: list[str] = []
    seen_ad5592_init = False
    ad936x_failed = False
    current_packet: HtModemTxPacket | None = None

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue

        # "Start of log <ctime>" is not a colon-delimited message line
        som = _START_OF_LOG_RE.match(line)
        if som:
            timestamps.append(_fmt_ts(som.group(1)))
            continue

        m = _LINE_RE.match(line)
        if not m:
            continue

        ts_raw, msg = m.groups()
        ts = _fmt_ts(ts_raw)
        timestamps.append(ts)

        # ── FPGA version check ────────────────────────────────────────────────
        if _FPGA_OK_RE.search(msg):
            hm.fpga_version_ok = True

        # ── LIBIIO / filter bank ──────────────────────────────────────────────
        lm = _LIBIIO_RE.search(msg)
        if lm and not hm.libiio_version:
            hm.libiio_version = lm.group(1)

        fbm = _FILTER_BANK_RE.search(msg)
        if fbm and not hm.filter_bank:
            hm.filter_bank = fbm.group(1)
            hm.filter_range_mhz = fbm.group(2)

        # ── AD5592 init marker (must check before "Found N devices" below,
        #    since the disambiguation depends on whether this has fired yet) ──
        if _AD5592_INIT_RE.search(msg):
            seen_ad5592_init = True

        # ── "Found N devices" — ambiguous per-occurrence; disambiguated by
        #    whether AD5592 init has been seen yet ─────────────────────────────
        fdm = _FOUND_DEVICES_RE.search(msg)
        if fdm:
            n = int(fdm.group(1))
            if seen_ad5592_init:
                hm.ad5592_devices_found = n
            else:
                hm.iio_devices_found = n

        # ── AD936X init-failure cascade — collapsed to one count. Real captures
        #    interleave non-ERROR progress lines ("Using table index...") among
        #    the ERROR lines, so this is NOT a single contiguous window — once
        #    the root-cause line fires, every subsequent ERROR-prefixed line for
        #    the rest of the session is counted as part of the same cascade,
        #    rather than trying to track contiguous blocks that don't actually
        #    stay contiguous in practice. ─────────────────────────────────────
        if _AD936X_MISSING_RE.search(msg):
            ad936x_failed = True
            hm.ad936x_init_error_count += 1
        elif ad936x_failed and msg.startswith("ERROR"):
            hm.ad936x_init_error_count += 1

        # ── Calibration / GPS ─────────────────────────────────────────────────
        ccm = _CLOCK_CAL_RE.search(msg)
        if ccm:
            hm.clock_cal_offset = int(ccm.group(1))

        sim = _SI4460_CAL_RE.search(msg)
        if sim:
            hm.si4460_cal_offset = int(sim.group(1))

        if _GPSD_ERROR_RE.search(msg):
            hm.gpsd_connect_error = True

        # ── Frequency / power control ─────────────────────────────────────────
        frm = _FREQ_RE.search(msg)
        if frm:
            hm.freq_changes.append(HtModemFreqChange(
                timestamp=ts, direction=frm.group(1), hz=int(frm.group(2)),
            ))

        pwm = _POWER_RE.search(msg)
        if pwm:
            hm.power_changes.append(HtModemPowerChange(
                timestamp=ts, xmit_level=float(pwm.group(1)),
            ))

        # ── TX packet lifecycle ────────────────────────────────────────────────
        txm = _TX_PACKET_RE.search(msg)
        if txm:
            current_packet = HtModemTxPacket(
                packet_id=int(txm.group(1)),
                timestamp=ts,
                chdesc=int(txm.group(2)),
                mod_mode=int(txm.group(3)),
                fec_mode=int(txm.group(4)),
                priority=int(txm.group(5)),
                local_flag=int(txm.group(6)),
                data_length=int(txm.group(7)),
            )
            hm.tx_packets.append(current_packet)
            continue  # a packet-encoding line carries no other fields

        symm = _SYMBOL_COUNT_RE.search(msg)
        if symm and current_packet is not None:
            current_packet.symbol_count = int(symm.group(1))
            current_packet.sample_count = int(symm.group(2))
            current_packet.encoded_len  = int(symm.group(3))
            current_packet.bch_val      = symm.group(4)
            continue

        pem = _PAYLOAD_EXT_RE.search(msg)
        if pem and current_packet is not None:
            current_packet.payload_extended_from = int(pem.group(1))
            current_packet.payload_extended_to   = int(pem.group(2))
            continue

        qm = _QUEUED_RE.search(msg)
        if qm and current_packet is not None:
            current_packet.queued = True
            current_packet.numinqueue = int(qm.group(1))
            continue

        if _DROPPED_RE.search(msg):
            if current_packet is not None and current_packet.queued is None:
                current_packet.queued = False
            else:
                # No open packet to attribute this drop to (either none seen
                # yet, or the most recent one already got an outcome) — don't
                # fabricate a packet record for it.
                hm.orphaned_drop_count += 1
            continue

        tram = _TRANSMITTED_RE.search(msg)
        if tram:
            # Does not always immediately follow "Added packet to xmit
            # queue" (2,585 occurrences vs. 2,288 immediately adjacent in a
            # real capture — other lines like a temp reading can intervene),
            # so attach to whichever packet is current, same as the drop
            # attribution above, rather than requiring strict adjacency.
            #
            # Appended, not overwritten, because a packet can end up with two
            # confirmations — but be careful what that means. The line carries
            # no packetID, so attribution is positional, and the modem
            # sometimes starts encoding the NEXT packet before the previous
            # one's confirmation appears. That shifts a confirmation forward
            # by one packet. In the real capture, 43 packets have zero
            # confirmations and 42 have two, and 40 of those 42 sit
            # immediately after a zero-confirmation packet — so most "second
            # confirmations" are the previous packet's, not a retry. Keeping
            # both is still right (overwriting would discard a real
            # observation either way), but the count is not evidence of RF
            # retransmission. Fixing this properly needs packetID matching
            # against the queue, which these lines don't carry.
            if current_packet is not None:
                current_packet.transmissions.append(HtModemTransmitConfirmation(
                    rev_val=int(tram.group(1)),
                    fwd_val=int(tram.group(2)),
                    s11_db=int(tram.group(3)),
                    temp_val=int(tram.group(4)),
                ))
            else:
                hm.orphaned_transmitted_count += 1
            continue

        # ── Thermal ────────────────────────────────────────────────────────────
        tm = _TEMP_RE.search(msg)
        if tm:
            hm.temp_samples.append(HtModemTempSample(
                timestamp=ts,
                lpd_c=float(tm.group(1)),
                fpd_c=float(tm.group(2)),
                pl_c=float(tm.group(3)),
            ))

    # ── Post-loop assembly ────────────────────────────────────────────────────

    if timestamps:
        result.session_start = min(timestamps)
        result.session_end = max(timestamps)

    result.device = DeviceInfo(
        platform="htmodem",
        callsign="unknown",   # no device identity field observed in this log yet
        radio_serial="",
        radio_firmware="",
    )

    if hm.fpga_version_ok is None:
        result.parse_errors.append(
            "DATA LIMITATION — 'FPGA Version is correct' line never appeared in "
            "this log; FPGA version check status is unknown, not confirmed OK."
        )

    if hm.ad936x_init_error_count:
        result.parse_errors.append(
            f"DATA LIMITATION — AD936X PHY device was not found at startup, "
            f"causing {hm.ad936x_init_error_count} cascading RF init errors "
            "(collapsed to this one count rather than itemized). This "
            "indicates the radio's RF front end likely never initialized "
            "correctly for this session."
        )

    if hm.gpsd_connect_error:
        result.parse_errors.append(
            "DATA LIMITATION — Could not connect to gpsd; GPS sync state for "
            "this session is unknown."
        )

    if hm.orphaned_drop_count:
        result.parse_errors.append(
            f"DATA LIMITATION — {hm.orphaned_drop_count} 'CSMA QUEUE is Full' "
            "drop event(s) could not be attributed to a specific TX packet "
            "(no open packet record at the time the drop line appeared)."
        )

    if hm.orphaned_transmitted_count:
        result.parse_errors.append(
            f"DATA LIMITATION — {hm.orphaned_transmitted_count} 'Packet "
            "Transmitted' RF confirmation event(s) could not be attributed "
            "to a specific TX packet."
        )

    # Reported as an attribution limitation, not a retransmission count. A
    # multi-confirmation packet is genuinely ambiguous: 'Packet Transmitted'
    # carries no packetID, so a confirmation arriving after the next packet
    # started encoding is attributed to that next packet instead. Calling
    # these "retransmissions" (as this entry originally did) asserted a
    # hardware fact the same capture contradicts.
    multi_confirmed = [p for p in hm.tx_packets if p.retransmit_count > 0]
    unconfirmed = [p for p in hm.tx_packets if not p.transmitted]
    if multi_confirmed:
        extra = sum(p.retransmit_count for p in multi_confirmed)
        result.parse_errors.append(
            f"DATA LIMITATION — {len(multi_confirmed)} TX packet(s) have more "
            f"than one 'Packet Transmitted' confirmation attributed to them "
            f"({extra} extra confirmation(s)), while {len(unconfirmed)} have "
            "none. The confirmation line carries no packetID, so attribution "
            "is positional: a confirmation logged after the next packet began "
            "encoding is credited to that next packet. An extra confirmation "
            "may therefore be a genuine RF retry or the previous packet's "
            "confirmation — this log cannot distinguish the two."
        )

    if not hm.temp_samples:
        result.parse_errors.append(
            "DATA LIMITATION — No LPD/FPD/PL temperature samples found in "
            "this log."
        )

    return result
