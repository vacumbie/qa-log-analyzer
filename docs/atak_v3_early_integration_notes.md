# ATAK Plugin v3.0 — Early Integration Notes
_Created: 2026-07-29_

## Purpose

This doc tracks what data the ATAK plugin v3.0 build actually emits, as observed
in the field, while the plugin/FW/radio combo is still in early integration.
The goal is a running baseline so we can tell "this field is genuinely not
available yet" apart from "the parser is missing something." Expect this doc
to go stale fast as the plugin matures — that's fine, it's meant to be
disposable. Update it whenever a new log reveals something new (or something
that used to be missing shows up).

## Source Logs

| File | Callsign (device) | GID | Session window | Messages |
|---|---|---|---|---|
| `diagnostic_BARK_65043_2026-07-28_15_09_17_944.log` | BARK | 65043 | 2026-07-28 18:06:21 → 20:02:15 UTC | 1,215 (713 sent / 502 recv) |
| `diagnostic_EUD-009_54498_2026-07-29_04_02_14_14.log` | EUD-009 | 54498 | 2026-07-28 20:17:28 → 21:02:16 UTC | 267 (90 sent / 177 recv) |

Both: app version `3.0.0 (dae7d160) - [5.6.0]`, ATAK version `5.6.0.21`,
device `Samsung SM-S931U1`, Android API 36. Parsed cleanly by the existing
`atak` parser — 0 parse errors on either file.

## Filename convention (changed)

Old: `diagnostic_ATAK_<CALLSIGN>_<GID>_<DATE>_<TIME>.log` (literal `ATAK_` segment).
New (v3.0): `diagnostic_<CALLSIGN>_<GID>_<DATE>_<TIME>.log` — no `ATAK_` segment.

Format *detection* (`_detect_format` in `api/routes/parse.py`) still works —
it falls back to content sniffing (`logId`, `atakVersion` in the JSON) when the
filename doesn't match. But `atak.py`'s `_FILENAME_RE` requires the old
convention to extract callsign/GID from the filename, and there is no other
code path that sets `device.callsign`. Net effect: **own-device callsign comes
back blank** on every v3.0-named log. GID is unaffected (it has a fallback via
`senderGid` on the device's own sent messages). This is a parser gap, not a
data limitation from the FW/radio — tracked as a fix candidate whenever it's
worth doing given the naming may change again.

## What's present and reliable right now

- **App metadata** — version, build number, ATAK version, device model, API
  level. Populated on every log seen so far.
- **Message parsing** — `pli` and `textChat` message types seen; both parse
  clean.
- **Delivery status** — `SENT`, `FULLY_RECEIVED`, and (once) `DELIVERED` seen.
  No `FAILED`/timeout status observed yet in this sample.
- **Message protocol** — mostly `BROADCAST`; one `PRIVATE` message seen in the
  EUD-009 log.
- **Hop count** — populated (values 2–5 seen) — mesh relaying is visibly
  functioning across multiple hops.
- **Peer identity** — other devices' callsigns/GIDs come through fine via
  their own `senderCallsign`/`senderGid` on received messages (e.g. BIXBY,
  KNIGHTRIDER, HIKE, EAGLE CLIFF, EUD-025, EUD-013 all appeared). It's only the
  *local* device's own callsign that's affected by the filename issue above.
- **Lifecycle events** — `deviceConnected`/`deviceDisconnected`,
  `ledStateUpdated`, `pliSettingUpdated` all seen and parsed.
- **Session continuity** — no gaps detected in either log (continuous
  sessions).

## What's missing or inconsistent — flagged honestly

- **No device-health telemetry** — zero `connectionState` records in either
  log. That means **no battery %, thermal, firmware version, or radio-health
  snapshot** for this log type as it currently stands. Thermal/Battery tabs
  render empty. Unknown whether this is "not implemented yet in this FW/plugin
  build" or "just didn't fire in these two sessions" — needs more samples to
  tell apart.
- **RSSI always `0`** — every single message in both logs, sent and received,
  reports `rssi: 0`. The field exists and the parser reads it correctly; it
  simply isn't being populated by this FW/radio combo yet. No signal-strength
  insight is currently possible from this log type.
- **PLI interval churn** — BARK's session shows four distinct interval values
  (`5`, `15`, `60`, and blank `""`) within one continuous session. Could be
  legitimate setting changes mid-session, could be a reporting quirk on the
  new FW. Worth watching across more logs before treating it as either normal
  or a bug.
- **No SDK Logging 2.0 (`sdkError`) records** — expected, since these are
  "regular" logs rather than "enhanced" debug logs; not a gap.

## Not yet observed (unknown, not confirmed absent)

These simply haven't shown up in the two logs reviewed so far — no
conclusion either way:
- `fileTransfer` messages
- `firmwareUpdate`, `powerLevelUpdated`, `frequencyUpdated` events
- Any delivery status other than `SENT` / `FULLY_RECEIVED` / `DELIVERED`
  (e.g. `FAILED`)

## How to use this doc

- Add a row to the Source Logs table each time a new v3.0 log is reviewed.
- Move items between "missing" and "present" sections as the picture
  clarifies — don't just delete the old note, it's useful to see what changed
  and when.
- Once the plugin/FW stabilizes and this stops being "early integration,"
  fold anything durable into `CLAUDE.md`'s Known Data Limitations table and
  retire this doc.
