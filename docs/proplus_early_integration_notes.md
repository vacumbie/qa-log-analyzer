# Pro+ JSON Log — Early Integration Notes
_Created: 2026-10-04 · Updated: 2026-10-06 (build 310 logs from the 2026-10-05 test)_

## Purpose

This doc records what the new **Pro+** JSON diagnostic log (Pro+ app 3.2.0)
actually contains, based on the first four field captures. It holds
**observations only**. Work items live in the canonical backlog
(`docs/ui-requirements.md` → To Do / Backlog), and parser rules will live in
`docs/parsing-requirements.md` once written. As with the ATAK v3 notes, the goal
is to keep "this field isn't in the log yet" separate from "the parser is
missing something."

**Name:** displayed as **Pro+**, internal format key `proplus`. This is a
separate format from the existing **Diagnostic** format (the older Pro+
block-text export), which is unchanged.

## Source Logs

All four come from one group test on **2026-10-02**, roughly 16:54 → 17:29 UTC.
All four: app `3.2.0` (build 307), radio firmware `3.2.11`, chip architecture
`legacyNXP`, BLE connection.

| File | Phone (decoded) | Platform | Radio serial | GID | Session window (UTC) | Records | Messages logged |
|---|---|---|---|---|---|---|---|
| `AndPro_S20_diagnostic_log_2026-10-02_13-26-22.json` | SM-G781U (Galaxy S20 FE 5G) | Android 13 (API 33) | PNE234100344 | 90177632067335 | 17:00:18 → 17:26:18 | 235 | 146 (49 sent / 97 recv) |
| `AndPro_S24_diagnostic_log_2026-10-02_13-26-37.json` | SM-S921U1 (Galaxy S24) | Android 16 (API 36) | MNE251500092 | 90163251493958 | 17:00:15 → 17:26:12 | 205 | 148 (28 sent / 120 recv) |
| `iOSPro_13_diagnostic_log_2026-10-02_13-29-09.json` | iPhone14,3 (iPhone 13 Pro Max) | iOS 18 | PNE234100450 | 90167828132566 | 16:54:12 → 17:28:58 | 399 | 323 (36 sent / 287 recv — **144 unique**) |
| `iOSPro_16_diagnostic_log_2026-10-02_13-29-25.json` | iPhone17,1 (iPhone 16 Pro) | iOS (version unknown) | MNE251000006 | 90033540780181 | 16:57:56 → 17:29:18 | 378 | 258 (73 sent / 185 recv — **93 unique**) |

Phone model names are decoded from the model identifiers; they are not in the logs.

**2026-10-05 test (build 310):** six logs, app `3.2.0` (build **310**), radio
firmware `3.2.11`, BLE. About 6 hours each, 13:48 → 20:09 UTC. The mesh had nine
members: these six plus three ATAK devices, Val_ATAK, Mike_ATAK and Jen_ATAK
(plugin build `6830bbcf`). Devices are named by the callsign they used on the
mesh. The filename column shows each file's own label; full filenames, radio
serials and GIDs are left out because the Android filenames start with phone
serial numbers.

| Callsign | Filename label | Phone (decoded) | Platform | App launches | Records | Messages logged |
|---|---|---|---|---|---|---|
| Jon_iOS | `Jon` | iPhone12,1 (iPhone 11) | iOS 17 | 2 | 2,671 | 2,296 (174 sent / 2,122 recv — **1,061 unique**) |
| Keri_iOS | `Keri_iOS` | iPhone18,1 (likely iPhone 17 Pro) | iOS 26 | 4 | 2,519 | 2,305 (23 sent / 2,282 recv — **1,141 unique**) |
| Wen_IOS | `Wendell` | iPhone12,1 (iPhone 11) | iOS 26 | 3 | 2,557 | 2,164 (180 sent / 1,984 recv — **992 unique**) |
| Ki_And | `KI_And` | SM-S931U1 (Galaxy S25) | Android 16 | 3 | 1,565 | 1,171 (180 sent / 991 recv) |
| Ivan_And | `ivan_and` | SM-S931U1 (Galaxy S25) | Android 16 | 2 | 1,481 | 1,173 (117 sent / 1,056 recv) |
| Victor_And | `vic-and` | SM-S931U1 (Galaxy S25) | Android 16 | 4 | 1,621 | 1,238 (181 sent / 1,057 recv) |

All six parse cleanly. Each device's GID is the same in every log.

## File structure

- **NDJSON:** one JSON object per line. All 1,217 lines across the four files
  parse cleanly. Records are in time order.
