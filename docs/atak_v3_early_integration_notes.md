# ATAK Plugin v3.0 — Early Integration Notes
_Created: 2026-07-29 · Updated: 2026-10-05 (build `ebb7b8c5` logs)_

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
| `diagnostic_BAMA_90361464844400_2026-10-02_13_26_58_66.log` | BAMA | 90361464844400 | 2026-10-02 17:01:56 → 17:27:00 UTC | 147 (33 sent / 114 recv) |
| `diagnostic_TESTLINE_90168163972632_2026-10-02_13_26_57_921.log` | TESTLINE | 90168163972632 | 2026-10-02 17:01:55 → 17:27:00 UTC | 149 (34 sent / 115 recv) |

Both: app version `3.0.0 (dae7d160) - [5.6.0]`, ATAK version `5.6.0.21`,
device `Samsung SM-S931U1`, Android API 36. Parsed cleanly by the existing
`atak` parser — 0 parse errors on either file.

**2026-10-02 logs (newer build):** app version `3.0.0 (ebb7b8c5) - [5.6.0]`,
ATAK version `5.6.0.17`, build number `1790946073` on both. BAMA: `Samsung
SM-S901U1` (Galaxy S22); TESTLINE: `Samsung SM-S931U` (Galaxy S25); both
Android API 36. Radio `PRO_X_2`, firmware `3.2.11`, chip `LEGACY_NXP`, BLE.
Same group test as the four Pro+ logs in
`docs/proplus_early_integration_notes.md`. Detected as `atak` and parsed with
0 parse errors (one informational sdkError DATA LIMITATION each).

**GID format changed between builds:** the July (`dae7d160`) logs carry short
GIDs (`65043`, `54498`); the October (`ebb7b8c5`) logs carry 14-digit GIDs, the
same form the Pro+ app uses.

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

**Update 2026-10-04:** fixed in PR #33 — `_FILENAME_RE` now treats the `ATAK_`
segment as optional, and the own sent `senderCallsign` is a fallback. Both
October logs return their callsign (BAMA, TESTLINE) and GID from the filename.

**Correction 2026-10-05:** the original 2026-10-04 statement (callsign and GID
come "from the filename") did not hold in either path. The real October filenames
do not match `_FILENAME_RE` even on a direct `parse_atak_log()` call — they use a
space before the time and a dot before the milliseconds
(`diagnostic_<CALLSIGN>_<GID>_2026-10-02 13_26_58.66.log`). And through
`POST /parse`, the parser never sees the real name anyway: `api/routes/parse.py` writes the upload to a
`NamedTemporaryFile` and calls `parse_atak_log(tmp_path)`, so `_FILENAME_RE` sees
a temp name (`tmpXXXX.log`) for **every** ATAK upload; only
`result.source_filename` is restored afterwards. What the UI shows for the
October logs is therefore always the content fallbacks: callsign from the device's
own sent `senderCallsign`, GID from the first Device Health `gid` or the own sent `senderGid`, whichever is logged first. The
same applies to the "own-device callsign comes back blank" paragraph above: via
the API the filename was never the source. A log with no sent messages would show
a blank callsign. Tracked as "Upload filename not passed to parsers" in
`docs/ui-requirements.md`.

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

**New in build `ebb7b8c5` (2026-10-02 logs):**

- **Device-health telemetry** — 58 (BAMA) and 45 (TESTLINE) `connectionState`
  records: battery %, charging, firmware, serial, mode (`NORMAL`), stored
  messages, transmit power differential, hardware `9` / bootloader `20`,
  `errorCode: SystemErrorCodes(errorValue=0)` throughout.
  - PA temperature: 105.8–125.6 °F (BAMA), 104.0–136.4 °F (TESTLINE).
  - System temperature: 102.2–107.6 °F (BAMA), 96.8–105.8 °F (TESTLINE).
  - Logged in °C; the figures above are converted.
- **RSSI on received messages** — populated on every received message:
  −20 / −19 dBm on BAMA; −31 to −19 dBm on TESTLINE.
- **`fileTransfer`** — one 170-segment JPEG (`goTenna_ATAK_1790961198265.jpg`)
  sent by TESTLINE: `SUCCESS` after 186,705 ms (~3 min 7 s); BAMA received it
  `FULLY_RECEIVED` at 1 hop, −19 dBm.
