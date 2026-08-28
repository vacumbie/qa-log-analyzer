"""
parser/htrouter.py
Parser for the next-gen radio platform's ht-router process log (network/link
layer — manages UDP client/mgt interfaces, forwards protocol messages, and
spawns/monitors the ht-modem process).

Format: two interleaved line shapes.
  1. Discrete events: <ISO8601 with microseconds>Z: <message>
  2. A periodic counter snapshot: ~20 of those discrete lines (input.*,
     output.*, connected) emitted together roughly every 10s, which must be
     grouped into ONE RouterStatSnapshot record, not 20 separate events.

Also present: two startup banner lines in a THIRD, different timestamp
format (space-separated, no microseconds, no Z) —
    "<Y-m-d H:M:S> Starting ht-router (<path>)..."
    "<Y-m-d H:M:S> ht-router started (pid <n>)"
and a handful of genuinely un-timestamped internal trace lines
("output.ready <- ...") right at startup, which are counted but not parsed.

Key characteristics:
- Four real captures showed DIFFERENT snapshot schemas, in two independent
  ways. A session with zero modem-transmit activity never emits
  output.time_outs / .bottom.timed_out / .modem_xmit_failed / .tap.frames /
  .overhead[] / .xmit_completion[] at all; and two of the four never report
  the input.* validity/error counters (bad_crc, wrong_link_version,
  too_short.*, subframe.*_error) either.
  Every RouterStatSnapshot field is therefore Optional; absence is not zero.
- Snapshots are retained in full — no downsampling at parse time. Trimming
  for display is deliberately deferred to the API/UI layer.
- "reopened log file" is a session/rotation boundary; counters reset after
  it, so it is recorded but not treated as a continuation point.
- Several discrete event types (clinfo, bcast_hub_forward, echo_info, the
  "nb output: aggr..." aggregation-frame detail line) are tallied by type in
  `unparsed_event_counts` rather than deep-parsed — flagged honestly as a
  DATA LIMITATION rather than silently dropped.

See docs/parsing-requirements.md "Next-Gen Radio — Router (ht-router) Log"
and docs/log-field-definitions.md Format 6 for the full spec.
"""

from __future__ import annotations
import re
from datetime import datetime
from pathlib import Path

from .models import (
    ParseResult, DeviceInfo,
    HtRouterResult, RouterStatSnapshot, RouterHistogramBucket,
    RouterProtocolMessage, RouterForwardEvent, RouterTransmission,
)

# ── Regex patterns ────────────────────────────────────────────────────────────

# "2026-08-12T05:13:22.340729Z: <message>"
_LINE_RE = re.compile(r'^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+)Z:\s?(.*)$')

# Startup banner lines use a different, timestamp-only-to-the-second format:
# "2026-08-12 05:13:22 Starting ht-router (/usr/bin/ht-router)..."
_BANNER_START_RE = re.compile(
    r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\s+Starting ht-router'
)
_BANNER_PID_RE = re.compile(
    r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\s+ht-router started \(pid (\d+)\)'
)

_UDP_SOCKET_RE   = re.compile(r'local UDP socket ([\d.]+:\d+)')
_US_WARN_RE      = re.compile(r'^us_warn\b')
_AGHUB_RE        = re.compile(r'created aghub_tick event, aghub (0x[0-9a-f]+)')
_MODEM_START_RE  = re.compile(r'nb_modem_start: started ht-modem pid (\d+)')
_REOPENED_RE     = re.compile(r'^reopened log file')

_UDP_INPUT_RE = re.compile(
    r'udp input: udp idx (\d+) peer ([0-9a-f]+:\d+) : '
    r'client-hdr versflags version (\d+), options \w+, next-proto \w+ \| '
    r'mgt-hdr dst (0x[0-9a-f]+|any), src (0x[0-9a-f]+|none), version (\d+), '
    r'type ([\w-]+), direction (\w+)'
)
_UDP_OUTPUT_RE = re.compile(
    r'udp output: udp idx (\d+):\s*'
    r'client-hdr versflags version (\d+), options \w+, next-proto \w+ \| '
    r'mgt-hdr dst (0x[0-9a-f]+|any), src (0x[0-9a-f]+|none), version (\d+), '
    r'type ([\w-]+), direction (\w+)'
)
_FORWARD_RE = re.compile(
    r'mgt_hub_forward\.548:\s*request type (\d+) for (0x[0-9a-f]+):\s*'
    r'sent to (\d+) client\(s\), skipped (\d+) with no session'
)
_TRANSMISSION_RE = re.compile(r'^transmission (\d+) finished in (\d+) ns')

