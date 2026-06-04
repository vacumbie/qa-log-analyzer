# Log Analysis Report — Enhanced ATAK Diagnostic Logs (7 devices)
## Session: 2026-06-03 — File Transfer / GRIP Focus

---

## Format

- **Detected format:** `atak`
- **Environment:** Field session — real devices, real RF mesh
- **Platform:** Android (all devices `ANDROID-*` UUIDs)
- **ATAK Plugin version:** `3.0.0 (3103456d) - [5.6.0]` (where present)
- **ATAK version:** `5.6.0.18`
- **Device model:** Samsung SM-G781U1 (Android API 33)

---

## Device Inventory

| Callsign | Serial | GID | Firmware | Role in transfers |
|----------|--------|-----|----------|-------------------|
| BIRD | PNE234200715 | 90495447405391 | 3.2.11 | Receiver |
| DARE | PNE241500442 | 90456542927689 | 3.2.10 | Receiver |
| FUJIN | PNE234900079 + PNE233000568 | 90310306113271 | 3.2.11 + 3.2.10 | **Sender** (all 4 transfers) |
| HOTLIPS | PNE234200704 + PNE241600027 | 90296226464906 | 3.2.11 + 3.2.10 | Receiver |
| INDIA | PNE234100316 + PNE234100456 | 90201001227679 | 3.2.10 + 3.2.11 | Receiver |
| KNOT | PNE234500229 | 90039086012911 | 3.2.10 | Receiver |
| KOPEK | PNE241500446 | 90041986626169 | 3.2.10 | Receiver |

**Three devices (FUJIN, HOTLIPS, INDIA) show multiple serials + "Unknown"** — see Multi-Radio section below.

---

## Record Type Inventory (all 7 logs combined)

| Record Type | Count | Currently Parsed? | Notes |
|------------|-------|------------------|-------|
| `sdkError` | 56,179 | ❌ No | **SDK Logging 2.0 format — dominant record type** |
| `message` | 16,830 | ✅ Yes (AtakMessage) | PLI, chat, fileTransfer, mapObject |
| `deviceHealth` | 4,077 | ✅ Yes (AtakDeviceHealth) | |
| `event` | 87 | ✅ Partial | Some event types parsed, new ones found |
| `appLaunch` | 11 | ✅ Yes (AtakAppInfo) | |

**Critical finding:** `sdkError` records (56,179) are the single most common record type
in these logs — outnumbering `message` records 3:1 — and are currently completely unparsed.
They follow the SDK Logging 2.0 JSON schema proposed in the RSDK PDF. This is not an
error condition — it is the new structured log format being used in production.

---

## Record Type Details

### 1. `message` — AtakMessage (currently parsed ✅)

**Message types observed:**

| type | Count | Notes |
|------|-------|-------|
| `pli` | dominant | Parsed ✅ |
| `textChat` | present | Parsed ✅ |
| `fileTransfer` | 28 total | Parsed ✅ — key focus of this session |
| `mapObject` | present | Parsed ✅ |

**New sub-fields in `message` object:**
- `fileTransfer`: `fileName` — the actual filename (e.g. `goTenna_ATAK_1780506877104.jpg`). When transfer is incomplete, `fileName` = `"UNKNOWN"`. **Not currently parsed.**
- `mapObject`: `objectType` — only `PIN` observed. **Not currently parsed.**
- `textChat`: no sub-fields beyond `type` in these samples.

**New top-level fields on message records:**

| Field | Type | Sample | Currently Parsed? | Notes |
|-------|------|--------|-------------------|-------|
| `loggingUserLocation` | object | `{lat, long, alt}` | ❌ No | Logging device's GPS at time of message |
| `transmittedLocation` | object | `{lat, long, alt}` | ❌ No | Location embedded in the message being logged |
| `originatorCallsign` | string | `"FUJIN"` | ❌ No | Originator (may differ from sender in relayed msgs) |
| `originatorUUID` | string | `"ANDROID-05da679508273f58"` | ❌ No | Originator UUID |