- **Same record envelope on every line:** `{"id", "timestamp", "tags", "message"}`.
  `message` holds exactly one key that names the record type.
- This is the same envelope ATAK uses for its SDK Logging 2.0 records — which
  is why the current tool misdetects these files (see **Detection** below).
- Every message-type record carries `"version": 1`.

### Record types

| Tags | `message` key | S20 | S24 | iOS 13 | iOS 16 | What it holds |
|---|---|---|---|---|---|---|
| `INFO, APP_INFO` | `applicationInfo` | 1 | 1 | 1 | **0** | App version/build, launch time, phone model, `apiVersion` |
| `INFO, RADIO` | `radioStatus` | 24 | 24 | 33 | 33 | Radio serial, GID, firmware, battery %, charging, mode, connection state/type — every ~60 s |
| `INFO, LOCATION` | `location` | 24 | 24 | 33 | 32 | Phone GPS fix (lat/long/alt) — roughly every 60 s |
| `INFO, USER_EVENT` | `userEvent` | 8 | 8 | 9 | 8 | `deviceConnected`, `frequencyUpdated`, `pliSettingUpdated` |
| `INFO, MESSAGE` | `transmittedMessage` | 146 | 148 | 323 | 258 | Every mesh message sent or received |
| `INFO, TAK` | `TAK_Srvr_Conn` | 1 | — | — | 1 | TAK server connection (address + time) |
| `INFO, MESSAGE, TAK` | `takMessage` | 31 | — | — | 46 | Messages passing between the phone and the TAK server |

Only the `INFO` severity appears in these four files.

**Update 2026-10-06 (build 310):** the same seven record types. One `WARNING` record appears
(see Group test timeline). `applicationInfo` now appears once per app launch,
2–4 times per log.

## Telling iOS from Android

**The format is identical on both platforms:** same record types, field names,
field order and timestamp precision. This suggests one shared logging library.
Unlike ATAK's `deviceState` records, there is **no `platformType` field**.

**The reliable signal is the phone model string:**

- `applicationInfo.deviceInfo.deviceModel` (startup record), and
- `userEvent` → `deviceConnected` → `modelNumber`.

Values starting with `iPhone` (or presumably `iPad`) mean iOS; Samsung-style
models such as `SM-…` mean Android. **Both sources are needed:** iOSPro_16 has
no `applicationInfo` record (its log begins at the first `radioStatus`), so its
platform can only be read from `deviceConnected`.
**Update 2026-10-06 (build 310):** all six logs have `applicationInfo`. The
`deviceConnected` fallback is still worth keeping for logs like iOSPro_16.

**Field-meaning traps:**

- `apiVersion` means different things per platform: an Android **API level**
  (33 = Android 13, 36 = Android 16) versus an iOS **major version** (18 = iOS 18).
  The number alone doesn't say which OS it refers to.
- `deviceConnected.modelNumber` is the **phone's** model, even though it sits
  next to the **radio's** `serialNumber`.

**Behavioral differences** (real, but not suitable for detection):

- **iOS logs every received message twice.** The two copies are 1–7 ms apart.
  iOS 13: 287 received entries = 144 unique (143 duplicates). iOS 16:
  185 = 93 unique (92 duplicates). Android: **zero** duplicates. Counted as-is,
  the iPhones appear to receive about twice the traffic they actually did.
  **Update 2026-10-06 (build 310):** still present on all three iPhones (see Source
  Logs), still zero on Android. The two copies share the same `messageUUID`.
- **iOS location fixes can be stale or repeated.** 9 (iOS 13) and 6 (iOS 16)
  location records were logged more than 60 s after the fix was taken; the first
  iOS 13 fix was 3 minutes old. The same fix was also logged twice 8 and 6
  times. Android: none of either.
  **Update 2026-10-06 (build 310):** **not iOS-only.** Ki_And logged 16 stale
  fixes, up to about 13 minutes old, and 16 repeats; Wen_IOS 17 stale (up to
  4 min 21 s); Keri_iOS 1.

## Callsigns

- **No identity record holds the device's own callsign.** It does not appear in
  `applicationInfo` or `radioStatus`.
- **Every `transmittedMessage` and `takMessage` carries `senderCallsign`,**
  including the device's own sent PLIs ("AndPro S20", "AndPro S24",
  "iOSPro 13", "iOSPro 16"). The own callsign can therefore be derived from
  own sent messages.