# Simple "<key> <int>" snapshot lines, mapped to RouterStatSnapshot field names.
_SNAPSHOT_INT_FIELDS = {
    "input.too_short.link_hdr":                 "input_too_short_link_hdr",
    "input.too_short.link_payload":             "input_too_short_link_payload",
    "input.too_short.link_crc":                 "input_too_short_link_crc",
    "input.wrong_link_version":                 "input_wrong_link_version",
    "input.crc_present":                        "input_crc_present",
    "input.bad_crc":                            "input_bad_crc",
    "input.subframe.no_protocol":               "input_subframe_no_protocol",
    "input.subframe.logical_recv_error":        "input_subframe_logical_recv_error",
    "input.subframe.family_recv_error":         "input_subframe_family_recv_error",
    "input.subframe.count":                    "input_subframe_count",
    "input.traffic[aggr_next_proto_ag]":        "input_traffic_ag",
    "input.ctl":                                "input_ctl",
    "input.sts":                                "input_sts",
    "input.total_frames":                       "input_total_frames",
    "input.total_bytes":                        "input_total_bytes",
    "input.total_m2m":                          "input_total_m2m",
    "input.m2m_by_type[m2m_type_xmit]":         "input_m2m_xmit",
    "input.m2m_by_type[m2m_type_control]":      "input_m2m_control",
    "input.m2m_by_type[m2m_type_recv]":         "input_m2m_recv",
    "input.m2m_by_type[m2m_type_status]":       "input_m2m_status",
    "input.m2m_by_type[m2m_type_xmit_status]":  "input_m2m_xmit_status",
    "output.traffic[aggr_next_proto_ag].ok":    "output_traffic_ag_ok",
    "output.traffic[aggr_next_proto_ag].fail":  "output_traffic_ag_fail",
    "output.ctl.ok":                            "output_ctl_ok",
    "output.ctl.fail":                          "output_ctl_fail",
    "output.sts.ok":                            "output_sts_ok",
    "output.sts.fail":                           "output_sts_fail",
    "output.aggregation.subframes":             "output_aggregation_subframes",
    "output.aggregation.frames":                "output_aggregation_frames",
    "output.total_bytes":                       "output_total_bytes",
    "output.time_outs":                         "output_time_outs",
    "output.bottom.timed_out":                  "output_bottom_timed_out",
    "output.modem_xmit_failed":                 "output_modem_xmit_failed",
    "output.tap.frames":                        "output_tap_frames",
}
_SNAPSHOT_KV_RE = re.compile(r'^([\w.\[\]]+)\s+(\d+)$')
_HISTOGRAM_RE = re.compile(
    r'^output\.(overhead|xmit_completion)\[(\d+)\]\s*\(\[(\d+),\s*(\d+)\]\s*(?:bytes|ms)\)\s*(\d+)$'
)
_CONNECTED_RE = re.compile(r'^connected\s+([01])$')

# Discrete event types tallied but not deep-parsed. Matched against the start
# of the message (after the timestamp), longest/most-specific patterns first.
_UNPARSED_EVENT_PATTERNS = [
    ("clinfo",                          re.compile(r'^clinfo\b')),
    ("bcast_hub_forward",               re.compile(r'^bcast_hub_forward\.\d+:')),
    ("client_sessionful_iffamily_send", re.compile(r'^client_sessionful_iffamily_send\.\d+:')),
    ("echo_info",                       re.compile(r'^echo_info\b')),
    ("nb_output_aggregation",           re.compile(r'^nb output:')),
    ("nb_connect",                      re.compile(r'^nb_connect:')),
    ("us_info",                         re.compile(r'^us_info\b')),
    ("ag_warn",                         re.compile(r'^ag_warn\b')),
    ("enter",                           re.compile(r'^enter$')),
]

