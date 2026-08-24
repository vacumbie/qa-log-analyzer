"""
parser/tak.py
Parses goTenna TAK server CoT (Cursor-on-Target) event streams.

Input format
------------
A JSON array of pre-parsed CoT events, e.g.:

    [
      {
        "callsign": "PICKUP", "category": "PLI", "lat": 30.153289,
        "lon": -85.664925, "nodeType": "Android", "parentCallsign": null,
        "platform": "ATAK-CIV", "raw": "<event ...>...</event>",
        "receivedAt": "2026-07-30T19:27:01.907Z",
        "time": "2026-07-30T19:24:54Z", "type": "a-f-G-U-C",
        "uid": "ANDROID-9c47b9ce85beb696"
      },
      ...
    ]

Each record is a CoT event already extracted from the TAK server's stream
(the original CoT XML is preserved in `raw` for anything the derived fields
don't cover). This is NOT a raw multicast/UDP CoT capture — if a raw XML
stream ever needs support, this module would need a separate ingestion path.

category values observed:
  PLI     — a-f-G-U-* friendly ground unit position report
  Marker  — a-f-G-U-C-I "I" (icon) variant, seen from WebTAK clients
  Chat    — b-t-f GeoChat text message
  Other   — server plumbing, e.g. t-x-takp-v TAK protocol/version handshake
            (TakControl/TakServerVersionInfo) — no device identity or position

Data limitations (returned in parse_errors)
-------------------------------------------
- lat/lon of exactly (0.0, 0.0) is the CoT convention for "no GPS fix" (paired
  with a hae/ce/le sentinel of 999999.0 or 9999999.0 in the raw XML), not a
  real position at (0,0). These events are flagged has_gps_fix=False; do not
  plot them.
- latency_ms (receivedAt - time) can be negative when a source device's
  clock runs fast relative to the TAK server. This has been observed in the
  sample data (e.g. repeated WebTAK PLI updates) and is preserved as-is
  rather than clamped, since the skew itself is the signal of interest
  (see backlog item P8, cross-device timestamp skew).
- Chat (b-t-f) message bodies are not extracted from `raw` in this version;
  only the envelope (sender callsign, timestamps) is captured.

Usage:
    from parser.tak import parse_tak_log
    result = parse_tak_log(Path("tak-stream-2026-07-30T19-42-44.json"))
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from .models import ParseResult, TakEvent, TakServerInfo

_TS_FMT_OUT = "%Y-%m-%d %H:%M:%S.%f"

# Content-based detection: these keys together are distinctive to this format
# and don't overlap with ATAK plugin logs (logId/connectionState/atakVersion)
# or any other supported format.
_SIGNATURE_KEYS = ('"receivedAt"', '"nodeType"', '"category"')

_SERVER_VERSION_RE = re.compile(r'serverVersion="([^"]*)"')
_API_VERSION_RE = re.compile(r'apiVersion="([^"]*)"')


def is_tak_log(content: str) -> bool:
    """Heuristic content check for the TAK server stream format."""
    snippet = content[:4000]
    if not snippet.lstrip().startswith("["):
        return False
    return all(key in snippet for key in _SIGNATURE_KEYS)


# Elements carried in the CoT XML that this parser does not promote to fields.
# Each is real telemetry a reader could reasonably expect to find — a battery
# percentage and a device model especially — so their absence is reported rather
# than left for someone to discover by grepping raw_cot.
_UNEXTRACTED_XML = (
    ("<status battery", "battery percentage"),
    ("<takv ", "device model / OS / TAK version"),
    ("<track ", "speed and course"),
)


def _read_coordinates(rec: dict):
    """Return (lat, lon) as floats, or (None, None) if either is unusable.

    Both-or-neither on purpose: a record carrying one coordinate has no position,
    and the missing half must not become 0.0 — see the caller. A non-numeric
    value is treated the same way as an absent one; 0 and 0.0 are real values and
    pass through, since (0,0) is the CoT no-fix sentinel the caller tests for.
    """
    lat, lon = rec.get("lat"), rec.get("lon")
    if lat is None or lon is None:
        return None, None
    try:
        return float(lat), float(lon)
    except (TypeError, ValueError):
        return None, None


def _count_unextracted_xml(events) -> list:
    """Count events whose raw CoT XML carries each unextracted element.

    Data-driven on purpose: a stream with no <takv> elements should not be told
    its <takv> data was dropped. Returns [(label, count), ...] for those
    actually present, so the caller can stay silent when the list is empty.
    """
    counts = []
    for marker, label in _UNEXTRACTED_XML:
        n = sum(1 for e in events if marker in e.raw_cot)
        if n:
            counts.append((label, n))
    return counts


def _parse_iso(ts: Optional[str]) -> Optional[datetime]:
    if not ts:
        return None
    try:
        # Normalize trailing 'Z' (Zulu/UTC) to an offset fromisoformat accepts
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None


def _fmt(dt: Optional[datetime]) -> str:
    return dt.strftime(_TS_FMT_OUT) if dt else ""


def _extract_server_info(raw_cot: str) -> Optional[TakServerInfo]:
    sv = _SERVER_VERSION_RE.search(raw_cot)
    av = _API_VERSION_RE.search(raw_cot)
    if not sv and not av:
        return None
    return TakServerInfo(
        server_version=sv.group(1) if sv else "",
        api_version=av.group(1) if av else "",
    )


def parse_tak_log(path: Path) -> ParseResult:
    result = ParseResult(log_format="tak", source_filename=path.name)

    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        result.parse_errors.append(f"Could not read file: {e}")
        return result

    try:
        records = json.loads(text)
    except json.JSONDecodeError as e:
        result.parse_errors.append(f"Could not parse TAK stream as JSON: {e}")
        return result

    if not isinstance(records, list):
        result.parse_errors.append(
            "TAK stream JSON root is not an array — expected a list of CoT event records."
        )
        return result

    events: list[TakEvent] = []
    skipped = 0
    no_fix_count = 0
    missing_coord_count = 0
    negative_latency_count = 0
    server_info: Optional[TakServerInfo] = None
    all_times: list[datetime] = []

    for i, rec in enumerate(records):
        if not isinstance(rec, dict):
            skipped += 1
            continue

        event_time = _parse_iso(rec.get("time"))
        if event_time is None:
            result.parse_errors.append(
                f"Record {i}: missing or unparseable 'time' field — skipped."
            )
            skipped += 1
            continue

        received_at = _parse_iso(rec.get("receivedAt"))

        # A CoT <point> carries lat and lon together, so a record with only one
        # of them is malformed rather than positioned. Coercing the missing half
        # to 0.0 would invent a coordinate on the equator or prime meridian and
        # — because the sentinel test below only fires on the (0,0) *pair* —
        # would mark that fabricated position as a real fix. Both stay None.
        lat, lon = _read_coordinates(rec)
        if lat is None or lon is None:
            has_fix = False
            missing_coord_count += 1
        else:
            has_fix = not (lat == 0 and lon == 0)
            if not has_fix:
                no_fix_count += 1

        latency_ms = None
        if received_at is not None:
            latency_ms = round((received_at - event_time).total_seconds() * 1000)
            if latency_ms < 0:
                negative_latency_count += 1

        raw_cot = rec.get("raw", "") or ""

        events.append(TakEvent(
            timestamp=_fmt(event_time),
            category=rec.get("category", "Other"),
            cot_type=rec.get("type", ""),
            uid=rec.get("uid", "") or "",
            callsign=rec.get("callsign"),
            node_type=rec.get("nodeType", "") or "",
            platform=rec.get("platform"),
            parent_callsign=rec.get("parentCallsign"),
            lat=lat,
            lon=lon,
            has_gps_fix=has_fix,
            received_at=_fmt(received_at),
            latency_ms=latency_ms,
            raw_cot=raw_cot,
        ))
        all_times.append(event_time)

        if server_info is None and rec.get("category") == "Other":
            server_info = _extract_server_info(raw_cot)

    result.tak_events = events
    result.tak_server_info = server_info

    if all_times:
        result.session_start = _fmt(min(all_times))
        result.session_end = _fmt(max(all_times))

    if skipped:
        result.parse_errors.append(
            f"{skipped} of {len(records)} record(s) were malformed or missing a "
            "'time' field and were skipped."
        )
    # Reported separately from the no-fix count below: a (0,0) sentinel is a
    # device saying "I have no fix", while a missing coordinate is the record
    # itself being incomplete. Folding them together would misattribute a
    # malformed export to GPS trouble in the field.
    if missing_coord_count:
        result.parse_errors.append(
            f"{missing_coord_count} event(s) carry only one of lat/lon (or a "
            "non-numeric value) — no position could be read, and the missing "
            "coordinate was not defaulted to 0. These are excluded from the map "
            "alongside no-fix events."
        )
    if no_fix_count:
        result.parse_errors.append(
            f"{no_fix_count} event(s) reported no GPS fix (lat/lon sentinel "
            "0.0/0.0) — position for these is not meaningful and should not "
            "be plotted."
        )
    if negative_latency_count:
        result.parse_errors.append(
            f"{negative_latency_count} event(s) show negative server latency "
            "(receivedAt before time), indicating the source device's clock "
            "is running fast relative to the TAK server rather than a data error."
        )
    if not events:
        result.parse_errors.append("No valid CoT event records found in this file.")

    if any(e.category == "Chat" for e in events):
        result.parse_errors.append(
            "DATA LIMITATION — Chat message bodies not extracted: only the "
            "envelope (sender callsign, timestamps) is captured from GeoChat "
            "(b-t-f) records in this version; the <remarks> text is not parsed."
        )

    unextracted = _count_unextracted_xml(events)
    if unextracted:
        detail = ", ".join(f"{label} ({n} event(s))" for label, n in unextracted)
        result.parse_errors.append(
            "DATA LIMITATION — Telemetry present in the raw CoT XML is not "
            f"extracted into fields: {detail}. It remains in raw_cot, which the "
            "API does not serialize, so it is not reachable from the UI or an "
            "export."
        )

    return result
