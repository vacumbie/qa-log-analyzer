# Parsing Requirements

> **Source of truth for all log parsing requirements.**
> Update this file as requirements change or grow.
> Keep changes in sync with parser code and tests.

---

## Table of Contents
- [Supported Log Sources](#supported-log-sources)
- [General Rules](#general-rules)
- [Android ATAK Plug-in](#android-atak-plug-in)
- [Pro+ Application](#pro-application)
- [Relay Health Manager](#relay-health-manager)
- [Relay Firmware (UART/USB Debug) Log](#relay-firmware-uartusb-debug-log)
- [Shared Output Requirements](#shared-output-requirements)
- [Known Limitations](#known-limitations)

---

## Supported Log Sources

The log parsing tool accepts logs from the following goTenna applications:

| # | Application | Platform | Log Types | Parser File |
|---|-------------|----------|-----------|-------------|
| 1 | Android ATAK Plug-in | Android only | 2 (regular, enhanced — same format) | `parser/atak.py` ✅ |
| 2 | Pro+ Application (RSDK) | iOS, Android | 1 per platform (confirmed) | `parser/rsdk.py` ✅ |
| 3 | Relay Health Manager | Android *(iOS TBD)* | Android logcat (`com.gotenna.relaymanager`) | `parser/relay_manager.py` ✅ |
| 4 | goTenna Pro+ diagnostic export | iOS, Android | Block-format diagnostic export | `parser/diagnostic.py` ✅ *(detection fallback)* |
| 5 | Relay radio firmware | Relay radio | UART/USB serial debug console | `parser/fw_log.py` ✅ *(detection priority 1)* |

---

## General Rules

- Temperatures must always be reported in **Fahrenheit**
- Flag data limitations honestly — if a field cannot be parsed or is missing, surface it explicitly rather than silently skipping
- Parsers live in `parser/` and must have corresponding tests in `tests/`
- Each log source gets its own parser or clearly separated parsing path
- Platform (iOS / Android) must be detected or inferred from log content where possible

---

## Android ATAK Plug-in

### Overview
A goTenna plugin that integrates with the ATAK (Android Team Awareness Kit) application.

- **Platform:** Android only
- **Package:** `com.gotenna.atak`
- **Log format:** Newline-delimited JSON (identical structure to ATAK enhanced log)

### Log Types

Both log types share the **same JSON format and record structure**. The difference is in content depth, not format.

| Type | Description | Example File |
|------|-------------|--------------|
| Regular (user) | Standard operational log; less verbose | `diagnostic_VALERIE_90303856880026_2026-05-20_15_53_30_502.log` |
| Enhanced (debug) | Testing and debugging; more verbose | `diagnostic_ATAK_HOTEL_90215634664458_2026-03-04_16_42_04_775.log` |

### Differences: Regular vs Enhanced

| Feature | Regular | Enhanced |
|---------|---------|----------|
| Format | Newline-delimited JSON | Newline-delimited JSON |
| Record types | Same 5 types | Same 5 types |
| Callsign/UUID fields | Always empty strings | Always empty strings |
| `frequencyUpdated` event | ✅ Present (full channel list) | ❌ Not observed |
| `powerLevelUpdated` event | ❌ Not observed | ✅ Present |
| `pliSettingUpdated` event | ✅ Present | ✅ Present |
| `mapObject` CASEVAC type | ✅ Present | ❌ Not observed |
| Multi-session accumulation | ✅ Yes — log accumulates across app launches | Single session observed |
| App Info records | Multiple (one per launch) | One per session |
| `transmitPowerDifferential` | Mix of real values (5–16) and 255 sentinel | Mix of real values (1–3) and 255 sentinel |

### Multi-Session Accumulation (Regular Log)

The regular user log accumulates data across multiple app launches without being cleared. This means:
- Multiple App Info records will be present (one per launch)
- Timestamps span the full lifetime of the log — session boundaries must be detected from App Info `launchTimeInMillis` values
- The sample log spans **2026-04-20 to 2026-05-20 (30 days)** across **10 app launches**

### Filename Convention

Same as enhanced log:
```
diagnostic_ATAK_<CALLSIGN>_<GID>_<YYYY-MM-DD>_<HH_MM_SS_mmm>.log
```

### Fields to Parse

All fields from the enhanced log apply — see **Android ATAK Plug-in — Enhanced Log** section. Additional fields specific to the regular log:

#### `frequencyUpdated` Event (regular log — full channel list)

| Field | Type | Example | Notes |
|-------|------|---------|-------|
| `event.type` | string | `"frequencyUpdated"` | |
| `event.power` | float | `0.5` | Watts |
| `event.bandwidth` | float | `11.8` | kHz |
| `event.channels` | list | see below | Full channel list |
| `event.channels[].frequency` | float | `445.5` | MHz |
| `event.channels[].isControlChannel` | bool | `true` | |

#### `mapObject` Subtypes

All `mapObject` subtypes are **conditionally present** — a subtype only appears in a log if a user actually sent that object type over the network during the session. The parser must handle any subtype gracefully and never assume a specific subtype will be present.

| `objectType` | Description | Seen in |
|-------------|-------------|--------|
| `PIN` | Map pin | Both log types |
| `SHAPE` | Map shape | Enhanced log |
| `CIRCLE` | Map circle | Enhanced log |
| `ROUTE` | Map route | Enhanced log |
| `VEHICLE` | Map vehicle | Enhanced log |
| `CASEVAC` | Casualty Evacuation — ATAK-specific | Regular log |

> ⚠️ This list is not exhaustive. New `objectType` values may appear as ATAK features are used. The parser must not fail on unknown subtypes — capture `objectType` as-is and surface it.

**Message types observed in regular log:**

| `message.type` | `message.objectType` | Count |
|---------------|---------------------|-------|
| `pli` | — | 30,456 |
| `mapObject` | `PIN` | 45 |
| `mapObject` | `ROUTE` | 19 |
| `mapObject` | `CIRCLE` | 18 |
| `mapObject` | `CASEVAC` | 1 |
| `fileTransfer` | — | 23 |
| `textChat` | — | 20 |

### Parsing Rules

All rules from the enhanced log apply. Additional rules for the regular log:

1. **Multi-session detection** — multiple App Info records indicate multiple launches; use `launchTimeInMillis` to segment sessions
2. **`frequencyUpdated` event** — parse full channel list including frequency (MHz) and `isControlChannel` per channel
3. **`CASEVAC` map object** — treat as a valid `mapObject` subtype; no additional fields beyond `objectType`
4. **`transmitPowerDifferential=255`** — sentinel value; treat as null (observed in both log types during CONNECTING state and intermittently during CONNECTED)

### Known Limitations — ATAK Regular Log

- **Callsign and UUID fields are always empty** in both log types — same as enhanced log
- **`transmitPowerDifferential`** real values (5–16) observed in regular log vs (1–3) in enhanced; meaning remains undocumented
- **Multi-session accumulation** means the log may contain data from very different dates/contexts — always segment by App Info `launchTimeInMillis`
- **`frequencyUpdated` vs `powerLevelUpdated`** — these appear to be different event types for overlapping purposes; relationship not yet fully documented

### Sample File Observations (diagnostic_VALERIE_90303856880026_2026-05-20_15_53_30_502.log)

- Log spans: 2026-04-20 to 2026-05-20 (30 days, 10 app launches)
- Device callsign: VALERIE, GID: 90303856880026, Serial: PNE233200358 (primary), PNE233200212 (earlier sessions)
- App version: 2.2.33 (51165ad5), ATAK 5.0.0, Samsung SM-G981U1 (API 33)
- Firmware: 3.2.10, Hardware v9
- 8 unique sender GIDs observed
- 5 frequency change events across the log lifetime

---

## Pro+ Application

### Overview
A goTenna application built on the Flutter/Dart framework.

- **Platform:** iOS and Android
- **Package:** `com.gotenna.pro`
- **Framework:** Flutter/Dart

### Log Types

| Platform | Log Types | Status |
|----------|-----------|--------|
| Android | 1 (confirmed) | ✅ Example log analyzed: rsdk_log_wendell_and.txt |
| iOS | 1 (confirmed) | ✅ Example log analyzed: rsdk_log_JonathaniOS.txt |

### Parsing Rules
> Both platforms are now implemented in `parser/rsdk.py`. The detailed,
> per-platform parsing rules and field tables live in the sections below:
> [Pro+ Application — iOS RSDK Log](#pro-application--ios-rsdk-log) and
> [Pro+ Application — Android RSDK Log](#pro-application--android-rsdk-log).
> This section is kept as the high-level overview only.

### Fields to Parse
> See the per-platform **Fields to Parse** tables in the iOS RSDK and Android
> RSDK sections below — they are the source of truth for what `rsdk.py` extracts.

---

## Relay Health Manager

### Overview
A Flutter/Dart application used to obtain health data from goTenna relays in the field.

- **Platform:** Android confirmed; iOS TBD
- **Package:** `com.gotenna.relaymanager`
- **Framework:** Flutter/Dart
- **Log format:** Android system log (logcat) — full device log including system noise

### Log Format

This is a **full Android logcat** dump, not an isolated app log. The file contains:
- Android system noise (io_stats, Watchdog, DeviceStorageMonitor, etc.)
- Appium/UiAutomator2 test framework output (used for automated testing)
- Flutter app output tagged as `I flutter`
- goTenna app activity visible in system entries (e.g. `com.gotenna.relaymanager` in WindowManager, SGM, ActivityManager)

The parser must filter for relevant lines and ignore system/test noise.

### Log Line Format

**Android logcat standard format:**
```
MM-DD HH:MM:SS.mmm  PID  TID  LEVEL TAG: message
```
Example:
```
03-04 04:26:17.711  4282  4282 I flutter : [Api] Get (https://portal-stage.gotennapro.com/api/v2/user/settings)
```

**Note:** No year in timestamp — year must be inferred from file metadata or context.

### Log Levels

| Level | Meaning |
|-------|---------|
| `V` | Verbose |
| `D` | Debug |
| `I` | Info |
| `W` | Warning |
| `E` | Error |
| `F` | Fatal |

### Fields to Parse

All parseable data comes from lines tagged `I flutter` (Flutter app output):

| Field | Source Tag | Example | Notes |
|-------|-----------|---------|-------|
| Timestamp | Line prefix | `03-04 04:26:17.711` | MM-DD HH:MM:SS.mmm — no year |
| API request | `[Api]` | `Get (https://portal-stage.gotennapro.com/api/v2/user/settings)` | HTTP method + URL |
| API response | `[Api]` | `Get (...) -> 200` | HTTP status code |
| Auth refresh attempt | `[AUTH]` | `Refresh (token...)` | Token value present but not needed for QA |
| Auth refresh result | `[AUTH]` | `Refresh -> 200 {...}` | HTTP status + JWT response |
| Portal retry | `[Portal]` | `Retrying (401) URL. Attempt 1` | HTTP status + URL + attempt number |
| Available frequencies | `[FrequencySetsNotifier]` | `Available frequencies -> [FrequencySetModel(...)]` | Full frequency set model including channels |
| Frequency set fields | `[FrequencySetsNotifier]` | `id, name, maxPowerWatts, deviation, isUseOnly, channelList` | Channel list includes mhz + isControlChannel per channel |

### Frequency Set Model Fields

| Field | Type | Example | Notes |
|-------|------|---------|-------|
| `id` | int | `26058` | |
| `name` | string | `Compliant` | |
| `maxPowerWatts` | float | `0.5` | |
| `deviation` | float | `2.0` | |
| `isUseOnly` | bool | `false` | |
| `channelList` | list | see below | |
| `fromPortal` | bool | `true` | |
| `createdBy` | string/null | `null` | |
| `overrideWatts` | float/null | `null` | |

### Channel Fields (per entry in channelList)

| Field | Type | Example | Notes |
|-------|------|---------|-------|
| `mhz` | float | `461.03750` | Frequency in MHz |
| `isControlChannel` | bool | `true` | True = control channel, False = data channel |

### Parsing Rules

1. **Filter by tag** — only parse lines where log tag is `flutter` (i.e. `I flutter :`)
2. **Extract category** — parse the `[Category]` prefix from the Flutter message body
3. **Ignore `[calculateLuminance]`** — this tag is high-volume UI noise with no QA value (817 occurrences observed in sample log); skip entirely
4. **Timestamp has no year** — use file metadata or session context to infer; flag if ambiguous
5. **Auth tokens** — present in `[AUTH]` lines; do not store token values, only HTTP status and outcome
6. **Frequency sets** — the `FrequencySetModel(...)` string must be parsed as structured data, not stored as raw string
7. **API polling** — the app polls `portal-stage.gotennapro.com/api/v2/user/settings` every ~5 minutes; repeated identical frequency set responses are expected and should be deduplicated or counted

### Known Observations from Sample Log (day1_RelayManagerLogs.txt)

- Log spans 2026-03-03 to 2026-03-04
- App process PID: 4282
- Other goTenna apps present on device: `com.gotenna.gokit`, `com.gotenna.atak`, `com.gotenna.pro`
- Only Flutter log output is parseable app data; rest is Android system/Appium noise
- Auth token refresh occurs every ~5 minutes (token expires in 300 seconds)
- Only one frequency set observed: `Compliant` (id: 26058)
- No relay health data (battery, firmware, signal) observed in this log sample — ⚠️ see Known Limitations

### Health Score scoping

The `relay_manager` summary carries **none** of the per-device Health Score dimension
inputs (`peak_temp_f`, `min_battery_pct`, `avg_rssi`, `ble_fail_count`,
`max_stored_messages`) — those come from device-format logs, and relay health
attributes remain undecoded (BLE payload limitation above). Consequently the UI Health
Score tab is scoped to device formats only (`atak`, `diagnostic`, `rsdk`) and excludes
`relay_manager`; otherwise a relay card would default-pass every dimension and show a
misleading 5/5. See the Health Score spec in `ui-requirements.md` (section 10).

---

## Shared Output Requirements

> _Document what the parsed output should look like — models, field names, data types_
> _To be defined once all log formats are confirmed_

---

## Known Limitations

- **Relay Health Manager — no dedicated app log format:** The Relay Health Manager currently only produces ADB (Android Debug Bridge) system logs — there is no dedicated app-level log export. Relay health data carried over BLE (battery, firmware version, signal strength) is captured as raw hex but not decoded, so it is not surfaced in a parseable form from the app log. A proper user-facing app log format may arrive in a future app version. (Note: this blockage is specific to the *app-level, BLE-sourced* health export. The relay radio's own **firmware UART/USB debug log is a separate source and is now parsed** — see [Relay Firmware (UART/USB Debug) Log](#relay-firmware-uartusb-debug-log). It surfaces firmware-internal data directly from the radio, but its serial/firmware-version fields live in a binary RHC payload and are likewise undecoded.)
- **Relay Health Manager — no year in timestamp:** Android logcat timestamps omit the year. Year must be inferred from file metadata or context; flag if ambiguous.
- **Relay Health Manager — full logcat format:** The log is a complete Android system log, not an isolated app log. Parser must filter aggressively to avoid processing system/Appium noise.
- **Android ATAK Plug-in:** Both log types confirmed as newline-delimited JSON. Parser built (`parser/atak.py`), including SDK Logging 2.0 `sdkError` aggregation.
- **Pro+ Application:** 1 log type per platform confirmed. iOS: rsdk_log_JonathaniOS.txt analyzed. Android: rsdk_log_wendell_and.txt analyzed.
- **Relay Health Manager — iOS:** Not yet confirmed whether an iOS version exists.
- **Pro+ diagnostic (block format) — firmware 3.1.11 omits originator identity:** Some firmware-3.1.11 diagnostic logs omit the originator callsign and GID from Received Message blocks, so the sender of those messages cannot be identified. `parser/diagnostic.py` now surfaces this in `parse_errors` with a `DATA LIMITATION —` entry, emitted **only when it actually manifests** (a Received Message block carrying neither originator identity field) and reporting the affected count (`{n} of {total}`). Logs that include the fields emit nothing.
- All temperatures stored internally in Celsius and must be converted to Fahrenheit for display.

---

_Last updated: 2026-06-12_

---

## Android ATAK Plug-in — Enhanced Log (UPDATED)

### Overview
A goTenna plugin that integrates with ATAK (Android Team Awareness Kit).

- **Platform:** Android only
- **Package:** `com.gotenna.atak`
- **Framework:** Native Android (not Flutter)
- **Log format:** Newline-delimited JSON objects (one per line)

### Filename Convention
```
diagnostic_ATAK_<CALLSIGN>_<GID>_<YYYY-MM-DD>_<HH_MM_SS_mmm>.log
```
Example: `diagnostic_ATAK_HOTEL_90215634664458_2026-03-04_16_42_04_775.log`

| Filename Segment | Meaning |
|-----------------|---------|
| `HOTEL` | Device callsign |
| `90215634664458` | Device GID |
| `2026-03-04_16_42_04_775` | Log export timestamp |

### Log Format

The file is an array of newline-delimited JSON objects. Each line is one record ending with a comma:
```json
{"timestampInMillis":1772664110169, ...},
{"timestampInMillis":1772664101408, ...},
```

All timestamps are **Unix epoch milliseconds** — must be converted to human-readable datetime for display.

### Record Types

There are 5 distinct record types, identified by their field set:

#### 1. App Info Record (1 per file)
Captured at app launch. Contains app and device identity.

| Field | Type | Example | Notes |
|-------|------|---------|-------|
| `launchTimeInMillis` | int | `1772635974500` | Unix epoch ms |
| `appVersion` | string | `"2.3.0 (be06682e) - [5.2.0]"` | App + SDK version |
| `buildNumber` | int | `1766517077` | |
| `atakVersion` | string | `"5.5.1.10"` | ATAK platform version |
| `version` | int | `1` | Log schema version |
| `deviceInfo.deviceModel` | string | `"Samsung SM-S711U1"` | Android device model |
| `deviceInfo.apiVersion` | int | `34` | Android API level |

#### 2. Device Health Record (~every 30 seconds)
One record per periodic radio health poll.

| Field | Type | Example | Notes |
|-------|------|---------|-------|
| `timestampInMillis` | int | `1772664074583` | Unix epoch ms |
| `serialNumber` | string | `"PNE234100406"` | Radio serial number |
| `connectionState` | string | `"CONNECTED"` | `CONNECTED` or `CONNECTING` |
| `batteryLevel` | int | `46` | Percent (0–100) |
| `isCharging` | bool | `false` | |
| `connectionType` | string | `"BLE"` | Connection type to radio |
| `mode` | string | `"NORMAL"` | Radio operating mode |
| `firmwareVersion` | string | `"3.2.10"` | Radio firmware |
| `storedMessages` | int | `0` | Messages stored on radio |
| `powerAmpTemperature` | int | `30` | Celsius — display as °F |
| `systemTemperature` | int | `24` | Celsius — display as °F |
| `transmitPowerDifferential` | int | `2` | ⚠️ See Known Limitations |
| `hardwareVersion` | int | `9` | Radio hardware revision |
| `bootloaderVersion` | int | `20` | |
| `chipArchitecture` | string | `"LEGACY_NXP"` | Radio chip type |
| `errorCode` | string | `"SystemErrorCodes(errorValue=0)"` | Parse error value integer |
| `gid` | int | `90215634664458` | Device GID (matches filename) |

> ⚠️ **Temperature note:** `systemTemperature` reads `0` when `connectionState` is `CONNECTING` — this is a placeholder value, not a real reading. Flag these as unreliable.

#### 3. Message Record (majority of records)
One record per RF message sent or received.

| Field | Type | Example | Notes |
|-------|------|---------|-------|
| `timestampInMillis` | int | `1772664110169` | Unix epoch ms — log receipt time |
| `logId` | int | `965606410` | Can be negative (signed 32-bit) |
| `messageTimestampInMillis` | int | `1772664110138` | Originator send time |
| `isSender` | bool | `true` | True = this device sent it |
| `senderGid` | int | `90215634664458` | Sender's GID |
| `deliveryStatus` | string | `"FULLY_RECEIVED"` | See delivery statuses below |
| `segmentCount` | int | `1` | Total RF segments |
| `numberOfOpenSegments` | int | `0` | Segments not yet received |
| `retryCount` | int | `0` | Number of TX retries |
| `deliveryTimeInMillis` | int | `8517` | ms from send to receive — ⚠️ can be negative (clock skew) |
| `version` | int | `1` | Message schema version |
| `messageProtocol` | string | `"BROADCAST"` | RF protocol |
| `message.type` | string | `"pli"` | Message content type |
| `message.interval` | string | `"60"` | PLI interval (PLI only) |
| `message.objectType` | string | `"PIN"` | Map object subtype (mapObject only) |
| `message.fileName` | string | `"UNKNOWN"` | File name (fileTransfer only) |
| `senderCallsign` | string | `""` | ⚠️ Empty in enhanced log — see Known Limitations |
| `senderUUID` | string | `""` | ⚠️ Empty in enhanced log |
| `originatorCallsign` | string | `""` | ⚠️ Empty in enhanced log |
| `originatorUUID` | string | `""` | ⚠️ Empty in enhanced log |
| `receiverGid` | int | `90215634664458` | `0` when isSender=true |
| `hopCount` | int | `1` | RF hops; `0` when isSender=true |
| `rssi` | int | `-19` | dBm; `0` when isSender=true |
| `receiverCallsign` | string | `""` | ⚠️ Empty in enhanced log |
| `receiverUUID` | string | `""` | ⚠️ Empty in enhanced log |

**Message types observed:**

| `message.type` | `message.objectType` | Count | Description |
|---------------|---------------------|-------|-------------|
| `pli` | — | 3796 | Position/location update |
| `mapObject` | `PIN` | 37 | Map pin |
| `mapObject` | `SHAPE` | 11 | Map shape |
| `mapObject` | `CIRCLE` | 4 | Map circle |
| `mapObject` | `ROUTE` | 2 | Map route |
| `mapObject` | `VEHICLE` | 1 | Map vehicle |
| `textChat` | — | 12 | Text message |
| `fileTransfer` | — | 7 | File transfer |

**Delivery statuses observed:**

| Status | Count | Meaning |
|--------|-------|---------|
| `SUCCESS` | — | Sender-side confirmed delivery (final ACK). Only on `isSender=true` `fileTransfer`. Distinct from `FULLY_RECEIVED`. |
| `FULLY_RECEIVED` | 3467 | Receiver assembled all segments |
| `SENT` | 387 | Sent by this device |
| `DELIVERED` | 9 | Unicast confirmed delivery |
| `PARTIALLY_RECEIVED` | 7 | Some segments missing |

#### 4. Event Record (8 observed)
Lifecycle and configuration change events.

| Field | Type | Example | Notes |
|-------|------|---------|-------|
| `timestampInMillis` | int | `1772656822686` | Unix epoch ms |
| `event.type` | string | `"deviceConnected"` | Event category |
| `event.connectionType` | string | `"BLE"` | Present on connect/disconnect events |
| `event.serialNumber` | string | `"PNE234100406"` | Present on `deviceConnected` only |
| `event.power` | float | `5.0` | Watts — present on `powerLevelUpdated` |
| `event.isDistance` | bool | `false` | Present on `pliSettingUpdated` |
| `event.interval` | int | `60` | Seconds — present on `pliSettingUpdated` |
| `event.isAutoSend` | bool | `true` | Present on `pliSettingUpdated` |
| `event.location` | object | `{lat, long, alt}` | Present on `deviceDisconnected` only |
| `event.updateStatus` | string | `"STARTED"` | Present on `firmwareUpdate` only |
| `event.updateTimeInMillis` | int | `1780500003000` | Present on `firmwareUpdate` only |

**Event types observed:**

| `event.type` | Count | Meaning |
|-------------|-------|---------|
| `deviceConnected` | 3 | Radio connected via BLE |
| `deviceDisconnected` | 3 | Radio disconnected (now carries `location`) |
| `powerLevelUpdated` | 1 | TX power changed |
| `pliSettingUpdated` | 1 | PLI interval/mode changed |
| `firmwareUpdate` | — | Firmware update lifecycle (`updateStatus`, `updateTimeInMillis`) — significant QA event |

#### 5. SDK Error Record (SDK Logging 2.0) — NEW

Structured SDK log events following the SDK Logging 2.0 schema. The **dominant
record type** in enhanced field logs (56,179 across 7 logs in the 2026-06-03
session — outnumbering message records 3:1). Despite the `sdkError` name these
are general structured log events, not error-only records.

| Field | Type | Example | Notes |
|-------|------|---------|-------|
| `id` | string | UUID | Record ID |
| `timestamp` | string | `2026-06-03T22:15:22.082133Z` | ISO 8601 UTC, microsecond precision |
| `tags` | string[] | `["ERROR","BLE"]` | `["ERROR","RADIO"]` also observed |
| `message.deviceState.platformType` | string | `"ANDROID"` | |
| `message.deviceState.connectionType` | string | `"BLE"` | |
| `message.deviceState.serialNumber` | string | `"PNE234200715"` | |
| `message.deviceState.address` | string | `"FB:6C:DB:3B:3A:9A"` | BLE MAC |
| `message.deviceState.connectionState` | string | `"CONNECTING"` | `"DISCONNECTED"` also observed |
| `message.deviceState.personalGid` | int | `90495447405391` | |
| `message.deviceState.batteryLevel` | int | `68` | |
| `message.deviceState.firmwareVersion` | string | `"3.2.11"` | |
| `message.deviceState.radioType` | string | `"PRO_X_2"` | **Surfaced nowhere else** — device classification |
| `message.deviceState.mcuuuid` | string | `"0028..."` | |
| `message.deviceState.endorsements` | string | `"PREMIUM"` | |
| `message.event.additionalInfo` | string | `"Gatt write back off..."` | Human-readable description |

> ⚠️ **Aggregate only — never store per-record.** Because of the volume, the parser
> emits a single `AtakSdkErrorSummary` (counts by tag, counts by additionalInfo,
> radio types, serials, connection states, plus one retained sample) and adds a
> `DATA LIMITATION` to `parse_errors`. Baseline volume for a healthy session is unknown.

### Parsing Rules

1. **Format:** Newline-delimited JSON — parse each line individually; skip malformed lines
2. **Record type detection:** Identify by presence of key fields, in this order:
   - Has `appVersion` → App Info record
   - Has `connectionState` → Device Health record
   - Has `logId` → Message record
   - Has `id` **and** `tags` **and** `timestamp` (top-level) → SDK Error record — **must precede the `event` check** (an sdkError record's `message` also nests an `event`)
   - Has `event` → Event record
3. **Timestamps:** All are Unix epoch milliseconds — divide by 1000 for seconds, then convert to datetime
4. **Temperature:** `powerAmpTemperature` and `systemTemperature` are Celsius — convert to Fahrenheit for display
5. **Callsigns/UUIDs:** All empty strings in this enhanced log format — do not rely on these fields
6. **Negative `deliveryTimeInMillis`:** Occurs in 767 records (18%) — caused by clock skew between devices, especially at high hop counts (3–4 hops). Flag but do not discard
7. **`transmitPowerDifferential` = 255:** Seen during `CONNECTING` state — indicates value not yet valid; treat as null
8. **`systemTemperature` = 0 during CONNECTING:** Placeholder, not a real reading — treat as null
9. **Filename parsing:** Extract callsign, GID, and export timestamp from filename
10. **`numberOfOpenSegments` = -99:** Sentinel meaning the transfer was cancelled/timed out before the open-segment count was known — store as `null`, never the literal -99. Positive values (e.g. 183) are genuine and preserved.
11. **`deliveryStatus` = SUCCESS:** Sender-side final-ACK confirmation; distinct from `FULLY_RECEIVED` (receiver assembled all segments). Only `deliveryTimeInMillis` on `SUCCESS`/`isSender` records is meaningful; receiver-side `0` is a placeholder.
12. **`message.fileName`:** Real filename on completed `fileTransfer` records; `"UNKNOWN"` when incomplete.
13. **`loggingUserLocation` / `transmittedLocation`:** Two distinct `{lat, long, alt}` objects — the logger's own GPS vs the location in the message payload. `transmittedLocation` is absent on `textChat` (store `null`).
14. **`originatorUUID`:** `ANDROID-*` UUID; store `""` when missing. `originatorCallsign` is empty in observed samples.
15. **`sdkError` records:** Aggregate into `AtakSdkErrorSummary`; never store per-record; surface a `DATA LIMITATION` for the unknown volume baseline. The total count stays informational, but `_result_to_dict()` sums the `ERROR|BLE` subset of `counts_by_tag` into `summary.ble_fail_count` to drive the BLE Health Score dimension. The fallback to the `deviceDisconnected` event count fires **only when no SDK 2.0 summary is present at all** (`atak_sdk_error_summary is None`) — a summary that exists but has zero `ERROR|BLE` entries is a genuine `0`, not a fallback trigger. The `> 0 = fail` threshold is an initial estimate pending field validation.

### Known Limitations — ATAK Enhanced Log

- **Callsign and UUID fields are always empty** in the enhanced log format — identity can only be determined from GID (`originatorUUID` does carry an `ANDROID-*` UUID, but `senderUUID`/`receiverUUID`/all callsigns are empty)
- **Negative `deliveryTimeInMillis`** (767 records, 18%) indicates clock skew between originator and receiver devices; most common at hop counts 3–4. **Distinguish two patterns:** *sporadic* negatives (varying per message/hop, ~18% here) are normal inter-device skew; a *constant whole-session* offset uniform across all senders and hop counts is **host-clock skew** on the receiving device (see P6 — KNOT showed a fixed ≈ −2 h offset across all 50 senders). The parser captures both honestly; interpretation differs.
- **`transmitPowerDifferential`** meaning is not fully documented — observed values 1–3 during normal operation and 255 during connecting state
- **Regular user log format** not yet confirmed — need example to compare against enhanced format
- **`PARTIALLY_RECEIVED` records** all appear to be `fileTransfer` type — may indicate file transfers are unreliable over mesh; needs further investigation
- **`numberOfOpenSegments = -99` is a sentinel** meaning the transfer was cancelled before the segment count was known — treated as `null`/unknown in the UI, never displayed as -99
- **Receiver-side `deliveryTimeInMillis = 0` on `fileTransfer`** is a placeholder, not a real delivery time — only meaningful when `isSender=true` and `deliveryStatus=SUCCESS`
- **`serialNumber = "Unknown"` in Device Health records** is expected behavior during BLE reconnection (the health poll fires before the serial resolves) — not a parser error
- **SDK Logging 2.0 / `sdkError` record volume** (56,179 across 7 logs) is very high; the baseline for healthy sessions is unknown — the total count is flagged as informational in `parse_errors` until a baseline is established. The `ERROR|BLE` subset is the one exception that drives a pass/fail signal (the BLE Health Score dimension via `summary.ble_fail_count`); that threshold is likewise unvalidated and may change once a BLE-error baseline is established
- **`sdkError` regular vs enhanced scope is unconfirmed** — it is not yet known whether regular (non-enhanced) user logs from the same firmware also emit `sdkError` records or whether this record type is exclusive to enhanced/debug sessions. The `Differences: Regular vs Enhanced` table is intentionally left without an `sdkError` row until a regular log from the same firmware version is available to compare

### Sample File Observations (day1 session)

- Session: 2026-03-04 14:41 to 22:41 (8 hours)
- Device callsign: HOTEL, GID: 90215634664458, Serial: PNE234100406
- Firmware: 3.2.10, Hardware v9, Chip: LEGACY_NXP
- 20 unique sender GIDs observed (active mesh network)
- Two radios connected during session: PNE234100241 (briefly), PNE234100406 (primary)

---

## Pro+ Application — iOS RSDK Log

### Overview
The Pro+ iOS app uses the goTenna RSDK and produces line-by-line structured text logs.

- **Platform:** iOS (confirmed)
- **Package:** `com.gotenna.pro`
- **Framework:** RSDK (same SDK as Android)

### Log Format

Identical line structure to the existing RSDK format already parsed by `parser/rsdk.py`:

```
YYYY-MM-DDTHH:MM:SS.ffffffZ  LEVEL  Device - SERIAL  COMPONENT: message
```

Example:
```
2026-03-03T14:53:22.804698Z DEBUG Device - PNE234100406 Radio: Data incoming from device PNE234100406
```

- **Timestamp:** Full ISO 8601 UTC with microseconds — year is present ✅
- **Platform detection:** `IosBleRadio` present in log → infer iOS ✅
- **Deduplication needed:** Many lines appear exactly twice (iOS SDK quirk) — existing deduplication in `rsdk.py` handles this ✅

### Log Levels Observed

| Level | Count |
|-------|-------|
| `DEBUG` | 339,712 |
| `INFO` | 48,829 |
| `WARN` | 423 |
| `ERROR` | 1 |

### Component Tags Observed

| Component | Line Count | Notes |
|-----------|-----------|-------|
| `GRIP_SENDER` | 151,020 | Outbound message queue management |
| `Radio` | 70,367 | BLE radio layer |
| `COMMANDHANDLER` | 53,207 | Command parsing — contains DeviceInfo |
| `BleChunkProcessor` | 26,346 | BLE packet chunking |
| `ReceivedData` | 22,698 | Parsed command output |
| `MESSAGE_QUEUE` | 19,606 | Radio state and sequence tracking |
| `IosBleRadio` | 18,883 | iOS BLE reconnection events |
| `GRIP_Receiver` | 11,714 | Inbound message processing, ACKs |
| `ContactManager` | 7,409 | Contact/callsign discovery |
| `Send_Defferred` | 7,079 | Hardware send queue |
| `Segmentation` | 490 | MTU/segmentation checks |
| `Base` | 87 | Base layer |
| `Remaining_messages` | 59 | Stored message count on radio |

### Fields to Parse

#### Device Info (from `COMMANDHANDLER` lines containing `DeviceInfo(...)`)

| Field | Source | Example | Notes |
|-------|--------|---------|-------|
| `deviceSerial` | `DeviceInfo(...)` | `PNE234100406` | Radio serial number |
| `firmwareVersion` | `DeviceInfo(...)` | `3.2.10` | |
| `hardwareVersion` | `DeviceInfo(...)` | `9` | |
| `bootloaderVersion` | `DeviceInfo(...)` | `20` | |
| `batteryLevel` | `DeviceInfo(...)` | `99` | Percent; `-1` = not yet valid |
| `powerAmpTemperature` | `DeviceInfo(...)` | `27` | Celsius → convert to °F; `-1` = not yet valid |
| `systemTemperature` | `DeviceInfo(...)` | `0` | Celsius → convert to °F; `0` on first connect = placeholder |
| `errorCode` | `DeviceInfo(...)` | `SystemErrorCodes(errorValue=0)` | Parse error integer |
| `batteryCharging` | `DeviceInfo(...)` | `false` | |
| `numberOfStoredMessage` | `DeviceInfo(...)` | `0` | |
| `reflectedPowerRatio` | `DeviceInfo(...)` | `255` | `255` = not yet valid |

#### BLE Reconnection Failures (from `IosBleRadio` lines)

| Field | Source | Example |
|-------|--------|---------|
| `timestamp` | Line prefix | `2026-03-03T17:45:22.941017Z` |
| `radio_serial` | `Device - SERIAL` | `PNE234100241` |
| Pattern | `IosBleRadio: BLE reconnection failed, retrying in 2000ms` | |

#### Contact Discovery (from `ContactManager` lines)

| Field | Source | Example | Notes |
|-------|--------|---------|-------|
| `callsign` | `Created contact for user <callsign>` | `MikeRiOS` | |
| `uuid` | `with UUID <uuid>` | `899bc6d1-072c-58fe-bb5b-eba3a2c13f16` | |


#### GRIP Structured Message Fields (GRIP_SENDER and GRIP_Receiver)

Both `GRIP_SENDER` (outgoing) and `GRIP_Receiver` (incoming) emit a structured
fields line for every message segment. This is the richest per-message data in
the RSDK format.

**Line format:**
```
GRIP_SENDER:   Outgoing message fields: MsgType: N; SRC: N; DST: N; appId: N; msgId: N; seqNo: N; isFirstPacket: N; segReserved: N; isAck: N; requiresAck: N; agOriginated: N; isPeriodic: N; repCounter: N; reservedByte: N segment size: N
GRIP_Receiver: Incoming message fields: MsgType: N; SRC: N; DST: N; appId: N; msgId: N; seqNo: N; isFirstPacket: N; segReserved: N; isAck: N; requiresAck: N; agOriginated: N; isPeriodic: N; repCounter: N; reservedByte: N hops: N rssi: N segment size: N
```

Note: incoming lines include `hops` and `rssi` **before** `segment size`. Outgoing lines do not include these fields.

| Field | Parsed As | Notes |
|-------|-----------|-------|
| `MsgType` | `grip_message.msg_type` | `0` = private/unicast · `2` = broadcast |
| `SRC` | `grip_message.src_gid` | Sender's **hashed** GID — signed 32-bit integer |
| `DST` | `grip_message.dst_gid` | Destination hashed GID; `0` for broadcast |
| `appId` | `grip_message.app_id` | App ID used when initializing SDK |
| `msgId` | `grip_message.msg_id` | Message ID; matches `file id` in COMMANDHANDLER lines |
| `seqNo` | `grip_message.seq_no` | Segment sequence number — **reverse order** (highest = first packet) |
| `isFirstPacket` | `grip_message.is_first_packet` | `1` = this is the first (highest seqNo) segment |
| `isAck` | `grip_message.is_ack` | `1` = this segment is an ACK, not data |
| `requiresAck` | `grip_message.requires_ack` | `1` = receiver must send keep-alive ACK after this segment |
| `isPeriodic` | `grip_message.is_periodic` | `1` = message is a periodic (PLI) broadcast |
| `repCounter` | `grip_message.rep_counter` | Retransmission count for this segment. `0` = first attempt. Firmware cancels transfer after 3 attempts. |
| `segment size` | `grip_message.segment_size` | Byte size of this segment |
| `hops` | `grip_message.hops` | **Incoming only.** Genuine RF mesh hop count. |
| `rssi` | `grip_message.rssi` | **Incoming only.** Real dBm (signed). |

> ⚠️ **SRC and DST are hashed GID values, not full GIDs.** They are signed 32-bit integers derived from the full 64-bit GID. The same node will always produce the same hash, enabling correlation across messages, but the hash cannot be reversed to the full GID without a lookup table.
>
> ⚠️ **repCounter on outgoing lines only.** The retransmission count appears on `GRIP_SENDER` outgoing lines. A `repCounter > 0` means the firmware retried that segment. `repCounter = 2` means one more failure will cancel the transfer.
>
> ⚠️ **hops and rssi are genuine RF data on incoming lines.** Unlike the RSDK hop count from older `SendMessageResponse` patterns (which was an SDK sequence counter), these values from `GRIP_Receiver` incoming message fields are real RF mesh hop count and received signal strength.

#### GRIP Transfer Lifecycle (COMMANDHANDLER + GRIP_SENDER)

Three additional log lines enable end-to-end delivery time tracking:

| Line pattern | Component | Meaning |
|-------------|-----------|---------|
| `File transmission started, file id: N` | `COMMANDHANDLER` | Transfer begins on sender |
| `File has been successfully delivered to destination, file id: N` | `COMMANDHANDLER` | Transfer complete on sender |
| `sent file msgId: N stopped with true in Nms earlyCancel: false` | `GRIP_SENDER` | Sender stopped; delivery time in ms; `earlyCancel: true` = cancelled |
| `Full grip file received! id: N number of segments: N` | `COMMANDHANDLER` | Transfer complete on receiver side |

The delta between `File transmission started` and `File has been successfully delivered` is the end-to-end delivery time (`delivery_ms` in `GripTransfer`).

#### GRIP ACK Events (from `GRIP_Receiver` lines)

| Event | Pattern | Notes |
|-------|---------|-------|
| Final ACK | `SRC: Final ACK received, message fully delivered` | Unicast confirmed delivered. No message ID in line — stored as empty string. |
| Keep-alive ACK | `SRC: Keep-alive ACK received. Segment ID: N msgId: N` | Mid-transfer ACK. `msgId` captured as `message_id`. |

> ⚠️ **No timeout-outcome lines exist.** `"expected timeout of Xms"` (GRIP_SENDER) is a send-start log, not a delivery failure. No `outcome = "timeout"` events are produced.
>
> ⚠️ **NACKs on iOS** surface via the `NACK` component tag (same as Android), not via `GRIP_Receiver`.

#### Radio Error (from `Radio` lines)

| Pattern | Meaning |
|---------|---------|
| `failed to provision device on reconnection, disconnecting` | Radio failed to re-pair after BLE reconnect |

#### Stored Messages (from `Remaining_messages` lines)

| Pattern | Example |
|---------|---------|
| `Remaining messages in storage <n>` | `Remaining messages in storage 1` |

### Parsing Rules

1. **Line format** matches existing `_LINE_RE` in `rsdk.py` — no change needed to line parser
2. **Platform detection** — `IosBleRadio` present → iOS ✅ (existing logic works)
3. **Deduplication** — exact duplicate lines are an iOS quirk; existing 120-char key deduplication in `rsdk.py` handles this ✅
4. **Battery extraction** — `batteryLevel=` in `DeviceInfo(...)` lines; existing `_SYS_BATT_RE` (`batteryLevel[=:\s]+`) matches correctly ✅
5. **⚠️ PA Temperature bug** — existing `_SYS_TEMP_RE` matches `powerAmpTemp[=:\s]+` but the actual field name in this log is `powerAmpTemperature=` — **regex does not match**; parser is currently missing all temperature data from this format. Fix: update regex to `powerAmpTemperature[=:\s]+`
6. **`DeviceInfo` regex** — existing `_DEV_INFO_RE` looks for `deviceSerial=` and `firmwareVersion=` — field order in this log places `firmwareVersion` before `deviceSerial`; verify regex handles non-greedy match correctly across field order
7. **Invalid sentinel values** — `batteryLevel=-1`, `powerAmpTemperature=-1`, `systemTemperature=-1`, `reflectedPowerRatio=255` indicate values not yet valid on first connect; treat as null, do not record
8. **Two radios in log** — `PNE234100241` (primary, 388,917 lines) and `PNE234100406` (briefly connected, 48 lines); parser must track per-serial
9. **Temperatures** — all Celsius; convert to °F for display

### Known Limitations — Pro+ iOS RSDK Log

- **⚠️ Parser bug:** `_SYS_TEMP_RE` in `rsdk.py` uses `powerAmpTemp` but log field is `powerAmpTemperature` — temperature is not being captured; requires regex fix
- **`systemTemperature=0`** on first connect is a placeholder, not a real reading — cannot distinguish from a genuine 0°C reading without context
- **`reflectedPowerRatio=255`** meaning is not fully documented; appears as a sentinel for "not yet valid"
- **Contact callsigns** are available via `ContactManager` lines but not currently parsed by `rsdk.py`
- ✅ **TX pattern bug fixed:** `rsdk.py` previously targeted `SendMessageResponse.*FINAL_ACK` etc. Now correctly matches `GRIP_Receiver` structured fields lines and final ACK text lines. NACKs handled via `component == "NACK"` (unchanged).
- **GRIP structured fields now parsed:** `GRIP_SENDER` outgoing and `GRIP_Receiver` incoming message fields lines are fully parsed into `GripMessage` records. `hops` and `rssi` from incoming lines are genuine RF data. `repCounter` tracks retransmissions per segment.
- **GRIP hop count / RSSI availability now surfaced in `parse_errors`:** hop count and RSSI exist **only** on `GRIP_Receiver` incoming message-fields lines. When a session has no such lines (e.g. outgoing-only GRIP, or no GRIP at all), those RF fields are unavailable for the whole log. `parser/rsdk.py` now emits a `DATA LIMITATION —` entry in that case rather than implying the radio reported no hops. Outgoing GRIP messages alone do **not** suppress the entry — the lines must be incoming.
- **GRIP transfer lifecycle now tracked:** End-to-end delivery time (`delivery_ms`) computed from `File transmission started` → `File has been successfully delivered` delta. Stored in `GripTransfer` records.
- **`Send_Defferred`** and `Remaining_messages` components contain potentially useful data not currently captured

### Sample File Observations (rsdk_log_JonathaniOS.txt)

- Session: 2026-03-03 14:53 to 22:23 (7.5 hours)
- Primary radio: PNE234100241 (388,917 lines)
- Secondary radio: PNE234100406 (briefly connected at session start, 48 lines)
- Firmware: 3.2.10, Hardware v9
- BLE reconnection failures observed on PNE234100241 starting at 17:45
- One provisioning error at 20:12: `failed to provision device on reconnection, disconnecting`
- Contacts discovered: `MikeRiOS` (UUID: 899bc6d1-072c-58fe-bb5b-eba3a2c13f16)

---

## Pro+ Application — Android RSDK Log

### Overview
The Pro+ Android app uses the same goTenna RSDK as iOS but produces a noticeably different log.

- **Platform:** Android (confirmed)
- **Package:** `com.gotenna.pro`
- **Framework:** RSDK (same SDK as iOS)

### Log Format

Identical line structure to iOS RSDK and existing `parser/rsdk.py`:

```
YYYY-MM-DDTHH:MM:SS.ffffffZ  LEVEL  Device - SERIAL  COMPONENT: message
```

- **Timestamp:** Full ISO 8601 UTC with microseconds — year present ✅
- **Platform detection:** `AndroidBleRadio` present → Android ✅ (existing logic works)
- **⚠️ No duplicate lines** — Android does NOT have the iOS duplicate-line quirk; deduplication in `rsdk.py` is harmless but unnecessary for Android logs

### Key Differences vs iOS RSDK Log

| Feature | iOS | Android |
|---------|-----|---------|
| Duplicate lines | ✅ Yes (every line doubled) | ❌ No duplicates |
| Platform tag | `IosBleRadio` | `AndroidBleRadio` |
| BLE reconnect failures | `IosBleRadio: BLE reconnection failed` | Not observed; different reconnect behavior |
| NACK component | Not present as separate tag | `NACK` component tag present |
| `reflectedPowerRatio` | `255` (sentinel) on connect | Real values (4–10 observed) |
| Log volume | ~389K lines (7.5 hrs) | ~117K lines (2.2 hrs) |

### Log Levels Observed

| Level | Count |
|-------|-------|
| `DEBUG` | 98,676 |
| `INFO` | 18,867 |
| `ERROR` | 6 |

### Component Tags Observed

| Component | Line Count | Notes |
|-----------|-----------|-------|
| `GRIP_SENDER` | 42,789 | Outbound message queue |
| `Radio` | 21,085 | BLE radio layer |
| `COMMANDHANDLER` | 15,248 | Command parsing — contains DeviceInfo |
| `AndroidBleRadio` | 12,541 | Android BLE write/confirm layer |
| `BleChunkProcessor` | 7,529 | BLE packet chunking |
| `ReceivedData` | 6,393 | Parsed command output |
| `MESSAGE_QUEUE` | 3,709 | Radio state and sequence tracking |
| `GRIP_Receiver` | 3,463 | Inbound message processing |
| `Send_Defferred` | 2,342 | Hardware send queue |
| `ContactManager` | 2,270 | Contact/callsign discovery |
| `Segmentation` | 147 | MTU/segmentation checks |
| `NACK` | 18 | ⚠️ Android-only — explicit NACK component tag |
| `Remaining_messages` | 15 | Stored message count |

### Fields to Parse

All fields from the iOS RSDK log apply here. Android-specific additions:

#### NACK Events (Android only — `NACK` component tag)

| Pattern | Level | Meaning |
|---------|-------|---------|
| `SRC a nack has been received but doesn't match the pending outbound file, discarding.` | ERROR | Stale NACK — no matching outbound message |
| `src: nack triggered for GoTennaTransportFrame(...messageId=<id>...)` | DEBUG | NACK received for specific message |
| `SRC: missing segments [<n>] for msgId: <id> from <src> to <dst>` | DEBUG | Segment retransmit request |
| `Retransmitting segments [<n>] for message id: <id>` | DEBUG | Retransmit initiated |

Key fields to extract from NACK lines:
- `messageId` — message being NACKed
- `origin` / `uniMultiCastDestination` — source and destination GIDs
- Missing segment list

#### PowerBandwidth (Android — `MESSAGE_QUEUE` lines)

Observed power level changes during session — useful for correlating RF performance:

| Field | Example | Notes |
|-------|---------|-------|
| `power` | `0.5`, `1.0`, `2.0`, `5.0` watts | TX power setting |
| `bandwidth` | `11.80 kHz` | Channel bandwidth |
| `action` | `SET` / `GET` | Command type |

#### `reflectedPowerRatio` (Android — real values)

On Android, `reflectedPowerRatio` in `DeviceInfo(...)` contains real values (4–10 observed), unlike iOS where it is `255` on first connect. This field may indicate antenna/RF health and should be captured.

### Parsing Rules

All iOS RSDK parsing rules apply. Android-specific additions:

1. **No deduplication needed** — Android logs have no duplicate lines; existing deduplication is safe but a no-op
2. **NACK component** — parse `NACK:` tagged lines for message retransmit events; not present in iOS logs
3. **`reflectedPowerRatio`** — capture real values from Android DeviceInfo (not sentinel `255`); flag `255` as invalid on either platform
4. **⚠️ PA Temperature bug applies here too** — same `powerAmpTemperature` vs `powerAmpTemp` regex mismatch as iOS; fix needed in `rsdk.py`
5. **PowerBandwidth** — log records power/bandwidth changes; parse if TX power history is required

### Known Limitations — Pro+ Android RSDK Log

- **⚠️ PA Temperature bug** — same as iOS: `_SYS_TEMP_RE` in `rsdk.py` will not match `powerAmpTemperature=` on Android either
- ✅ **NACK parsing correct:** NACKs handled via `component == "NACK"` path. `SendMessageResponse` patterns were removed.
- **GRIP structured fields and transfer lifecycle:** Same as iOS — see iOS RSDK section above.
- ✅ **PA Temperature bug fixed (both platforms):** `_SYS_TEMP_RE` updated to match `powerAmpTemperature=` — temperature data now captured correctly for both iOS and Android RSDK logs.
- **`ContactManager` empty UUID warnings** — `Tried to update contact storage but sender uuid was empty` appears frequently; contact lookups may be incomplete for some messages
- **`reflectedPowerRatio` meaning** — real values observed (4–10) but no documentation found on what range is normal vs anomalous

### Sample File Observations (rsdk_log_wendell_and.txt)

- Session: 2026-03-03 19:45 to 21:57 (2.2 hours)
- Device: PNE234200715, Firmware 3.2.10, Hardware v9
- Contact discovered: `Wendell And` (UUID: 6e82240c-e95e-5951-be0c-2ee060029c54)
- 6 NACK errors observed between 20:08–20:15
- Power level changes: 2.0W → 1.0W → 0.5W → 5.0W during session
- No BLE reconnection failures observed (Android reconnect behavior differs from iOS)

---

## Relay Firmware (UART/USB Debug) Log

### Overview

The relay radio's own firmware emits a serial debug console over UART/USB. This
is **not** an app log — it comes directly off the radio, so it surfaces
firmware-internal state (message-history buckets, routing decisions, channel
energy, neighbor table) that no app-level log exposes. Parsed by
`parser/fw_log.py`. Detection runs **first** (priority 1) because the line
format is highly distinctive and cannot collide with the other four formats.

### Log Format

```
[<ts_abs>-<delta_ms>, <MODULE>, <LEVEL>] <message>
```

- `ts_abs` / `delta_ms` — **relative milliseconds from boot, not wall clock.**
  `delta_ms` (time since previous line) is captured by the regex but not used.
- `MODULE` — one of `TRX`, `RELAY`, `TPORT`, `FLSH`, `MAIN`, `PRNT`, `USB`,
  `DEBUG`.
- `LEVEL` — `INFO`, `ERROR`, `WARN`, or `DEBUG`.

Bucket-history lines fall **outside** the bracket pattern and are parsed
separately:

```
bucket[N] HH - HH hours ago: X messages rx'd Y messages relayed Z messages tx'd
```

### Detection

`is_fw_log()` scans the first 30 non-empty lines and returns `True` once it sees
**≥3** bracket lines whose module is in the known firmware-module set. The
catch-all `diagnostic` parser never sees these because fw_log is checked first.

### Log Levels

- `INFO`, `ERROR`, `WARN` — parsed.
- `DEBUG` — **skipped** (roughly half of all lines), counted in `skipped_debug`.

### Fields to Parse

| Source line | Parsed into | Notes |
|-------------|-------------|-------|
| `rhc_build_resp: using origin hash 0x<hash>` | `origin_hash` | Authoritative device identity (short address) |
| First `RELAY` `prevSdr=<hash>` | `origin_hash` (fallback) | **Best-effort only** — `prevSdr` is the previous sender, so this may be a neighbor's hash, not self. Used only when no RHC origin line appears |
| `rhc_build_resp: version 0x<v>` | `fw_format_version` | RHC response format version, not radio firmware version |
| `rhc_build_resp: enter` | `rhc_poll_count` (+1) | One per health poll |
| `bucket[N] HH - HH hours ago: ...` | `buckets[]` (`FwBucket`) | 6-hour message-count windows. RHC history repeats once per poll; counts grow monotonically, so the highest-rx snapshot per index is kept (the most recent poll) |
| `TRX INFO` `RF Configuration for <device>` … | `rf_config` (`FwRfConfig`) | Block start. Captures `device_type`, `tx_power`, `bit_rate` (ends the block), `region`, `frequencies_hz` (9-digit Hz), `control_channels`, `data_channels` |
| `TRX INFO` `Energy on chn=N: last_rssi=-XdBm > avg_rssi=-YdBm (cnt=Z)` | `energy_samples[]` | `last_rssi` per preamble detection — the **RSSI proxy** surfaced in the UI |
| `TRX` `RSSI[N]: avg=… last=… [min=… max=…] num=…` | `rssi_samples[]` (`FwRssiSample`) | **DEBUG-level → skipped → always empty** in observed logs; matcher kept wired ahead of a firmware build that emits these at INFO |
| `RELAY INFO` `Msg-N cmd=N: transmitMsg=… flooding=… echo=… vine= …` | `routing` (`FwRoutingDecision`) | Increments `transmit` / `flood` / `echo` / `vine` per `=1` flag |
| `RELAY INFO` `msg already Rx` / `msg already TX` | `routing.skip_rx` / `routing.skip_tx` | Duplicate-suppression counts (rx and tx paths) |
| `RELAY INFO` `neighborAdd[N]: update hash=<h>, …` | `neighbor_hashes[]` | Unique node hashes seen |
| `ERROR` `Battery stabilization …` | `battery_error_count` | Counted **separately** from real errors — known firmware quirk |
| Other `ERROR` lines | `error_counts{module}`, `error_messages[]` | Up to 20 unique messages |
| `WARN` lines | `warn_counts{module}`, `warn_messages[]` | Up to 20 unique messages |
| Min/max bracket timestamps | `first_ts_ms` / `last_ts_ms` / `duration_ms` | Relative ms |

### Parsing Rules

1. Two logical passes over the lines: bucket lines (raw text) and bracket lines
   (`INFO`/`ERROR`/`WARN`).
2. DEBUG lines are dropped before any field matching — anything that only
   appears at DEBUG (e.g. `RSSI[]`) will not be captured.
3. Buckets are de-duplicated per index keeping the highest rx (most recent
   poll), then sorted by index descending (newest window first).
4. Battery stabilization errors never count toward `error_counts`.
5. Serial number and firmware version are **not** extracted — they live in the
   binary RHC payload (see Known Limitations).

### Known Limitations — Relay Firmware Log

- **Relative timestamps:** ms from boot, not wall clock. A session cannot be
  pinned to absolute time without a reference point from a correlated Relay
  Manager log. (The Time Window step is skipped for this format — its timestamps
  don't match the wall-clock scan.)
- **Binary RHC payload:** device serial number and firmware version are encoded
  in the binary RHC response, not plaintext. Identity is the origin hash only.
- **Battery stabilization quirk:** these errors fire even when the battery is
  already stable; counted separately, not indicative of hardware failure.
  Pending field validation.
- **RSSI[] is DEBUG-only:** `rssi_samples` / `rssi_summary` are always empty;
  channel energy is the RSSI proxy. The matcher is kept for a future firmware
  build that may emit RSSI at INFO.
- **Single-fixture validation:** parser behavior (detection, `prevSdr` origin
  fallback, bucket de-dup) is currently proven against one sample
  (`tests/fixtures/fw_log_sample.log`). A second real log is needed to exercise
  the fallback paths.

### Sample File Observations (fw_log_sample.log)

- Origin hash: `0f07`; RHC format version `0x10`; 1 RHC poll.
- 12 bucket windows; most recent (0–6 hrs) = 100 rx / 30 relayed / 1 tx.
- RF config: goTenna Pro, 3 frequencies, control channel [0], data channels [1, 2].
- Routing: 1 each of transmit / echo / vine; 1 skip_rx; 1 skip_tx.
- 2 neighbors (`e1a5`, `83e5`); 2 battery stabilization errors; 1 USB error; 1 RELAY warn.

---

## Message Protocol Architecture — Cross-Format Requirements

### Overview

The goTenna ATAK plugin supports three message protocols that determine how
messages are routed across the mesh network. Understanding these is essential
for correctly interpreting delivery outcomes, failure analysis, and congestion
measurements across all log formats.

### Protocol Definitions

| Protocol | Value in logs | Description | UI lane |
|----------|--------------|-------------|---------|
| BROADCAST | `"BROADCAST"` | One-to-many. Message is transmitted to all devices on the network. All devices receive and log it. | BROADCAST |
| PRIVATE | `"PRIVATE"` | One-to-one addressed transmission. ATAK plugin log term. Other devices relay but only the intended recipient processes it. | PRIVATE |
| UNICAST | `"UNICAST"` | One-to-one addressed transmission. RSDK log term. **Functionally synonymous with PRIVATE in the goTenna mesh** — same RF behavior, different label used by the SDK vs the ATAK plugin. | PRIVATE (normalized) |

> **Normalization rule:** `UNICAST` and `PRIVATE` are the same protocol in
> goTenna mesh — they differ only in naming between log formats. The parser
> must normalize both to a single `PRIVATE` lane in the UI. Never show
> UNICAST as a separate lane from PRIVATE.

### Message Type × Protocol Matrix

| Message Type | BROADCAST | PRIVATE | GRIP |
|-------------|-----------|---------|------|
| PLI | ✅ Always | ✗ Never | ✗ |
| textChat | ✅ Yes | ✅ Yes | ✗ |
| fileTransfer | ✅ Yes | ✅ Yes | ✅ Always |
| mapObject (PIN, etc.) | ✅ Yes | ✅ Yes | ✗ |

**Key rules:**
- PLI is always BROADCAST — it is a network-wide position report by definition.
- fileTransfer always uses GRIP for segmented delivery management, regardless
  of whether the transfer is BROADCAST or PRIVATE.
- GRIP is fileTransfer-only. It does not carry textChat or mapObject messages.
- textChat, fileTransfer, and mapObject can each be sent as BROADCAST or
  PRIVATE/UNICAST at the user's discretion.
- PRIVATE and UNICAST are synonymous in goTenna mesh — same RF behavior,
  different label used by the ATAK plugin (`PRIVATE`) vs the SDK (`UNICAST`).
  Always normalize to a single PRIVATE lane in analysis and UI.
- Day 2 field session (2026-06-04) did not include private message tests.
  The 53 PRIVATE fileTransfer records in gt_Sassy_B_Net's log originated
  from devices outside the 14-device test inventory (GIDs 90263279227901
  and 90459992601199) — likely background activity from other network users.

### GRIP — File Transfer Protocol

GRIP (goTenna Reliable IP) is the segmented delivery protocol that manages
file transfer across the mesh. It operates on top of BROADCAST or PRIVATE
at the application layer.

**GRIP-specific fields on fileTransfer records:**

| Field | Parsed name | Description |
|-------|-------------|-------------|
| `segmentCount` | `segment_count` | Total segments the file was divided into |
| `numberOfOpenSegments` | `open_segments` | Segments not yet received; −99 = transfer cancelled before count known (treat as `None`) |
| `retryCount` | `retry_count` | Number of GRIP retransmission attempts |
| `deliveryTimeInMillis` | `delivery_time_ms` | Sender-side only — time from first segment to final ACK. Always `0` on receiver side (placeholder, not real). |
| `deliveryStatus: SUCCESS` | `delivery_status` | Sender-side confirmed delivery with ACK. Receiver-side equivalent is `FULLY_RECEIVED`. |

**Segment size:** ~71 bytes/segment confirmed against 2026-06-04 field session
actual file sizes (e.g. 25.53 KB ÷ 368 segments = 71 bytes/seg, consistent
across all 6 official transfers).

**BROADCAST vs PRIVATE GRIP behavior:**
- BROADCAST GRIP: all devices on the mesh receive segments; any device can
  relay segments to others. Generates one logId shared across all receivers.
- PRIVATE GRIP: segments addressed to a specific GID; other devices relay
  but do not process. Generates one logId shared between sender and recipient.

### logId — Cross-Device Correlation Key

`logId` is assigned by the **sender** at transfer initiation and embedded in
every segment. It is the definitive join key for correlating delivery outcomes
across multiple device logs.

**Rules:**
- A matching logId across sender and receiver logs = confirmed same transfer.
- Segment count similarity alone is NOT sufficient — two different transfers
  can have the same segment count.
- When a relay device re-initiates a transfer (retransmission), the new sender
  generates a **new logId**. The segment count remains the same but the logId
  changes. This is the relay copy / retransmission mismatch pattern.
- `logId` values are 32-bit signed integers and can be negative.

**Relay copy detection (observed in 2026-06-04 GATOR data):**
GATOR received file transfer records with segment counts matching official
transfers (368, 92, 370, 344 segments) but different logIds than FUJIN's
originals. These are probable relay copies — the mesh routing the files
through intermediate nodes, each generating a new logId at the relay point.
None completed successfully. GATOR's one official success (T4) matched FUJIN's
logId `-1867690559` exactly at 4 hops / −77 dBm.

---

## Parser Requirements — Day 2 Field Session Findings (2026-06-04)

### P1 — MESMER SDK Tag Profile (HIGH — correctness bug)

**Finding:** MESMER (firmware 3.1.11) produces sdkError records with `DEBUG`
severity tags (`DEBUG|PROCESSING`, `DEBUG|RADIO`, `BLE|DEBUG`) instead of
`ERROR` severity tags like all other devices (`ERROR|BLE`, `ERROR|RADIO`).
The BLE health score dimension uses `ERROR|BLE` counts, causing MESMER to
falsely pass the BLE health check despite confirmed BLE instability (5
disconnect events in the first 5 minutes, 204,191 sdkError records).

**Requirement:** `ble_fail_count` in the ATAK summary must count BLE-related
SDK errors regardless of severity tag. Include both `ERROR|BLE` and `BLE|DEBUG`
(and any other tag combination containing `BLE`) when computing the BLE health
dimension. The distinction between firmware 3.1.11 (DEBUG tags) and 3.2.10+
(ERROR tags) must not affect the health score outcome.

**Status:** ✅ Done — `_result_to_dict()` in `api/routes/parse.py` now counts
any `counts_by_tag` key containing `BLE` regardless of severity (PR #4).

---

### P2 — Protocol Separation in TX/RX, File Transfer, and Congestion Analysis (MEDIUM)

**Finding:** BROADCAST and PRIVATE protocol messages have fundamentally
different failure modes and should not be aggregated together in delivery
statistics. The 53 PRIVATE fileTransfer failures in gt_Sassy_B_Net's log
(all `PARTIALLY_RECEIVED`) are invisible when mixed with BROADCAST transfer
statistics. Congestion analysis is also affected — PRIVATE traffic should
not inflate the BROADCAST message rate used to measure network load during
file transfers.

**Requirement — TX/RX Tab:**
- `messageProtocol` is already parsed. Add protocol breakdown to the TX/RX
  tab: two lanes — **BROADCAST** and **PRIVATE** (UNICAST normalized to PRIVATE).
  Show message counts, delivery rates, and message type breakdowns per lane.
- Sent and received counts shown per lane independently.
- Do not aggregate PRIVATE/UNICAST delivery rates into BROADCAST — they are
  different failure modes with different expected outcomes.
- Display as `PRIVATE / UNICAST` label in the UI to acknowledge both values
  map to the same lane.

**Requirement — File Transfer Section:**
- Add a protocol filter (BROADCAST / PRIVATE / All) to the file transfer
  section of the ATAK tab.
- Delivery rate, partial receive rate, and open segment counts computed
  per protocol independently.
- Flag when all PRIVATE fileTransfers fail — as seen with gt_Sassy_B_Net —
  as this pattern suggests a contact resolution or addressing issue rather
  than an RF problem.

**Requirement — Congestion Analysis:**
- When computing non-file-transfer network traffic during a transfer window,
  break down the count by protocol: BROADCAST PLI, BROADCAST other,
  PRIVATE messages.
- PRIVATE traffic contributes to total network load but should be shown
  as a separate component so QA engineers can distinguish fronthaul
  BROADCAST flooding (Poseidon pattern) from PRIVATE background traffic.
- Rate/min metric should show both total and BROADCAST-only rates since
  PRIVATE traffic has different propagation characteristics.

**Status:** ⏳ Pending

---

### P3 — Cross-Device Delivery Matrix (MEDIUM)

**Finding:** logId is the definitive join key for correlating delivery outcomes
across device logs. When multiple ATAK logs from the same session are loaded,
the parser has all the data needed to automatically compute a cross-device
delivery matrix. This is currently done manually in analysis.

**Requirement:** When 2+ ATAK logs are loaded simultaneously, compute and
display a transfer delivery matrix in the ATAK tab:
- Rows: unique sender logIds with `SUCCESS` status
- Columns: each loaded device
- Cells: `FULLY_RECEIVED`, `PARTIALLY_RECEIVED`, or `—` (no record)
- Include: hop count and RSSI in the cell tooltip on hover

**Status:** ⏳ Pending

---

### P4 — Relay Copy / Retransmission Flag (MEDIUM)

**Finding:** GATOR's log contains file transfer records with segment counts
matching official transfers but different logIds — probable relay copies
generated when intermediate mesh nodes re-initiated the transfer. The parser
currently has no way to distinguish these from unrelated transfers.

**Requirement:** When multiple ATAK logs are loaded, flag file transfer records
where:
1. The segment count matches a known sender `SUCCESS` transfer
2. The logId does NOT match the sender's logId
3. The timestamp falls within the known transfer window

Flag these as `probable_relay_copy: true` in the parsed output and surface
them distinctly in the UI — not as failed official transfers, but as evidence
the mesh was attempting to route copies to the receiver.

**Status:** ⏳ Pending

---

### P5 — Battery Critical Threshold (LOW)

**Finding:** Four devices hit below 10% battery (KOPEK 3%, CL_B 5%, BIRD 8%,
FONZ-B 9%). The health score battery dimension currently flags below 30% as
failing with no distinction between 29% (low) and 3% (critical).

**Requirement:** Add a second battery threshold at 10%:
- `min_battery > 30%` → PASS
- `10% ≤ min_battery ≤ 30%` → FAIL (existing behavior, yellow in UI)
- `min_battery < 10%` → CRITICAL (new, distinct red indicator in UI)

**Status:** ⏳ Pending

---

### P6 — KNOT Clock Skew Investigation (LOW — data quality)

**Finding:** KNOT's log shows T4 received at 08:39 MNT and T6 received at
09:51 MNT — both before those transfers started (10:13 and 11:21 MNT
respectively per FUJIN's log). This is either significant clock skew or a
timezone offset in KNOT's device clock.

**Requirement:** Investigate KNOT's `timestampInMillis` values relative to
other devices in the same session. If clock skew is confirmed, document as a
data limitation and consider adding a per-device clock offset indicator to
the Sessions tab when a device's timestamps are inconsistent with the session
window established by other devices.

**Status:** ⏳ Investigated 2026-06-15 — confirmed **host-clock skew**, pending QA resolution of the GID conflict and which clock was correct.

**Investigation finding (2026-06-15, `log-analyst` on `diagnostic_KNOT_90296226464906_2026-06-04 16_42_33.829.log`):**
- KNOT's own clock is internally clean: block timestamps are monotonic genuine UTC over 2026-06-04 12:15→20:42 (~8.5 h); no jumps or resets (only sub-second health-poll reordering).
- Against the mesh, `timestampInMillis − messageTimestampInMillis` (i.e. `deliveryTimeInMillis`) is a **constant ≈ −7232 s (−2 h 0 m 32 s)** — KNOT receives ~2 h *before* senders sent. The offset is **uniform across all 50 senders** (per-sender medians within a ~10 s band) and **flat across hop counts** (hop 1→8 varies only ~4 s), so it is one wrong clock, not 50 independent skews or relay latency. It does not drift over the 8.5 h session.
- **Not delivery lag:** `storedMessages` never exceeds 3 (0 in 465 of 507 health samples) — no buffer build-up to drain, so the offset cannot be buffering. Conclusion: **genuine host-clock skew** on KNOT's Android phone (magnitude ~2 h suggests a timezone/NTP misconfiguration; the +32 s argues for a clock set wrong rather than a clean tz label).
- **Limitation:** KNOT's log alone proves only that KNOT differs from all peers by a fixed offset — not that KNOT (vs. the rest of the mesh) holds the wrong time. Confirming which side is correct needs a correlated peer log from the same window.
- **Format note:** despite the `diagnostic_` filename, this log is **ATAK format** (`atakVersion` present → `_detect_format` routes to `parser/atak.py`). The `diagnostic_` prefix is a filename convention, not a format indicator.

**GID conflict (surface until QA resolves):** this log's own identity fields say GID `90296226464906` = **KNOT** (serial `PNE234200704`); a prior 2026-06-12 web-session analysis (see `session_summary.md`) attributed the *same* GID to **HOTLIPS** for the same 2026-06-04 event, and in this log HOTLIPS is a different originator (GID `90389599969003`). Likely a mislabel or callsign reassignment, not a true GID collision. Matters because the earlier `storedMessages` buffer-saturation finding was attributed to "HOTLIPS GID 90296226464906" — but that GID is KNOT here, and KNOT shows **no** buffer saturation (max 3).

---

### P7 — Poseidon Log Format (LOW — new format)

**Finding:** Poseidon (goTenna SmartEdge fronthaul bridge) produces 4 distinct
log formats across 7 files. The TAK server connectivity failure pattern
(`curl code: 1 - Unsupported protocol`) and COMMANDHANDLER failure counts
are high-value QA signals for identifying fronthaul configuration issues.
The Poseidon TAK server URL misconfiguration on 2026-06-02 caused incorrect
callsign fronthauling throughout the 2026-06-04 field session.

**Log formats to implement (in priority order):**
1. CoreApp Google glog (`[IWEF]yyyymmdd hh:mm:ss.uuuuuu tid file:line] msg`) — most structured, highest value
2. radioService Spring Boot + SDK — mixed format, goTenna Radio SDK interface
3. Mosquitto broker — Unix epoch timestamps, MQTT event stream
4. GPS NMEA — device-dependent, lowest priority

**Status:** ⏳ Deferred — analysis report available at
`docs/poseidon_analysis_2026-06-02.md`

---

> **Note:** An additional requirement (undocumented transfer warning) was
> considered but removed. The two unreported transfers found in FUJIN's log
> (09:32–09:46 and 09:48–09:59 MNT, 150 and 122 segments) were likely a
> tester warming up before the official session — not a parser issue requiring
> detection. No warning heuristic is warranted.

---

## deviceDisconnected — Serial Number Omission and Attribution Assumption

### Observation (2026-06-04 FUJIN log)

The `deviceDisconnected` event in ATAK plugin diagnostic logs does **not**
include the serial number of the radio that disconnected. The `serialNumber`
field in the event payload is always empty on disconnect events.

**Example from FUJIN log:**
```
18:28:34 UTC  deviceDisconnected  serialNumber=""   connectionType="BLE"
18:48:48 UTC  deviceConnected     serialNumber="PNE234200715"  connectionType="BLE"
```

This means the log alone cannot definitively confirm which radio disconnected
at any given moment. Multiple `deviceConnected` records for different serials
without intervening named disconnects could indicate either:
- Sequential radio swaps (one disconnects, another connects), or
- Simultaneous multi-radio connections (a genuine bug)

### Assumption — LIFO Attribution

**When a `deviceDisconnected` event fires, it is attributed to the most
recently connected serial (last in, first out).**

Under this assumption, the FUJIN 2026-06-04 session shows sequential radio
swaps — one radio at a time — rather than simultaneous connections:

```
12:28:56  deviceConnected   PNE232700054  → active: [PNE232700054]
18:48:34  deviceDisconnected (no serial)  → assume PNE232700054 disconnected
18:48:48  deviceConnected   PNE234200715  → active: [PNE234200715]
18:49:19  deviceDisconnected (no serial)  → assume PNE234200715 disconnected
18:49:48  deviceConnected   PNE241500432  → active: [PNE241500432]
```

This is consistent with expected field behavior — one goTenna radio connected
to the ATAK app at a time, swapped between transfers.

### Documentation Requirements

1. **`deviceDisconnected` serial omission is a known log format limitation.**
   It must be documented in `log-field-definitions.md` under the event field
   definitions. The parser must not attempt to attribute a serial number to
   disconnect events — they should be recorded as anonymous disconnects.

2. **The LIFO attribution assumption must be noted wherever multi-serial
   analysis is presented** — battery chart DataNote, health score, and any
   future cross-log correlation that relies on connection state.

3. **This assumption has not been validated with the dev team.** If the
   `deviceDisconnected` event is supposed to carry a serial number and its
   absence is a logging bug, the assumption is unnecessary. If serial omission
   is intentional by design, the assumption is the correct interpretation.

**Status:** ⏳ Pending dev team confirmation of whether `deviceDisconnected`
serial omission is intentional or a logging bug.

### Impact on Battery Chart

The battery % over time chart shows one line per serial number. Under the
LIFO assumption, each line segment represents one connected radio during its
active window — not simultaneous connections. The DataNote on the chart
reflects this assumption explicitly.