- **Callsigns changed mid-session:** the iPhone 16 began as **MARS** and the
  iPhone 13 as **MURKY**; both were renamed around 16:59 UTC.
- **The GID stayed constant through each rename,** so callsign alone can't
  identify a device across a session.
- **Update 2026-10-06 (build 310):** still no callsign in any identity record. Each
  device's own callsign is still derivable from its sent messages, for all six.
- Other participants seen: **BAMA**, **TESTLINE**, **FIRM** — ATAK devices with
  `ANDROID-…` UUIDs.

## Detection — current tool gets this wrong silently ⚠️

Running today's `_detect_format()` on main against all four files returns
**`atak`** for every one. The ATAK parser then:

- treats all records as SDK Logging 2.0 events and only counts them,
- extracts **zero** messages and an **empty** device identity, and
- emits `DATA LIMITATION — no device-health (connectionState) records in this
  log: battery %, … firmware version … unavailable`. **This is false:**
  `radioStatus` carries battery and firmware every 60 s.

**Root cause:** `_is_atak_content()` matches `"connectionState"` or
`"deliveryStatus"` anywhere in the first 2,000 characters. Pro+ `radioStatus`
and `transmittedMessage` contain both.

**Update 2026-10-06 (build 310):** today's detection still gets all six wrong, in two
different ways: five come back as `atak`, and one (Wen_IOS) as **`diagnostic`**.
In that file, the keys the ATAK check looks for don't appear in the first 2,000
characters, so it falls through to the fallback. All six start with an
`applicationInfo` record.

## Message details

**Message types (`message.type`):** `pli`, `textChat`, `mapObject` (with
`objectType` `pin`, `shape`, `circle`, `route`), `fileTransfer` (with `fileName`).

**Protocols:** `broadcast` (nearly everything) and `private` (a few chats;
`receiverGid` present on some).

**Delivery statuses seen:** only `sent` (own) and `fullyReceived` (received).
**Update 2026-10-06 (build 310):** still only these two (855 `sent`, 9,492
`fullyReceived`). No partial receptions are logged (see Cross-check with ATAK).

**Timestamps:** `messageTimestamp` has 6 fractional digits on PLIs this device
originated, and 3 digits otherwise.
**Update 2026-10-06 (build 310):** always 3 digits, own PLIs included.

### `logID` shapes

| Shape | Seen on |
|---|---|
| `<epoch-ms>:<gid>` | Own PLIs |
| `<senderUUID>\|<epoch-ms>` | PLIs from other Pro+ devices |
| `ANDROID-<uid>\|<epoch-ms>` | PLIs from ATAK devices (directly or via TAK) |
| bare UUID | `textChat` and `mapObject` |
| `GeoChat.ANDROID-…` | TAK chats forwarded into the mesh by a gateway phone |
| `<short-gid>:<seq>` | The `fileTransfer` (e.g. `27628:2605`) |
| `mattermost-user-` | Two different chats — looks truncated (see below) |

**Update 2026-10-06 (build 310):** **`logID` changed meaning.**

- It is now a plain signed number on every message (e.g. `894525721`,
  `-722245245`).
- The composite shapes above moved into a new field, **`messageUUID`**:
  - **PLIs:** `<senderUUID>|<epoch-ms>`, where the epoch-ms is the **receiver's**
    receive time. The same PLI has a different `messageUUID` in each receiver's
    log.
  - **Map objects:** the object's UUID, so re-sent edits of one object share it.
- The numeric `logID` is **not unique:** one of Ivan_And's PLI values recurred
  35 minutes later, on a different message, in every log that received both.
- The numeric `logID` equals the ATAK sender's `logId` for ATAK messages (see
  Cross-check with ATAK).
- `senderUUID` + `messageTimestamp` are identical in every receiver's log.

## TAK gateway behavior

- **Two phones acted as TAK gateways:** S20 (connected 17:21:18) and iPhone 16
  (connected 17:20:47), both to `qa-takserver.txtenna.com`.
- **`takMessage.direction` values:** `fronthaul`, `backhaul`, `sent`.
  _Inferred meaning (not confirmed):_ `fronthaul` = server → phone → mesh;
  `backhaul` = mesh → phone → server; `sent` = the phone's own message to the
  server.
- **The gateway logs forwarded TAK messages as its own sends:**
  `isSender: true`, its **own** `senderGid`, but the **original author's**
  `senderCallsign`.
- **Receivers log those same messages with `senderGid: 0`.** The counts match
  exactly — the S24's GID-0 messages equal the S20's forwarded sends (BAMA 6,
  iOSPro 16 6, TESTLINE 4, iOSPro 13 2, FIRM 2).