_ROUTER_MARKERS = ("ht-router", "aghub_init", "input.total_m2m", "output.modem_xmit_failed", "mgt_hub_forward")


# ── Detection ─────────────────────────────────────────────────────────────────

def is_htrouter_log(content: str) -> bool:
    """
    Detect a next-gen radio ht-router log: distinctive stat-counter key
    vocabulary (input.total_m2m, output.*, connected) or explicit ht-router
    process markers in the first portion of the file. This vocabulary does
    not overlap with any other supported format.
    """
    snippet = content[:4000]
    if "input.total_m2m" in snippet and "output." in snippet:
        return True
    return any(marker in snippet for marker in _ROUTER_MARKERS)


# ── Main parser ───────────────────────────────────────────────────────────────

def parse_htrouter_log(path: Path) -> ParseResult:
    """
    Parse a next-gen radio ht-router (network/link layer) log.

    Groups the periodic ~20-line counter snapshot into one RouterStatSnapshot
    per group (terminated by the "connected <0|1>" line), rather than storing
    20 unrelated per-line records. Retains every snapshot — no downsampling.
    """
    result = ParseResult(log_format="htrouter", source_filename=path.name)

    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        result.parse_errors.append(f"Cannot read file: {e}")
        return result

    hr = HtRouterResult()
    result.htrouter_result = hr

    lines = content.splitlines()
    hr.total_lines = len(lines)

    timestamps: list[str] = []
    pending: RouterStatSnapshot | None = None

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue

        # ── Startup banner lines (different timestamp format entirely) ───────
        if _BANNER_START_RE.match(line):
            continue  # session start comes from the first real Z-timestamp instead
        pidm = _BANNER_PID_RE.match(line)
        if pidm:
            hr.router_pid = int(pidm.group(1))
            continue

        m = _LINE_RE.match(line)
        if not m:
            # Genuinely un-timestamped internal trace lines (e.g. "output.ready
            # <- ..." at startup) — counted, not parsed.
            hr.untimestamped_line_count += 1
            continue

        ts, msg = m.groups()
        timestamps.append(ts)

        # A timestamp with nothing after it (blank separator line before a
        # snapshot block) carries no information — skip without counting it
        # as unparsed noise.
        if not msg:
            continue

        # ── Rotation marker ────────────────────────────────────────────────────
        if _REOPENED_RE.match(msg):
            hr.rotation_markers.append(ts)
            # Counters reset after a reopen — don't carry a half-built
            # snapshot across the boundary.
            pending = None
            continue

        # ── Process lifecycle ─────────────────────────────────────────────────
        mpm = _MODEM_START_RE.search(msg)
        if mpm:
            hr.modem_pid = int(mpm.group(1))
            continue

        usm = _UDP_SOCKET_RE.search(msg)
        if usm:
            hr.udp_sockets.append(usm.group(1))
            continue

        if _US_WARN_RE.match(msg):
            hr.socket_warning_count += 1
            continue

        agm = _AGHUB_RE.search(msg)
        if agm and not hr.aghub_init_addr:
            hr.aghub_init_addr = agm.group(1)
            continue

        # ── Protocol messages ──────────────────────────────────────────────────
        pmm = _UDP_INPUT_RE.search(msg)
        if pmm:
            hr.protocol_messages.append(RouterProtocolMessage(
                timestamp=ts,
                io_direction="input",
                udp_idx=int(pmm.group(1)),
                peer=pmm.group(2),
                dst=pmm.group(4),
                src=pmm.group(5),
                version=int(pmm.group(6)),
                msg_type=pmm.group(7),
                direction=pmm.group(8),
            ))
            continue

        pom = _UDP_OUTPUT_RE.search(msg)
        if pom:
            hr.protocol_messages.append(RouterProtocolMessage(
                timestamp=ts,
                io_direction="output",
                udp_idx=int(pom.group(1)),
                peer=None,
                dst=pom.group(3),
                src=pom.group(4),
                version=int(pom.group(5)),
                msg_type=pom.group(6),
                direction=pom.group(7),
            ))
            continue

        fwm = _FORWARD_RE.search(msg)
        if fwm:
            hr.forward_events.append(RouterForwardEvent(
                timestamp=ts,
                request_type=int(fwm.group(1)),
                dst=fwm.group(2),
                sent_count=int(fwm.group(3)),
                skipped_count=int(fwm.group(4)),
            ))
            continue

        # ── Transmission completion (router-side counterpart to the modem's
        #    TX packet lifecycle) ──────────────────────────────────────────────
        txm = _TRANSMISSION_RE.match(msg)
        if txm:
            hr.transmissions.append(RouterTransmission(
                timestamp=ts,
                transmission_id=int(txm.group(1)),
                duration_ns=int(txm.group(2)),
            ))
            continue

        # ── Periodic stat snapshot — histogram lines first (more specific) ────
        hgm = _HISTOGRAM_RE.match(msg)
        if hgm:
            if pending is None:
                pending = RouterStatSnapshot(timestamp=ts)
            bucket = RouterHistogramBucket(
                bucket=int(hgm.group(2)),
                range_min=int(hgm.group(3)),
                range_max=int(hgm.group(4)),
                count=int(hgm.group(5)),
            )
            if hgm.group(1) == "overhead":
                pending.output_overhead = bucket
            else:
                pending.output_xmit_completion = bucket
            continue

        cm = _CONNECTED_RE.match(msg)
        if cm:
            if pending is None:
                pending = RouterStatSnapshot(timestamp=ts)
            pending.connected = (cm.group(1) == "1")
            hr.stat_snapshots.append(pending)
            pending = None
            continue

        kvm = _SNAPSHOT_KV_RE.match(msg)
        if kvm and kvm.group(1) in _SNAPSHOT_INT_FIELDS:
            if pending is None:
                pending = RouterStatSnapshot(timestamp=ts)
            field_name = _SNAPSHOT_INT_FIELDS[kvm.group(1)]
            setattr(pending, field_name, int(kvm.group(2)))
            continue

        # ── Discrete event types tallied but not deep-parsed ──────────────────
        matched_unparsed = False
        for label, pattern in _UNPARSED_EVENT_PATTERNS:
            if pattern.match(msg):
                hr.unparsed_event_counts[label] = hr.unparsed_event_counts.get(label, 0) + 1
                matched_unparsed = True
                break
        if matched_unparsed:
            continue

        # Anything else falls through uncounted — this is the residual for
        # content genuinely not seen in the four sample captures.
        hr.unparsed_event_counts["_other"] = hr.unparsed_event_counts.get("_other", 0) + 1

    # A trailing pending snapshot with no closing "connected" line (file cut
    # off mid-block) is still real data — keep it rather than discard it.
    if pending is not None:
        hr.stat_snapshots.append(pending)

    # ── Post-loop assembly ────────────────────────────────────────────────────

    if timestamps:
        result.session_start = min(timestamps)
        result.session_end = max(timestamps)
    hr.session_start = result.session_start

    result.device = DeviceInfo(
        platform="htrouter",
        callsign="unknown",
        radio_serial="",
        radio_firmware="",
    )

    # ── DATA LIMITATIONS ───────────────────────────────────────────────────────
    if hr.modem_pid is None:
        result.parse_errors.append(
            "DATA LIMITATION — No 'nb_modem_start' line found; this session's "
            "corresponding ht-modem process (if any) cannot be identified by PID."
        )

    if hr.socket_warning_count:
        result.parse_errors.append(
            f"DATA LIMITATION — {hr.socket_warning_count} 'us_warn' socket "
            "warning(s) (e.g. sendto: Invalid argument) occurred; exact cause "
            "per warning is not yet decoded — see docs/parsing-requirements.md."
        )

    unparsed_total = sum(v for k, v in hr.unparsed_event_counts.items())
    if unparsed_total:
        breakdown = ", ".join(f"{k}: {v}" for k, v in sorted(hr.unparsed_event_counts.items()))
        result.parse_errors.append(
            f"DATA LIMITATION — {unparsed_total} discrete event line(s) of "
            f"types not yet structurally parsed, tallied by type only ({breakdown})."
        )

    if hr.untimestamped_line_count:
        result.parse_errors.append(
            f"DATA LIMITATION — {hr.untimestamped_line_count} line(s) had no "
            "recognizable timestamp (internal startup trace lines) and were "
            "counted but not parsed."
        )

    return result