- **Delivery statuses** — `SENT`, `FULLY_RECEIVED`, `DELIVERED` (2 private chats
  on BAMA) and **`SUCCESS`** (3 on TESTLINE: two map objects and the file
  transfer). `SUCCESS` is already in the UI's status colour map.
- **Message types** — `pli`, `textChat`, `mapObject` (`PIN`, `SHAPE`, `CIRCLE`,
  `ROUTE`), `fileTransfer`.
- **`frequencyUpdated`** — one per log (~17:03): power 5.0, bandwidth 11.8,
  16 channels (3 control: 461037.5, 464500.0, 469500.0).
- **`deviceDisconnected` → `deviceConnected`** — one pair per log at ~17:01:55,
  each disconnect with a location.
- **SDK Logging 2.0 `deviceState` records** (`WARNING`, `PROCESSING`), all
  `INCOMING` firmware nacks: BAMA 47 (204 ×25, 205 ×20, 228 ×2, last at
  17:16:17); TESTLINE 10 (204 ×4, 205 ×4, 228 ×2, last at 17:12:22). These
  carry `platformType: ANDROID`, `radioType: PRO_X_2`, the radio serial and
  `personalGid`.
- **New message fields** — `receiverCallsign`, `receiverUUID`, `senderUUID`,
  `version` (absent from the older ATAK test fixtures; **not** `ebb7b8c5`-specific —
  see the 2026-10-05 note below). Received messages name the local device as receiver; sent
  broadcasts carry `receiverCallsign: ""` (and `receiverUUID: ""`) and
  `receiverGid: 0` (placeholder, "no single receiver"); sent PRIVATE chats carry
  the receiver identity and a non-zero `receiverGid`. Only sent **PLI**
  broadcasts have a blank `senderUUID` / `originatorCallsign` — sent chat,
  mapObject and fileTransfer carry them (checked against both real logs).
- **Event type `cotDispatchedToAtak`** (absent from the older ATAK test
  fixtures; also present in `e6227295`, see the 2026-10-05 note below) — the largest record type: 206 of
  462 (BAMA) and 200 of 408 (TESTLINE). Fields: `cotType`, `destination`
  (`EXTERNAL`, `INTERNAL`, `BROADCAST`), `cotXml`. Most CoT types appear as
  `EXTERNAL`/`INTERNAL` pairs (e.g. `a-f-G-U-C` 79/79 on BAMA); `b-t-f` does not
  pair evenly (18/13 on BAMA, 16/13 on TESTLINE), and BAMA also has `b-t-f-d`
  `INTERNAL` ×2 with no `EXTERNAL`. An observation, not a rule.
- **No duplicate received entries** in either log.

**Update 2026-10-05 — not `ebb7b8c5`-specific:** three real logs from the older
plugin build `e6227295` (2026-08-24, `diagnostic_EUD-4_…_2026-08-24 18_08_17.821.log`
and two siblings) already populate `originatorCallsign`, `receiverCallsign`,
`senderUUID` and `receiverUUID` on most messages (71–82%), carry `version` `1` on
every message, and contain `cotDispatchedToAtak` events (1994 / 2442 / 778). Their
filenames also use the space + dotted-ms form. So the four message fields and the
event are present in `e6227295` as well as `ebb7b8c5`, and absent only from the
older ATAK test fixtures; population varies by build, and "empty" must never be
pinned to a build boundary.

## What's missing or inconsistent — flagged honestly

- **No device-health telemetry** — zero `connectionState` records in either
  log. That means **no battery %, thermal, firmware version, or radio-health
  snapshot** for this log type as it currently stands. Thermal/Battery tabs
  render empty. Unknown whether this is "not implemented yet in this FW/plugin
  build" or "just didn't fire in these two sessions" — needs more samples to
  tell apart.
  **Update 2026-10-04:** present in build `ebb7b8c5` (see above).
- **RSSI always `0`** — every single message in both logs, sent and received,
  reports `rssi: 0`. The field exists and the parser reads it correctly; it
  simply isn't being populated by this FW/radio combo yet. No signal-strength
  insight is currently possible from this log type.
  **Update 2026-10-04:** populated on received messages in build `ebb7b8c5`.
  Sent messages still report `0`.