- So `senderGid: 0` marks a message that came from TAK through a gateway. It
  carries no mesh radio identity.
- **Update 2026-10-06 (build 310):** two iPhones connected to a TAK server
  (a different internal host from 2026-10-02) for only 1–2 minutes around 14:05.
  `TAK_Srvr_Conn` gains a **`disconnectedTimestamp`** field. No forwarded
  messages and no `senderGid: 0` appear, so the gateway behaviour above wasn't
  re-observed.

## Group test timeline (from `userEvent`)

All four devices recorded the same configuration changes within seconds of
each other:

| ~Time (UTC) | Event |
|---|---|
| 16:58 / 17:04 | `deviceConnected`; 16-channel frequency set (3 control channels); power 5; PLI settings: every 60 s, auto-send on, distance-based off |
| ~17:08 | Frequency set changed to 3 channels (451.8 / 456.8 / 464.5 MHz), power 5 |
| ~17:12 | Channels changed, **power 1** |
| ~17:18 | Channels changed, power back to 5 |

Frequencies are logged as numbers like `461037.5`, which read as kHz.
`bandwidth: 11.8` has no unit in the log. Both units are **unconfirmed**.

**Update 2026-10-06 (build 310):** `frequencyUpdated` events are frequent but mostly
repeats.

- 13–30 per device across the session, roughly every 15 minutes.
- Most are the same configuration again: Ki_And logged 30 events with only
  1 distinct configuration.
- Only Jon_iOS (4 configurations: power 1 or 5, 3 or 16 channels) and Ivan_And
  (2) show real changes.
- **First `WARNING` record:** a failed frequency update on Ki_And at 18:01:16,
  `userEvent` with a new **`didSucceed: false`** field, during a run of BLE
  drops.

## What's missing or inconsistent — flagged honestly

Valerie confirmed (2026-10-04) that **hop count, RSSI, battery temperature and
other fields will be added in future logs.** The items marked _(future)_ are
expected, not defects.

- **Hop count and RSSI** _(future)_: present on only **one record per log** —
  the single `fileTransfer` (1 hop; RSSI −20, −20, −19, −34 dBm). Every PLI,
  chat and map object lacks them. They are **absent, not zero**.
  **Update 2026-10-06 (build 310):** **now populated on every received PLI and
  file transfer.** Still absent on map objects, chats and everything sent. Hops
  1–6 (mostly 1–3); RSSI −119 to −16 dBm.
- **Temperature** _(future)_: there are no thermal fields anywhere.
  **Update 2026-10-06 (build 310):** still none; `radioStatus` is unchanged.
- **iOS 16 has no `applicationInfo` record**: no app version, launch time or
  `apiVersion` for that file. Possibly rotated out of the log buffer —
  _unconfirmed_.
  **Update 2026-10-06 (build 310):** every log has it, one per app launch. More
  likely that 2026-10-02 session started before logging began — _unconfirmed_.
- **Duplicate received entries on iOS** (see above). Matching on `logID` +
  `messageTimestamp` + `senderUUID` identifies the copies exactly; `logID` alone
  does not (next item).
- **`logID` is not unique:** two different chats (from BAMA at 17:21:54 and
  TESTLINE at 17:24:21) share `logID: "mattermost-user-"`.
  **Update 2026-10-06 (build 310):** no `mattermost-user-` IDs, but the new numeric
  `logID` repeats too (see `logID` shapes).
- **One device, two GIDs:** TESTLINE (UUID `ANDROID-d48a7f48c457842e`) sends
  PLIs as `90168163972632`, but its file transfer came from **`27628`** — a
  short GID like those in ATAK v3 logs.
  **Update 2026-10-06 (build 310):** seen again. Jen_ATAK's private
  204-segment file transfer was logged by the receiving Pro+ device (Victor_And)
  under the short GID `49463`, while Jen_ATAK's own log uses her full GID.
  Both cases are file transfers, logged on the Pro+ receiving side.
- **S20 radio `mode` anomaly:** `normal` until 17:05:58, then `unknown` from
  17:06:58 for the remaining 20 samples. The other three devices stayed `normal`
  throughout. Unexplained.
  **Update 2026-10-06 (build 310):** `unknown` is the **majority** state on all six
  devices (e.g. 172 of 179 samples on Jon_iOS), so it isn't an S20 quirk.
- **Gateway `senderGid` inconsistency:** the gateway logs a forwarded message
  under its own GID, while receivers log the same message with GID 0.