**Note on `loggingUserLocation` vs `transmittedLocation`:** Every message record
has `loggingUserLocation` present. Some records have `transmittedLocation` (the
sender's location embedded in the message payload), some do not (e.g. textChat).
These are two distinct location fields — the logger's own position vs the
transmitted position. Both are currently unparsed.

**Delivery status — new value:**

| Status | Observed on | Meaning |
|--------|-------------|---------|
| `SUCCESS` | FUJIN (sender, fileTransfer only) | Sender-side confirmation of full delivery with ACK. Distinct from `DELIVERED`. |

Previously documented statuses: `FULLY_RECEIVED`, `SENT`, `DELIVERED`, `PARTIALLY_RECEIVED`.
`SUCCESS` is new — appears only on the sender side for fileTransfer records when
the full delivery was acknowledged. **Not currently handled by the parser.**

---

### 2. `deviceHealth` — AtakDeviceHealth (currently parsed ✅)

All currently documented fields confirmed present. No new fields in deviceHealth records.

**Multi-radio observation:** Three devices show `serialNumber: "Unknown"` records
alongside known serials. This occurs during radio switching or BLE reconnection —
the device health poll fires before the serial is resolved. The parser already
handles this via the `serial_number` field accepting any string. Worth documenting
explicitly as expected behavior.

**Firmware versions observed:** `3.2.10` and `3.2.11` (both in field simultaneously).
No new firmware-version-specific field differences detected.

---

### 3. `event` — AtakEvent (partially parsed ✅)

All previously documented event types confirmed, plus **two new ones:**

| event.type | Sample | Currently Parsed? |
|-----------|--------|------------------|
| `deviceConnected` | `{type, connectionType, serialNumber}` | ✅ Yes |
| `deviceDisconnected` | `{type, connectionType, location: {lat, long, alt}}` | ✅ Yes |
| `powerLevelUpdated` | `{type, power: 1.0}` | ✅ Yes |
| `pliSettingUpdated` | `{type, isDistance, interval, isAutoSend}` | ✅ Yes |
| `frequencyUpdated` | `{type, power, bandwidth, channels: [{frequency, isControlChannel}]}` | ✅ Yes |
| **`firmwareUpdate`** | `{type, updateStatus: "STARTED", updateTimeInMillis}` | ❌ **New — not parsed** |

**`firmwareUpdate` event** — observed on HOTLIPS. Fields: `updateStatus` (`"STARTED"` observed),
`updateTimeInMillis`. This is a significant QA event — firmware update during a session
could explain degraded behavior.

**`deviceDisconnected` new field:** `location` — `{lat, long, alt}` of the device at disconnect
time. Not in the current `AtakEvent` dataclass.

---

### 4. `appLaunch` — AtakAppInfo (currently parsed ✅)

All fields confirmed. Present in DARE and FUJIN logs. Not all logs have this record
(devices that were already running when logging started won't show a launch record).

---

### 5. `sdkError` — **NEW — SDK Logging 2.0 format** ❌ Not parsed

This is the most significant finding. These records follow the SDK Logging 2.0 JSON
schema described in the RSDK PDF. They are **not error-only records** — the name
`sdkError` is the parser classification I gave them based on the `tags` field
containing `"ERROR"`, but they are better described as **structured SDK log events**.

**Record structure:**
```json
{
  "id": "0cfc7a10-ca5f-4c8b-a629-2ab01d116f9e",
  "timestamp": "2026-06-03T22:15:22.082133Z",
  "tags": ["ERROR", "BLE"],
  "message": {
    "deviceState": {
      "platformType": "ANDROID",
      "connectionType": "BLE",
      "serialNumber": "PNE234200715",
      "address": "FB:6C:DB:3B:3A:9A",
      "connectionState": "CONNECTING",
      "personalGid": 90495447405391,
      "batteryLevel": 68,
      "firmwareVersion": "3.2.11",
      "radioType": "PRO_X_2",
      "mcuuuid": "0028ffffffffffff4e4573952013002d",
      "endorsements": "PREMIUM"
    },
    "event": {
      "logEventId": "1aadc4f2-4a96-4662-88ae-79139b994ea6",
      "additionalInfo": "Gatt write back off reached skipping write"
    }
  }
}
```

**Key fields:**

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID string | Unique record ID |
| `timestamp` | ISO 8601 UTC | High-precision timestamp (microseconds) — more precise than `timestampInMillis` |
| `tags` | string array | `["ERROR", "BLE"]`, `["ERROR", "RADIO"]` observed — indicates severity/category |
| `message.deviceState.platformType` | string | `"ANDROID"` |
| `message.deviceState.connectionType` | string | `"BLE"` |
| `message.deviceState.serialNumber` | string | goTenna serial |
| `message.deviceState.address` | string | BLE MAC address |
| `message.deviceState.connectionState` | string | `"CONNECTING"`, `"DISCONNECTED"` observed |
| `message.deviceState.personalGid` | integer | Full 64-bit GID |
| `message.deviceState.batteryLevel` | integer | Battery % at time of event |
| `message.deviceState.firmwareVersion` | string | |
| `message.deviceState.radioType` | string | `"PRO_X_2"` — **new field not in deviceHealth** |
| `message.deviceState.mcuuuid` | string | MCU UUID |
| `message.deviceState.endorsements` | string | `"PREMIUM"` |
| `message.event.logEventId` | UUID string | Event-level unique ID |
| `message.event.additionalInfo` | string | Human-readable error description |

**`radioType` field** — `"PRO_X_2"` — this is new and not present anywhere else in the
log format. Worth tracking for device identification.

**Tags observed:** `["ERROR", "BLE"]` and `["ERROR", "RADIO"]`. These are the only
tags seen in this sample but the SDK Logging 2.0 schema supports others.

**DATA LIMITATION:** At 56,179 records across 7 logs, these are extremely high-volume.
Whether this volume is normal or represents a real BLE connectivity issue during the
field session is unknown without baseline data. Do not parse individual records into
memory — aggregate counts and surface `additionalInfo` values as a summary.

---

## File Transfer Analysis (GRIP focus)

### Summary

| Callsign | Role | Transfers | Fully Received | Partially Received | Segment counts |
|----------|------|-----------|---------------|-------------------|----------------|
| FUJIN | Sender | 4 | 4 (`SUCCESS`) | 0 | 352, 368, 376, 376 |
| BIRD | Receiver | 4 | 2 | 2 | 376, 376 |
| HOTLIPS | Receiver | 7 | 4 | 3 | 352, 352, 376, 376, 1404, 1404 + more |
| INDIA | Receiver | 5 | 2 | 3 | 352, 1404, 368 + more |
| KOPEK | Receiver | 6 | 2 | 4 | 368, 368, 376, 376 + more |
| DARE | Receiver | 1 | 0 | 1 | 368 |
| KNOT | Receiver | 1 | 0 | 1 | 368 |

### Key file transfer findings

**1. `deliveryStatus: "SUCCESS"` is sender-side only**
FUJIN (sender) shows `SUCCESS` for all 4 transfers with real `deliveryTimeInMillis`
values (~1.9–2.1 seconds for 352–376 segment files). Receivers show `FULLY_RECEIVED`
or `PARTIALLY_RECEIVED` with `deliveryTimeInMillis: 0`. This confirms:
- `SUCCESS` = sender received final ACK (GRIP confirmed delivery)
- `FULLY_RECEIVED` = receiver assembled all segments
- `deliveryTimeInMillis` is only meaningful on the sender side (isSender=true + SUCCESS)
- Receiver-side `deliveryTimeInMillis: 0` is a placeholder, not a real value

**2. `numberOfOpenSegments: -99` is a sentinel**
Appears on `PARTIALLY_RECEIVED` fileTransfer records at DARE, INDIA, KNOT, KOPEK.
Meaning: the transfer timed out or was cancelled before the segment count could be
determined — the receiver never assembled enough to know how many were missing.
Distinct from positive values (e.g. `open=183`) which mean segments were received
but specific ones are missing. **Currently stored as-is — should be treated as
`None`/unknown in UI display rather than a literal -99.**

**3. `fileName` in fileTransfer**
Fully received transfers show the actual filename (`goTenna_ATAK_<timestamp>.jpg`).
Partially received transfers show `"UNKNOWN"`. This is the file being transferred
via GRIP over the mesh. **Not currently parsed.**

**4. HOTLIPS has a very large transfer: 1404 segments**
Two records with `segmentCount: 1404` — roughly 4x the size of the other transfers.
One `FULLY_RECEIVED`, one `PARTIALLY_RECEIVED`. The large transfer had higher retry
rates at some receivers. This is the largest GRIP file transfer observed in the dataset.

**5. Cross-log transfer correlation via `logId`**
The same `logId` appears across multiple device logs for the same transfer. For example:
- `logId=1835935479` (FUJIN=sender/SUCCESS, BIRD=FULLY_RECEIVED, HOTLIPS=FULLY_RECEIVED, KOPEK=FULLY_RECEIVED)
- `logId=-1315985673` (BIRD=PARTIALLY_RECEIVED, open=5)
This enables cross-device delivery analysis — the parser could correlate sender success
with receiver outcomes using `logId` as the join key.

---

## New Fields — Recommended Parser Actions

### High priority

| Field | Location | Action |
|-------|----------|--------|
| `sdkError` records | New record type | Add `AtakSdkError` dataclass; parse `id`, `timestamp`, `tags`, `message.deviceState.*`, `message.event.additionalInfo`; aggregate by tag type |
| `fileName` | `message.fileName` on fileTransfer | Add to `AtakMessage`; surface in UI for completed transfers |
| `deliveryStatus: "SUCCESS"` | message.deliveryStatus | Add to parser's delivery status handling; treat as sender-confirmed delivery |
| `numberOfOpenSegments: -99` | message.numberOfOpenSegments | Treat as sentinel `None` in UI display |
| `loggingUserLocation` | message top-level | Add to `AtakMessage`; `{lat, long, alt}` |
| `transmittedLocation` | message top-level | Add to `AtakMessage`; `{lat, long, alt}` — present on PLI/fileTransfer, absent on textChat |

### Medium priority

| Field | Location | Action |
|-------|----------|--------|
| `firmwareUpdate` event | event.type | Add to `AtakEvent` handling; parse `updateStatus` and `updateTimeInMillis` |
| `deviceDisconnected.location` | event.location | Add `location` to `AtakEvent` for disconnect events |
| `objectType` | `message.objectType` on mapObject | Add to `AtakMessage` |
| `radioType` | `sdkError.message.deviceState.radioType` | Capture `"PRO_X_2"` etc. for device classification |
| `originatorCallsign` / `originatorUUID` | message top-level | Already in AtakMessage but verify parser populates them |

---

## Nomenclature Check — `docs/log-field-definitions.md`

Comparing raw JSON field names against current documentation:

| Raw JSON name | Current doc name | Correct? | Notes |
|---------------|-----------------|----------|-------|
| `logId` | `log_id` | ✅ | |
| `timestampInMillis` | `timestamp` | ✅ | Converted from ms |
| `messageTimestampInMillis` | `message_timestamp` | ✅ | |
| `isSender` | `is_sender` | ✅ | |
| `senderGid` | `sender_gid` | ✅ | |
| `deliveryStatus` | `delivery_status` | ✅ | |
| `segmentCount` | `segment_count` | ✅ | |
| `numberOfOpenSegments` | `open_segments` | ✅ | |
| `retryCount` | `retry_count` | ✅ | |
| `deliveryTimeInMillis` | `delivery_time_ms` | ✅ | |
| `messageProtocol` | `message_protocol` | ✅ | |
| `hopCount` | `hop_count` | ✅ | |
| `rssi` | `rssi` | ✅ | |
| `receiverGid` | `receiver_gid` | ✅ | |
| `senderCallsign` | `sender_callsign` | ✅ | Note: always empty on sent messages — documented |
| `powerAmpTemperature` | `pa_temp_c` | ✅ | Renamed correctly |
| `systemTemperature` | `system_temp_c` | ✅ | |
| `transmitPowerDifferential` | `transmit_power_differential` | ✅ | |
| `loggingUserLocation` | — | ❌ **Missing** | Not in docs — new field |
| `transmittedLocation` | — | ❌ **Missing** | Not in docs — new field |
| `originatorCallsign` | `originator_callsign` | ⚠️ **Verify** | In AtakMessage but confirm parser populates it |
| `originatorUUID` | — | ❌ **Missing** | Not in docs |
| `fileName` | — | ❌ **Missing** | Not in docs — new field |
| `objectType` | — | ❌ **Missing** | Not in docs — new field |
| `deliveryStatus: SUCCESS` | — | ❌ **Missing** | New value not in docs |
| `event.firmwareUpdate` | — | ❌ **Missing** | New event type not in docs |
| `event.deviceDisconnected.location` | — | ❌ **Missing** | New sub-field not in docs |
| `sdkError` record type | — | ❌ **Missing** | Entire new record type not documented |

**Overall nomenclature assessment:** Existing field names are correctly documented.
The gaps are entirely in new fields introduced in this enhanced log format.

---

## Data Limitations to Surface

- `numberOfOpenSegments: -99` is a sentinel value meaning the transfer was
  cancelled before segment count was known — treat as `None` in UI, not -99
- `deliveryTimeInMillis: 0` on receiver-side fileTransfer records is a placeholder,
  not a real delivery time — only meaningful when `isSender=true` and `deliveryStatus=SUCCESS`
- `serialNumber: "Unknown"` in deviceHealth records is expected behavior during
  BLE reconnection — not a parser error
- SDK Logging 2.0 / `sdkError` records: volume of 56,179 across 7 logs is very high;
  baseline for healthy sessions is unknown — flag as informational until baseline is established
