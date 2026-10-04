"""
parser/tak.py
Parses goTenna TAK server CoT (Cursor-on-Target) event streams.

Input format — two real shapes seen in the wild
-------------------------------------------------
1. A JSON array of pre-parsed CoT events (the original sample this parser
   was built against):

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

2. JSON Lines (NDJSON) — a real production capture, one JSON object per
   line, each wrapping the same event shape inside a logger envelope:

    {"level":"info","message":{...same fields as above...},"timestamp":"..."}
    {"level":"info","message":{...},"timestamp":"..."}
    ...

   The outer `level`/`timestamp` are logging-framework metadata, not TAK
   data — only `message` is unwrapped. This shape was discovered from a real
   capture (tak-capture-*.log) after the original array-shaped sample and
   this NDJSON shape turned out to be genuinely different files, not one
   parser handling a filename variant.

Each record (whichever shape it came from) is a CoT event already extracted
from the TAK server's stream (the original CoT XML is preserved in `raw` for
anything the derived fields don't cover). This is NOT a raw multicast/UDP
CoT capture — if a raw XML stream ever needs support, this module would need
a separate ingestion path.

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
- NDJSON lines that fail to parse as JSON, or whose "message" isn't an
  object, are counted and skipped rather than aborting the whole file.

Usage:
    from parser.tak import parse_tak_log
    result = parse_tak_log(Path("tak-stream-2026-07-30T19-42-44.json"))
    result = parse_tak_log(Path("tak-capture-Stratfi_Tak_Stream.log"))
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
    """
    Heuristic content check for the TAK server stream format — either shape.

    Array shape: content starts with '[' and the signature keys appear.
    NDJSON shape: content starts with '{' and the FIRST NON-EMPTY LINE both
    looks like a logger envelope ("message") and carries the signature keys
    inside it — checking one line (not the whole 4000-char snippet) avoids
    false-positiving on some other JSON-Lines format that happens to mention
    these key names anywhere in the file.

    "First non-empty" rather than "first": a concatenated, re-saved or rotated
    capture can arrive with leading blank lines, and reading line 0 literally
    made the envelope test see "" and decline — sending the whole file to the
    diagnostic catch-all, where it parsed as empty with no error at all.
    """
    snippet = content[:4000]
    stripped = snippet.lstrip()
    if stripped.startswith("["):
        return all(key in snippet for key in _SIGNATURE_KEYS)
    if stripped.startswith("{"):
        first_line = next((ln for ln in content.splitlines() if ln.strip()), "")
        if '"message"' in first_line:
            return all(key in first_line for key in _SIGNATURE_KEYS)
    return False


def _load_records(text: str, result: ParseResult) -> Optional[list]:
    """
    Load the list of raw CoT event dicts from either supported shape.
    Returns None (with a parse_errors entry already appended) if nothing
    usable could be extracted.
    """
    stripped = text.lstrip()

    if stripped.startswith("["):
        try:
            records = json.loads(text)
        except json.JSONDecodeError as e:
            result.parse_errors.append(f"Could not parse TAK stream as JSON: {e}")
            return None
        if not isinstance(records, list):
            result.parse_errors.append(
                "TAK stream JSON root is not an array — expected a list of CoT event records."
            )
            return None
        return records

    if stripped.startswith("{"):
        records = []
        skipped_lines = 0
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                wrapper = json.loads(line)
            except json.JSONDecodeError:
                skipped_lines += 1
                continue
            msg = wrapper.get("message") if isinstance(wrapper, dict) else None
            if isinstance(msg, dict):
                records.append(msg)
            else:
                skipped_lines += 1
        if skipped_lines:
            result.parse_errors.append(
                f"{skipped_lines} line(s) in this JSON-Lines capture could not "
                "be parsed as a TAK event envelope ({\"message\": {...}}) and "
                "were skipped."
            )
        if not records:
            result.parse_errors.append(
                "No valid CoT event records found in this JSON-Lines file."
            )
            return None
        return records

    result.parse_errors.append(
        "TAK stream content is neither a JSON array nor JSON-Lines — "
        "unrecognized root character."
    )
    return None


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

    records = _load_records(text, result)
    if records is None:
        return result

    events: list[TakEvent] = []
    skipped = 0
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

        latency_ms = None
        if received_at is not None:
            latency_ms = round((received_at - event_time).total_seconds() * 1000)
            if latency_ms < 0:
                negative_latency_count += 1

        raw_cot = rec.get("raw", "") or ""

        events.append(TakEvent(
            timestamp=_fmt(event_time),
            # `or "Other"` rather than a get() default: an explicit null would
            # otherwise land None in a field annotated str and count in none of
            # the category buckets, same as uid/node_type two lines down.
            category=rec.get("category") or "Other",
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
    # Scoped, and derived from the same property summary.no_fix_count uses, so
    # the sentence and the KPI cannot drift apart. PLI and Marker are the
    # categories expected to carry a position, so a missing one there is a real
    # gap; Chat and server-control records carry the same sentinel but never had
    # a position to lose. Counting them in one number read as five devices
    # losing GPS when one did — the conflation the UI fixed first.
    positional_no_fix = len(result.tak_no_fix_events)
    other_no_fix = sum(
        1 for e in events
        if not e.has_gps_fix and e.category not in ("PLI", "Marker")
    )
    if positional_no_fix:
        sentence = (
            f"{positional_no_fix} PLI/Marker event(s) have no usable position "
            "— either the CoT 0.0/0.0 no-fix sentinel or an incomplete lat/lon "
            "pair. These are not plotted."
        )
        if other_no_fix:
            sentence += (
                f" A further {other_no_fix} Chat/server-control event(s) also "
                "carry no position, but those categories never carry one, so "
                "that is not a lost GPS fix."
            )
        result.parse_errors.append(sentence)
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

    # Named, not just counted: the value is the useful part when a new category
    # appears, and it's what tells someone whether the parser needs updating.
    unrecognized = sorted({e.category for e in events if e.is_unrecognized_category})
    if unrecognized:
        result.parse_errors.append(
            f"{len(unrecognized)} unrecognised event category value(s) — "
            f"{', '.join(repr(c) for c in unrecognized)}. These are stored "
            "verbatim and counted in their own bucket, not folded into "
            "'Other'; the category set is defined server-side and can grow."
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