- **PLI interval churn** — BARK's session shows four distinct interval values
  (`5`, `15`, `60`, and blank `""`) within one continuous session. Could be
  legitimate setting changes mid-session, could be a reporting quirk on the
  new FW. Worth watching across more logs before treating it as either normal
  or a bug.
  **Update 2026-10-04:** blank `""` still appears — 14 of 120 PLIs (BAMA) and
  17 of 124 (TESTLINE); every other PLI reports `60`.
- **No SDK Logging 2.0 (`sdkError`) records** — expected, since these are
  "regular" logs rather than "enhanced" debug logs; not a gap.
  **Update 2026-10-04:** build `ebb7b8c5` regular logs do contain them
  (firmware nack warnings, see above).

**Observed in build `ebb7b8c5` (2026-10-02 logs):**

- **Radio serial shows as `Unknown`** — the first health record of each log
  (`connectionState: CONNECTING`) carries the placeholder `serialNumber:
  "Unknown"`. `atak.py` keeps the first serial it sees, so the device summary
  reports `Unknown`. The real serial is in every later health record (57 / 44),
  in `deviceConnected`, and in the sdkError records. Parser gap.
- **`cotDispatchedToAtak` detail not captured** — `atak.py` records only the
  event type; `cotType`, `destination` and `cotXml` are dropped. The Device
  Events Timeline lists every event at 30 px per row, so these ~200 records per
  log would show as blank-detail rows (from reading the code; not yet confirmed
  in the browser). Parser/UI gap.
- **New message fields not captured** — `receiverCallsign`, `receiverUUID`,
  `senderUUID` and `version` are not in `AtakMessage`. Parser gap.
- **Sent messages report `rssi: 0` and `hopCount: 0`** — placeholders, not
  measurements. The RF map already excludes sent messages.
- **Hop count is `1` on every received message** — all devices were within
  direct range, so this test shows no multi-hop behaviour.
- **Narrow RSSI range** (−31 to −19 dBm) — consistent with devices close
  together.
- **Irregular health cadence** — gaps from 0 to 60 s; 12 (BAMA) and 17
  (TESTLINE) gaps are the full 60 s, the rest shorter.
- **Meanings unconfirmed** — firmware nack codes 204 / 205 / 228;
  `cotDispatchedToAtak` destinations `EXTERNAL` vs `INTERNAL`; `bandwidth: 11.8`
  unit; frequencies logged like `461037.5` (read as kHz).

## Cross-check with the Pro+ logs from the same test (2026-10-02)

- **TESTLINE's file transfer and the short GID** — TESTLINE's own log shows the
  transfer sent from its full GID `90168163972632`, and BAMA received it under
  that same GID. Only the Pro+ receivers logged it as `27628` (logID
  `27628:2605`).
- **GIDs match across apps** — BAMA and TESTLINE see each Pro+ device under the
  GID that device reports in its own `radioStatus`: AndPro S20
  `90177632067335`, AndPro S24 `90163251493958`, iOSPro 13 `90167828132566`,
  iOSPro 16 `90033540780181`.
- **Callsigns match** — the Pro+ devices appear here as "AndPro S20",
  "AndPro S24", "iOSPro 13" and "iOSPro 16".
- **Duplicates** — neither ATAK log has duplicate received entries; the iOS
  Pro+ logs do.
- **Frequency changes** — both ATAK logs record only the one `frequencyUpdated`
  at ~17:03. All four Pro+ logs also record changes at ~17:08, ~17:12 and
  ~17:18.

## CoT XML in `cotDispatchedToAtak` — epoch-zero `<creator>` time (observed 2026-10-05)

Observation only; no parser or UI decision is implied.

In both 2026-10-02 `ebb7b8c5` logs, the embedded CoT XML in
`cotDispatchedToAtak` records contains
`<creator uid='resolve THIS' callsign='…' time='1970-01-01T00:00:00…Z' type='a-f-G-U-C'/>`.
Counted read-only against the two logs: **4 occurrences per log**. Each log also
holds further `<creator>` elements with ordinary 2026-10-02 times, so the 1970
value is specific to these four.