**Observed in build 310 (2026-10-05 logs):**

- **Fields now omitted unless they apply:** `retryCount`, `segmentCount`,
  `numberOfOpenSegments` and `receiverGid` appear only on file transfers and
  private messages. On 2026-10-02 they were on every message. Absent means
  "not applicable," not 0.
- **Radio switch mid-session:** Keri_iOS moved to a second radio at 17:14:23 and
  back at 17:19:50, around three app relaunches. Only the final reconnect
  produced a `deviceConnected` event, and the second radio's GID appears in no
  other log.
- **Sparse sending:** Keri_iOS sent only 17 PLIs and logged 17 locations in about
  6 hours. The other five sent 112–180 PLIs.
- **Reconnects aren't logged:** Ki_And has 11 `deviceDisconnected` events but
  only 1 `deviceConnected`. All 174 of its `radioStatus` snapshots say
  `connected`, so the drops show up only as events.
- **`deviceDisconnected` events carry a GPS location** (`lat`, `long`, `alt`).
- **Sent file transfers may not be logged by the sender:** the ATAK logs show
  partial receptions of file transfers from two Pro+ devices (Victor_And and
  Wen_IOS), but neither device's own log records sending a file.

## Not yet observed (unknown, not confirmed absent)

- Severities other than `INFO` (e.g. `WARNING`, `ERROR`)
- `connectionState` other than `connected`, or `connectionType` other than `BLE`
- Disconnect or reconnect events
- Delivery statuses other than `sent` / `fullyReceived` (e.g. failed, delivered)
- Retries (`retryCount` > 0) or multi-segment messages other than the file transfer
- Any record with `"version"` other than 1

**Update 2026-10-06 (build 310):** now observed: one `WARNING` record and
`deviceDisconnected` events. Still not observed: `ERROR` severity,
`connectionState` other than `connected`, `connectionType` other than `BLE`,
delivery statuses other than `sent` / `fullyReceived`, retries above 0, and any
`version` other than 1.

## Cross-check with the ATAK logs from the same test (2026-10-05)

- **`logID` matches across the two apps:** the Pro+ `logID` for an ATAK message
  equals the ATAK sender's `logId`, for every one of 3,941 matched receptions.
- **A delivered message reported as failed:** Val_ATAK's private chat to Wen_IOS at
  19:06:21 is `FAILED` on Val's side after about 130 s, but **fully received**
  in Wen_IOS's log. The delivery confirmation didn't make it back. Three other
  ATAK → Pro+ private messages marked `FAILED` leave no trace at their Pro+
  receivers: Mike_ATAK → Victor_And (chat, 18:21:30) and Val_ATAK → Ki_And (map
  objects, 19:57:36 and 19:58:21).
- **PLIs flow in both directions:** per-link PLI delivery after 17:20 UTC ranged
  from 56% to 100% across all nine devices.
- **Partial receptions:** the ATAK logs record six partial file-transfer
  receptions; the Pro+ logs record none.
- **Connection events are unpaired on both sides,** in opposite directions:
  Pro+ logs disconnects without reconnects, ATAK logs reconnects without
  disconnects.
- **Frequency events:** the ATAK logs contain no `frequencyUpdated` events at
  all; the Pro+ logs contain 13–30 each.

## Open questions for the app developers

Questions about what the log data means, not project tasks.

- Does this JSON log **replace** the old Pro+ block-text export, or will
  testers use both? _(Assuming both for now.)_
- Is iOS double-logging received messages a bug or intended?
- What do `fronthaul` / `backhaul` mean exactly?
- Why does the S20 report radio `mode: unknown`?
- Why is `applicationInfo` missing from the iOS 16 log?
- What causes the truncated `mattermost-user-` logID?
- Why did TESTLINE's file transfer use a short GID (`27628`)?
- Will future logs add the device's own callsign to an identity record?

**Added 2026-10-06 (build 310):**

- What is the new numeric `logID` derived from, and why can it repeat on
  different messages?
- Does the Pro+ app send delivery confirmations for private messages from ATAK
  devices? (One delivered chat was reported `FAILED` by its ATAK sender.)
- Why are reconnects not logged as `deviceConnected`?
- Why does `frequencyUpdated` repeat the same configuration every ~15 minutes?
- Are sent file transfers meant to appear in the sender's own log?
- Where do the phone-serial prefixes on the Android filenames come from? The
  ATAK filenames have them too, which suggests the log-collection step rather
  than either app.
