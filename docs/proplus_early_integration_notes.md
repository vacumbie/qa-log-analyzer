# Pro+ JSON Log — Early Integration Notes
_Created: 2026-10-04_

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
- **iOS location fixes can be stale or repeated.** 9 (iOS 13) and 6 (iOS 16)
  location records were logged more than 60 s after the fix was taken; the first
  iOS 13 fix was 3 minutes old. The same fix was also logged twice 8 and 6
  times. Android: none of either.

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

## Message details

**Message types (`message.type`):** `pli`, `textChat`, `mapObject` (with
`objectType` `pin`, `shape`, `circle`, `route`), `fileTransfer` (with `fileName`).

**Protocols:** `broadcast` (nearly everything) and `private` (a few chats;
`receiverGid` present on some).

**Delivery statuses seen:** only `sent` (own) and `fullyReceived` (received).

**Timestamps:** `messageTimestamp` has 6 fractional digits on PLIs this device
originated, and 3 digits otherwise.

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

## What's missing or inconsistent — flagged honestly

Valerie confirmed (2026-10-04) that **hop count, RSSI, battery temperature and
other fields will be added in future logs.** The items marked _(future)_ are
expected, not defects.

- **Hop count and RSSI** _(future)_: present on only **one record per log** —
  the single `fileTransfer` (1 hop; RSSI −20, −20, −19, −34 dBm). Every PLI,
  chat and map object lacks them. They are **absent, not zero**.
- **Temperature** _(future)_: there are no thermal fields anywhere.
- **iOS 16 has no `applicationInfo` record**: no app version, launch time or
  `apiVersion` for that file. Possibly rotated out of the log buffer —
  _unconfirmed_.
- **Duplicate received entries on iOS** (see above). Matching on `logID` +
  `messageTimestamp` + `senderUUID` identifies the copies exactly; `logID` alone
  does not (next item).
- **`logID` is not unique:** two different chats (from BAMA at 17:21:54 and
  TESTLINE at 17:24:21) share `logID: "mattermost-user-"`.
- **One device, two GIDs:** TESTLINE (UUID `ANDROID-d48a7f48c457842e`) sends
  PLIs as `90168163972632`, but its file transfer came from **`27628`** — a
  short GID like those in ATAK v3 logs.
- **S20 radio `mode` anomaly:** `normal` until 17:05:58, then `unknown` from
  17:06:58 for the remaining 20 samples. The other three devices stayed `normal`
  throughout. Unexplained.
- **Gateway `senderGid` inconsistency:** the gateway logs a forwarded message
  under its own GID, while receivers log the same message with GID 0.

## Not yet observed (unknown, not confirmed absent)

- Severities other than `INFO` (e.g. `WARNING`, `ERROR`)
- `connectionState` other than `connected`, or `connectionType` other than `BLE`
- Disconnect or reconnect events
- Delivery statuses other than `sent` / `fullyReceived` (e.g. failed, delivered)
- Retries (`retryCount` > 0) or multi-segment messages other than the file transfer
- Any record with `"version"` other than 1

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