- **Which objects:** both map objects were created on an iOS device (the callsign
  inside the element is that iOS device's callsign). One is a marker carrying
  `<link production_time='…' parent_callsign='…'/>`; the other is a drawn circle
  shape with `<contact callsign='Circle_…'/>`, stroke/fill colours and `<archive/>`.
- **Occurrence arithmetic:** each object is dispatched `EXTERNAL` and `INTERNAL`,
  so 2 objects x 2 destinations = 4.
- **Reading the value:** `1970-01-01T00:00:00…Z` is an epoch-zero placeholder on
  the `<creator>` element, not the object's real time.
- **Quoting:** CoT XML attributes in these records are **single-quoted**.
- **Why it matters:** this is what pushed the time-window slider range back to
  1970 until `XML_TS_ATTR_RE` in `FileUpload.jsx` accepted single quotes (fixed
  2026-10-05; see `ui-requirements.md`).

## Bugs found and fixed along the way

- **Originator PLI card silently dropped 5s-cadence traffic (fixed 2026-07-29).**
  BARK's log showed a genuine ~5s PLI cadence for 534 of 702 sent messages (the
  dominant chunk of the session, ~44 minutes) — but the Originator PLI card
  only showed `60s` and `15s` buckets, and the UI's own banner claimed "no 5s
  data in loaded files." Root cause: the frontend inferred intervals purely
  from timing gaps between sent messages, bucketed into a fixed list
  (`15/30/60/120/180/300/600s`) with ±25% tolerance — a 5s gap is nowhere near
  15s±25%, so it was discarded as noise. Fix: the frontend now prefers the
  self-reported `message.interval` field (populated per-message starting with
  ATAK plugin v3.0) over gap inference, falling back to gap inference only for
  older-format logs that never populate that field. This also means the
  Originator PLI card is now reading the same ground-truth field the radio/app
  itself reports, rather than reconstructing it from timing — more reliable
  going forward, not just a 5s-specific patch.
- **"PLI Settings per Device" mislabeled its first entry as "session-start
  setting" (fixed 2026-07-29).** `pliSettingUpdated` only fires on a *change*
  — it doesn't log the starting configuration when the app launches. BARK's
  card showed "session-start setting: 15s" when the first `pliSettingUpdated`
  event actually fired 92 minutes into the session; the true starting
  cadence (self-reported at 60s, later 5s) was invisible to that card the
  whole time. Relabeled to "first observed setting-change event," with an
  explicit caveat surfaced when that first event falls more than 2 minutes
  into the session.

## Key takeaway for cross-referencing Originator PLI vs PLI Settings

These two cards can legitimately disagree, and BARK is the textbook example:
Settings said 15s (first logged change at 19:38:51), but Originator PLI (once
fixed) shows the device actually ran 60s → 5s → 15s across the session — the
first two phases had no corresponding settings-change event at all, so the
Settings card had zero visibility into them. Treat a mismatch as a prompt to
check *when* the first settings event fired relative to session start, not as
a parser bug by default.

## Not yet observed (unknown, not confirmed absent)

These simply haven't shown up in the two logs reviewed so far — no
conclusion either way:
- `fileTransfer` messages
- `firmwareUpdate`, `powerLevelUpdated`, `frequencyUpdated` events
- Any delivery status other than `SENT` / `FULLY_RECEIVED` / `DELIVERED`
  (e.g. `FAILED`)

**Update 2026-10-04:** `fileTransfer`, `frequencyUpdated` and `SUCCESS` are now
observed (see above). Still not observed: `firmwareUpdate`,
`powerLevelUpdated`, `FAILED`, retries (`retryCount` > 0), open segments > 0.
`ledStateUpdated` and `pliSettingUpdated` did not appear in the October logs.

## How to use this doc

- Add a row to the Source Logs table each time a new v3.0 log is reviewed.
- Move items between "missing" and "present" sections as the picture
  clarifies — don't just delete the old note, it's useful to see what changed
  and when.
- Once the plugin/FW stabilizes and this stops being "early integration,"
  fold anything durable into `CLAUDE.md`'s Known Data Limitations table and
  retire this doc.
