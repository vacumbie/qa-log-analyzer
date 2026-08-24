# Log Field Definitions

> **Source of truth for every log field used in parsing and data point generation.**
> Each entry defines what the field means in the raw log, how it is parsed, what it becomes
> in the data model, and any known accuracy limitations or caveats.
>
> Last updated: 2026-08-24

---

## Table of Contents

- [Format 1: goTenna Pro+ Diagnostic Log](#format-1-gotenna-pro-diagnostic-log)
- [Format 2: RSDK iOS/Android SDK Log](#format-2-rsdk-iosandroid-sdk-log)
  - [GRIP Message Fields](#grip-message-fields-grip_sender--grip_receiver)
  - [GRIP Transfer Lifecycle](#grip-transfer-lifecycle)
- [Format 3: Android ATAK Plug-in Log](#format-3-android-atak-plug-in-log)
- [Format 4: Relay Firmware (UART/USB Debug) Log](#format-4-relay-firmware-uartusb-debug-log)
- [Format 5: TAK Server CoT Event Stream](#format-5-tak-server-cot-event-stream)
- [Derived / Computed Fields](#derived--computed-fields)
- [Cross-Format Notes](#cross-format-notes)

---

## Format 1: goTenna Pro+ Diagnostic Log

**File type:** `.txt`
**Platform:** iOS only
**Structure:** Blank-line-delimited text blocks. Each block has a timestamp on line 1, a record type on line 2, then `key: value` pairs.

---

### Block: `Device & Application Info`

Written once per log file at app launch.

| Raw Field | Parsed As | Model Field | Notes |
|-----------|-----------|-------------|-------|
| `app version` | string | `device.app_version` | e.g. `2.2.1` |
| `build number` | string | `device.build_number` | e.g. `15` |
| `log version` | string | `device.log_version` | e.g. `v1` |
| `device` | string | `device.device_model` | iOS device model, e.g. `iPhone 15` |
| *(inferred)* | `"ios"` | `device.platform` | Diagnostic format is iOS-only |

> ⚠️ **One block per file.** If this block is missing, device identity will be empty.

---

### Block: `System Information`

Written approximately every 5 minutes while the app is active and in the foreground.

| Raw Field | Parsed As | Model Field | Notes |
|-----------|-----------|-------------|-------|
| `BATTERY LEVEL` | integer | `system_sample.battery_pct` | Percent (0–100). Parsed as integer only if purely numeric. |
| `POWER AMP TEMP` | integer | `system_sample.pa_temp_c` | **Celsius.** Must be converted to °F for display: `°F = (°C × 9/5) + 32` |
| `FIRMWARE VERSION` | string | `device.radio_firmware` | Captured from first System Information block only |
| `SERIAL NUMBER` | string | `device.radio_serial` | Radio serial number, e.g. `PNE234300142`. Present in every System Information block; captured from first occurrence. |
| `SYSTEM TEMP` | integer | *(not parsed)* | Celsius. Secondary temperature sensor (board/system), distinct from PA amp temp. Not currently extracted. |
| `TRANSMIT POWER DIFF` | integer | *(not parsed)* | Observed range 5–11. Meaning not fully documented. Not currently extracted. |
| `BATTERY CHARGE STATE` | boolean string | *(not parsed)* | `true` / `false`. Not currently extracted. |
| `HW VERSION` | integer | *(not parsed)* | Radio hardware revision, e.g. `9`. Not currently extracted. |
| `LED ENABLED` | boolean string | *(not parsed)* | `true` / `false`. Not currently extracted. |
| `BOOT VERSION` | integer | *(not parsed)* | Bootloader version, e.g. `20`. Not currently extracted. |
| `STORED MESSAGES` | *(not parsed)* | — | Present in log but not currently extracted. |
| Block timestamp | string | `system_sample.timestamp` | Wall clock time at the moment of polling |

> ⚠️ **Polling gap = app not active.** A gap of >5 min between System Information blocks means the app was closed, backgrounded, or the device was asleep. This is the primary crash/interruption proxy.
>
> ⚠️ **Temperature is Celsius in the log.** The raw value (e.g. `33`) means 33°C = 91°F. Never display the raw value directly.
>
> ⚠️ **Firmware 3.1.11 vs 3.2.10 — missing identity fields in Received Message blocks.** Devices on firmware 3.1.11 omit `receiver callsign`, `receiver gid`, `originator callsign`, `originator gid`, and `receiver location` from every `Received Message` block. Hop count, RSSI, timestamps, and PLI intervals are still present. Confirmed on serial `PNE235200117` (firmware 3.1.11, Apr 27 test) — all 150 received message blocks are missing identity fields. Devices on 3.2.10 include these fields normally. The parser must not fail on their absence.

---

### Block: `Received Message`

One block per RF message received over the mesh. This is the core data source for hop count, RSSI, PLI intervals, and network topology.

| Raw Field | Parsed As | Model Field | Notes |
|-----------|-----------|-------------|-------|
| `id` | string | `message.message_id` | Unique message identifier |
| `data type` | string | `message.data_type` | `broadcast` or `1to1` (private) |
| `message type` | string | `message.message_type` | `location` (PLI) or `text` (chat/map) |
| `hop count` | integer | `message.hop_count` | Number of RF hops from originator to this receiver. **Genuine RF routing data.** |
| `rssi` | integer | `message.rssi_raw` | **Unsigned byte (137–237).** Real dBm = `rssi_raw − 256` (range −119 to −19 dBm). Never display raw value. |
| `frequency set` | string | `message.frequency_set` | Name of the frequency set used, e.g. `Primary` |
| `frames used` | integer | `message.frames_used` | Number of RF frames consumed by this message |
| `originator callsign` | string | `message.originator_callsign` | Callsign of the node that originated the message |
| `originator gid` | string | `message.originator_gid` | GID of the originating node — used for network topology |
| `originator location` | string | `message.originator_location` | Lat/lon at time of send, e.g. `25.0808, 121.5591` |
| `originator pli interval` | string | `message.originator_pli_interval` | PLI broadcast rate of the originator, e.g. `300 seconds` |
| `originator timestamp` | string | `message.originator_timestamp` | When the originator sent the message |
| `receiver callsign` | string | `message.receiver_callsign` | Callsign of the logging device (this device) |
| `receiver gid` | string | `message.receiver_gid` | GID of the logging device — used for device identity |
| `receiver location` | string | `message.receiver_location` | Lat/lon of receiver at time of receipt |
| `receiver pli interval` | string | `message.receiver_pli_interval` | PLI broadcast rate of the logging device |
| `receiver timestamp` | string | `message.timestamp` | **Primary timestamp for this message** — when this device received it |

> ⚠️ **RSSI is an unsigned byte.** The value `147` in the log means −109 dBm. Always apply `value − 256` before displaying.
>
> ⚠️ **PLI sent = 0 in message counts.** Outbound PLI is not counted in the `pli messages sent` counter. The device's own PLI rate is confirmed via the `receiver pli interval` field on inbound messages, not from a sent counter.
>
> ⚠️ **This block records received messages only.** There is no equivalent block for sent messages. Sent chat/map counts come from `Message Count Details` (cumulative counter), not individual records.
>
> ℹ️ **Two timestamps.** The `receiver timestamp` row above maps to `message.timestamp` (the primary timestamp). `ReceivedMessage` also carries a separate `receiver_timestamp` field and `receiver_location`; both are populated by the diagnostic parser and serialized by `_result_to_dict()`. The UI prefers `receiver_timestamp` for PLI-interval timing and falls back to `originator_timestamp` then `timestamp`.

---

### Block: `Message Count Details`

Written approximately every 5 minutes alongside System Information. Cumulative counters — values only increase.

| Raw Field | Parsed As | Model Field | Notes |
|-----------|-----------|-------------|-------|
| `pli messages sent` | integer | `snapshot.pli_sent` | **Always 0.** Diagnostic format does not count outbound PLI in this field. |
| `pli messages received` | integer | `snapshot.pli_received` | Cumulative PLI messages received since app launch |
| `chat and map messages sent` | integer | `snapshot.chat_sent` | Cumulative chat + map messages sent since app launch |
| `chat and map messages received` | integer | `snapshot.chat_received` | Cumulative chat + map messages received since app launch |

> ⚠️ **Cumulative, not per-interval.** The value at time T is the total since app launch, not since the last snapshot. To get per-interval counts, subtract consecutive snapshots.
>
> ⚠️ **`pli_sent` is always 0** in this format. Do not use this field for sent PLI counts.
>
> ⚠️ **Final snapshot is the most reliable.** The last `Message Count Details` block in the file represents the total for the entire session.

---

### Block: `Frequency Set`

Describes the radio frequency configuration active at the time of logging.

| Raw Field | Parsed As | Model Field | Notes |
|-----------|-----------|-------------|-------|
| `name` | string | `freq_set.name` | e.g. `Primary` |
| `power level` | string | `freq_set.power_watts` | e.g. `5.0 watts` |
| `bandwidth` | string | `freq_set.bandwidth_khz` | e.g. `11.8 kHz` |
| `control channels` | string | `freq_set.control_channels` | MHz list, e.g. `[471.265, 478.265] Mhz` |
| `data channels` | string | `freq_set.data_channels` | MHz list, e.g. `[475.265, 476.265, 479.265] Mhz` |

---

### Block: `total number of messages received: N` (Radio Stat Snapshot)

Written when the app queries radio lifetime statistics. The block type line itself encodes one value.

| Raw Field | Parsed As | Model Field | Notes |
|-----------|-----------|-------------|-------|
| Block type line | integer | `stat.lifetime_msgs_received` | All-time messages received by this radio firmware, never reset |
| `total uptime in one tenth of hours` | integer | `stat.lifetime_uptime_tenths_hrs` | Divide by 10 for hours. All-time, never reset. |
| `total number of messages orginated` | integer | `stat.lifetime_msgs_originated` | Note: typo in raw log (`orginated`) — parsed as-is |
| `total number of messages relayed` | integer | `stat.lifetime_msgs_relayed` | All-time relay count |
| `total number of messages rejected` | integer | `stat.lifetime_msgs_rejected` | All-time rejection count |
| `total UHF transmit time in seconds at 5.0W` | integer | `stat.lifetime_uhf_tx_5w_sec` | All-time TX time at max power |
| `total UHF received time in seconds` | integer | `stat.lifetime_uhf_rx_sec` | All-time RX time |
| `number of commands errored` | integer | `stat.commands_errored` | All-time command errors |
| `number of events exceeding allowable temparature threshold` | integer | `stat.temp_threshold_events` | Note: typo in raw log (`temparature`) — parsed as-is |
| `average UHF RF RSSI, in dB` | integer | `stat.avg_uhf_rssi_db` | All-time average RSSI |
| `average UHF RF antenna quality, in dB` | integer | `stat.avg_uhf_ant_quality_db` | All-time average antenna quality |
| `average BLE RSSI` | integer | `stat.avg_ble_rssi` | All-time average BLE signal strength |
| `number of messages sent` | integer | `stat.session_msgs_sent` | **Session counter — resets on BLE re-pair. Use with caution.** |
| `number of messages received` | integer | `stat.session_msgs_received` | **Session counter — resets on BLE re-pair. Use with caution.** |
| `number of messages relayed` | integer | `stat.session_msgs_relayed` | **Session counter — resets on BLE re-pair.** |
| `number of messages rejected` | integer | `stat.session_msgs_rejected` | **Session counter — resets on BLE re-pair.** |

> ⚠️ **Lifetime vs session counters.** Fields prefixed `lifetime_` are all-time firmware counters that never reset. Fields prefixed `session_` reset when the radio is re-paired via BLE and should not be used for session-level analysis.
>
> ⚠️ **Two typos in raw log field names** are parsed verbatim: `orginated` and `temparature`.

---

### Block: `Tester Location`

> **Not parsed.** Location data from this block is present in the log but not currently extracted by the parser.

---

### Session Gap Detection (Diagnostic)

Gaps are detected by sorting all timestamps from `Received Message` and `System Information` blocks combined. Any gap > 30 minutes between consecutive timestamps is recorded as a `SessionGap`.

| Field | Definition |
|-------|------------|
| `session_start` | Earliest timestamp across all received messages and system samples |
| `session_end` | Latest timestamp across all received messages and system samples |
| `gap_minutes` | Duration of the gap in minutes (rounded to 1 decimal place) |

---

## Format 2: RSDK iOS/Android SDK Log

**File type:** `.txt`
**Platform:** iOS or Android (auto-detected from log content)
**Structure:** One log line per entry. Format: `TIMESTAMP LEVEL Device - SERIAL COMPONENT: message`

---

### Line Format

```
2026-03-03T15:16:13.515351Z DEBUG Device - PNE234100381 IosBleRadio: BLE reconnection failed...
```

| Segment | Parsed As | Notes |
|---------|-----------|-------|
| `TIMESTAMP` | ISO 8601 UTC with microseconds | Full year present — no inference needed |
| `LEVEL` | log level string | `DEBUG`, `INFO`, `WARN`, `ERROR` |
| `SERIAL` | `device.radio_serial` | Radio serial number, e.g. `PNE234100381` |
| `COMPONENT` | routing key | Used to route line to the correct handler |

---

### Component: `COMMANDHANDLER` — DeviceInfo lines

Lines containing `DeviceInfo(...)` provide periodic radio health data.

| Raw Field in DeviceInfo(...) | Parsed As | Model Field | Notes |
|-----------------------------|-----------|-------------|-------|
| `deviceSerial` | string | `device.radio_serial` | Captured from first occurrence |
| `firmwareVersion` | string | `device.radio_firmware` | e.g. `3.2.10` |
| `batteryLevel` | float | `system_sample.battery_pct` | Percent. Sentinel value `-1` = not yet valid on first connect — skipped. |
| `powerAmpTemperature` | integer | `system_sample.pa_temp_c` | **Celsius.** Sentinel value `-1` = not yet valid — skipped. Convert to °F for display. |
| `systemTemperature` | integer | *(not stored separately)* | Celsius. `0` on first connect = placeholder — skipped. |
| `reflectedPowerRatio` | integer | *(not stored)* | `255` = not yet valid sentinel. Real values observed on Android only. |
| `batteryCharging` | bool | *(not stored)* | Present but not currently extracted |
| `numberOfStoredMessage` | integer | *(not stored)* | Present but not currently extracted |
| `errorCode` | string | *(not stored)* | Contains `SystemErrorCodes(errorValue=N)` — not currently extracted |

> ⚠️ **Sentinel values must be skipped.** `batteryLevel=-1` and `powerAmpTemperature=-1` appear on first connect before valid readings are available. These are not real values.
>
> ⚠️ **PA Temperature regex bug (fixed).** The original parser used `powerAmpTemp` but the actual field is `powerAmpTemperature`. This was corrected — earlier versions of the parser silently dropped all temperature data from this format.
>
> ⚠️ **System samples are only emitted when both battery AND temperature are present** in the same `DeviceInfo` block. Partial readings are not stored.

---

### Component: `IosBleRadio` — BLE Reconnection Failures

**iOS only.** Lines matching `BLE reconnection failed, retrying in 2000ms`.

| Field | Parsed As | Model Field | Notes |
|-------|-----------|-------------|-------|
| Line timestamp | datetime | `ble_fail.timestamp` | UTC |
| `SERIAL` from line | string | `ble_fail.radio_serial` | Radio that failed to reconnect |
| `dt.hour` | integer | `ble_fail.hour` | Hour of day (0–23) for hourly bucketing |

> ⚠️ **iOS only.** Android BLE reconnection behavior differs and does not produce this specific log line.

---

### Component: `NACK` — Android NACK Events

**Android only.** Lines from the `NACK` component tag surface explicit retransmit failures.

| Pattern | Parsed As | Model Field | Notes |
|---------|-----------|-------------|-------|
| `missing segments [...] for msgId: N` | TxEvent | `tx_event.outcome = "nack"` | Segment retransmit request |
| `nack triggered for GoTennaTransportFrame(...messageId=N...)` | TxEvent | `tx_event.outcome = "nack"` | NACK for specific message |
| `SRC a nack has been received but doesn't match the pending outbound file, discarding.` | TxEvent | `tx_event.outcome = "nack"`, `message_id = ""` | Stale NACK — captured with empty message ID |

---

### Component: `GRIP_Receiver` — Unicast TX Outcomes (iOS and Android)

TX outcome lines appear on the `GRIP_Receiver` component on both platforms. There are no
`SendMessageResponse`-based outcome lines in the actual logs — that pattern was incorrect.

| Pattern | Parsed As | Model Field | Notes |
|---------|-----------|-------------|-------|
| `SRC: Final ACK received, message fully delivered` | TxEvent | `outcome = "final_ack"` | Unicast confirmed delivered. No message ID in this log line — `message_id` stored as empty string. |
| `SRC: Keep-alive ACK received. Segment ID: N msgId: N` | TxEvent | `outcome = "keepalive_ack"` | Mid-transfer ACK. `msgId` value stored as `message_id`. |

> ⚠️ **No timeout-outcome lines exist in the logs.** The line `"expected timeout of Xms"` (from `GRIP_SENDER`) is a send-start log, not a delivery failure. No `outcome = "timeout"` events will be produced by this parser.
>
> ⚠️ **NACKs are not surfaced on `GRIP_Receiver`.** They surface via the `NACK` component tag — see section below.

---


### GRIP Message Fields (`GRIP_SENDER` / `GRIP_Receiver`)

Parsed from structured `Outgoing message fields` and `Incoming message fields` log lines.
One `GripMessage` record per line. Incoming lines (GRIP_Receiver) include `hops` and `rssi`.

| Raw Field | Parsed As | Model Field | Notes |
|-----------|-----------|-------------|-------|
| `MsgType` | integer | `grip_message.msg_type` | `0` = private · `2` = broadcast |
| *(derived)* | string | `grip_message.msg_type_label` | `"private"` · `"broadcast"` · `"unknown(N)"` |
| `SRC` | signed integer | `grip_message.src_gid` | Hashed GID — signed 32-bit; not reversible to full GID |
| `DST` | signed integer | `grip_message.dst_gid` | Hashed GID; `0` for broadcast |
| `appId` | integer | `grip_message.app_id` | SDK app ID |
| `msgId` | integer | `grip_message.msg_id` | Matches `file id` in COMMANDHANDLER lines |
| `seqNo` | integer | `grip_message.seq_no` | Reverse order — highest seqNo = first packet |
| `isFirstPacket` | bool | `grip_message.is_first_packet` | `true` = highest seqNo packet |
| `isAck` | bool | `grip_message.is_ack` | `true` = this is an ACK segment, not data |
| `requiresAck` | bool | `grip_message.requires_ack` | `true` = receiver must send keep-alive ACK |
| `isPeriodic` | bool | `grip_message.is_periodic` | `true` = periodic PLI broadcast |
| `repCounter` | integer | `grip_message.rep_counter` | Retransmission count. `0` = first attempt. Max 3 before firmware cancels. |
| `segment size` | integer | `grip_message.segment_size` | Segment byte size |
| `hops` | integer | `grip_message.hops` | **Incoming only.** Genuine RF mesh hop count. Null on outgoing. |
| `rssi` | integer | `grip_message.rssi` | **Incoming only.** Real dBm (signed). Null on outgoing. |
| *(line serial)* | string | `grip_message.radio_serial` | From `Device - SERIAL` on the same line |
| *(line direction)* | string | `grip_message.direction` | `"outgoing"` (GRIP_SENDER) · `"incoming"` (GRIP_Receiver) |

> ⚠️ **SRC and DST are hashed GID values.** They are consistent across messages from the same node but cannot be reversed to the full 64-bit GID without a lookup. Use them for correlation, not identity.
>
> ⚠️ **hops and rssi on incoming lines are genuine RF data.** These are not SDK counters — they reflect actual mesh routing and signal strength. This is the first source of genuine hop count and RSSI in RSDK format logs.
>
> ⚠️ **repCounter tracks retransmissions per segment.** `repCounter = 1` means the segment was sent twice; `= 2` means three times (one more failure = firmware cancel). Monitor for `repCounter > 0` as a link quality indicator.

---

### GRIP Transfer Lifecycle

Aggregated from `COMMANDHANDLER` and `GRIP_SENDER` lines. One `GripTransfer` record per file transfer.

| Raw Log Pattern | Component | Parsed As | Model Field | Notes |
|----------------|-----------|-----------|-------------|-------|
| `File transmission started, file id: N` | `COMMANDHANDLER` | start event | `grip_transfer.start_timestamp` | Transfer start time on sender |
| `File has been successfully delivered to destination, file id: N` | `COMMANDHANDLER` | end event | `grip_transfer.end_timestamp` | Transfer end time on sender |
| `sent file msgId: N stopped with true in Nms earlyCancel: false` | `GRIP_SENDER` | duration | `grip_transfer.delivery_ms` | End-to-end delivery time in milliseconds |
| `sent file msgId: N stopped with false ... earlyCancel: true` | `GRIP_SENDER` | cancelled | `grip_transfer.outcome = "cancelled"` | Transfer cancelled; link failure |
| `Full grip file received! id: N number of segments: N` | `COMMANDHANDLER` | receiver done | `grip_transfer.segment_count` | Populated from receiver-side line |
| *(EOF with open transfer)* | — | incomplete | `grip_transfer.outcome = "incomplete"` | Transfer started but no completion log found |

| Field | Model Field | Notes |
|-------|-------------|-------|
| Computed | `grip_transfer.delivery_ms` | `end_timestamp − start_timestamp` in ms. Null if incomplete. |
| Computed | `grip_transfer.outcome` | `"delivered"` · `"cancelled"` (earlyCancel=true) · `"incomplete"` |
| Computed | `grip_transfer.max_rep_counter` | Max `repCounter` seen across all segments. `0` = clean. `2` = near-cancel. |

> ⚠️ **delivery_ms reflects sender-side timing only.** The receiver assembles the file slightly later. For a cross-device view, correlate `grip_transfer.start_timestamp` on sender with `Full grip file received` timestamp on receiver.
>
> ⚠️ **segment_count comes from the receiver side.** If only a sender log is loaded, `segment_count` will be null.

---

### Platform Detection (RSDK)

| Log Content | Inferred Platform |
|-------------|-------------------|
| `IosBleRadio` present | `ios` |
| `AndroidBleRadio` or `BluetoothGatt` present | `android` |
| Neither | `unknown` |

---

### Deduplication (RSDK)

iOS RSDK logs contain exact duplicate lines (every line appears twice). The parser deduplicates by storing the first 120 characters of each line as a key and skipping exact matches.

> ⚠️ **Android logs do not have duplicate lines.** The deduplication is a no-op for Android but harmless.

---

### Session Gap Detection (RSDK)

Gaps are detected from `system_samples`, `ble_fail_events`, and `tx_events` timestamps combined. Gap threshold: 30 minutes.

---

## Format 3: Android ATAK Plug-in Log

**File type:** `.log`
**Platform:** Android only
**Structure:** Newline-delimited JSON objects, one per line, optionally wrapped in `[ ]`

---

### Record Type Detection

Record type is identified by the presence of specific keys:

| Key Present | Record Type |
|-------------|-------------|
| `appVersion` | App Info |
| `connectionState` | Device Health |
| `logId` | Message |
| `message.deviceState` present (no `logId`) | SDK Error (SDK Logging 2.0) |
| `event` | Event |

> ⚠️ **Detection order:** the `sdkError` check (`message.deviceState` present) must come **before** the `event` check, because an `sdkError` record's `message` object also nests an `event` object.

---

### Record Type: App Info

One record per app launch. Regular logs accumulate multiple App Info records across launches.

| Raw Field | Parsed As | Model Field | Notes |
|-----------|-----------|-------------|-------|
| `launchTimeInMillis` | Unix epoch ms → datetime | `app_info.launch_timestamp` | Convert: `ms / 1000` → datetime |
| `appVersion` | string | `device.app_version` | e.g. `2.3.0 (be06682e) - [5.2.0]` |
| `buildNumber` | integer | `device.build_number` | |
| `atakVersion` | string | `app_info.atak_version` | e.g. `5.5.1.10` |
| `deviceInfo.deviceModel` | string | `device.device_model` | e.g. `Samsung SM-S711U1` |
| `deviceInfo.apiVersion` | integer | `app_info.android_api_version` | Android API level, e.g. `34` |
| *(inferred)* | `"android"` | `device.platform` | ATAK format is Android-only |

---

### Record Type: Device Health

Written approximately every 30 seconds. Provides radio health data.

| Raw Field | Parsed As | Model Field | Notes |
|-----------|-----------|-------------|-------|
| `timestampInMillis` | Unix epoch ms → datetime | `health.timestamp` | Convert: `ms / 1000` |
| `serialNumber` | string | `health.serial_number` | Radio serial, e.g. `PNE234100406` |
| `connectionState` | string | `health.connection_state` | `CONNECTED` or `CONNECTING` |
| `batteryLevel` | integer | `health.battery_pct` | Percent (0–100). Negative values skipped. |
| `isCharging` | bool | `health.is_charging` | |
| `connectionType` | string | `health.connection_type` | e.g. `BLE` |
| `mode` | string | `health.mode` | `NORMAL` most common; `LISTEN_ONLY` also confirmed (HOTLIPS, GATOR — 2026-06-04). This is the **confirmed** mode state, distinct from the `NetworkMode`/`TetherMode` SDK Error polls of it (see clientRequest section below) |
| `firmwareVersion` | string | `health.firmware_version` | e.g. `3.2.10` |
| `storedMessages` | integer | `health.stored_messages` | Messages stored on radio |
| `powerAmpTemperature` | integer | `health.pa_temp_c` | **Celsius.** Negative values skipped. Convert to °F for display. |
| `systemTemperature` | integer | `health.system_temp_c` | **Celsius.** `0` during `CONNECTING` = placeholder → stored as `null`. |
| `transmitPowerDifferential` | integer | `health.transmit_power_differential` | `255` during `CONNECTING` = sentinel → stored as `null`. Meaning undocumented. |
| `hardwareVersion` | integer | `health.hardware_version` | Radio hardware revision |
| `bootloaderVersion` | integer | `health.bootloader_version` | |
| `chipArchitecture` | string | `health.chip_architecture` | e.g. `LEGACY_NXP` |
| `errorCode` | string | `health.error_code` | e.g. `SystemErrorCodes(errorValue=0)` |
| `gid` | integer | `health.gid` / `device.gid` | Device GID — also used to populate device identity |

> ⚠️ **Sentinel values during CONNECTING state:**
> - `systemTemperature = 0` → stored as `null` (not a real reading)
> - `transmitPowerDifferential = 255` → stored as `null` (not yet valid)
>
> ⚠️ **Device Health records also populate `system_samples`** for cross-format compatibility, but only when both `battery_pct` and `pa_temp_c` are non-null.
>
> ⚠️ **Some early ATAK plugin v3.0 builds omit Device Health records entirely** — zero `connectionState` records for the whole session, meaning no battery/thermal/firmware/radio-health data at all. `parser/atak.py` surfaces this as a `DATA LIMITATION —` entry in `parse_errors` rather than silently rendering empty Thermal/Battery tabs. See `docs/atak_v3_early_integration_notes.md`.

---

### Record Type: Message

One record per RF message sent or received. The majority of records in a typical log.

| Raw Field | Parsed As | Model Field | Notes |
|-----------|-----------|-------------|-------|
| `timestampInMillis` | Unix epoch ms → datetime | `message.timestamp` | Log receipt time |
| `logId` | integer | `message.log_id` | Can be negative (signed 32-bit int) |
| `messageTimestampInMillis` | Unix epoch ms → datetime | `message.message_timestamp` | Originator send time |
| `isSender` | bool | `message.is_sender` | `true` = this device sent the message |
| `senderGid` | integer | `message.sender_gid` | GID of the sender |
| `deliveryStatus` | string | `message.delivery_status` | See delivery statuses below |
| `segmentCount` | integer | `message.segment_count` | Total RF segments for this message |
| `numberOfOpenSegments` | integer | `message.open_segments` | Segments not yet received. `> 0` = partially received. **`-99` is a sentinel** (transfer cancelled before count was known) → stored as `null`. |
| `retryCount` | integer | `message.retry_count` | Number of TX retries |
| `deliveryTimeInMillis` | integer | `message.delivery_time_ms` | ms from send to receive. **Can be negative** — see note. |
| `messageProtocol` | string | `message.message_protocol` | `BROADCAST` or `UNICAST` |
| `message.type` | string | `message.message_type` | `pli`, `textChat`, `mapObject`, `fileTransfer` |
| `message.objectType` | string | `message.message_object_type` | `PIN`, `SHAPE`, `CIRCLE`, `ROUTE`, `VEHICLE`, `CASEVAC`, etc. Only present on `mapObject` type. |
| `message.interval` | string | `message.pli_interval` | PLI interval in seconds. Only present on `pli` type. |
| `message.fileName` | string | `message.file_name` | Only present on `fileTransfer` type. Real filename on completed transfers (e.g. `goTenna_ATAK_<ts>.jpg`); `"UNKNOWN"` when the transfer was incomplete. |
| `receiverGid` | integer | `message.receiver_gid` | `0` when `isSender = true` |
| `hopCount` | integer | `message.hop_count` | RF hops. `0` when `isSender = true`. **Genuine RF routing data.** |
| `rssi` | integer | `message.rssi` | Real dBm (already signed). `0` when `isSender = true` — placeholder, not a real reading. |
| `originatorCallsign` | string | `message.originator_callsign` | **Always empty string** in observed samples. Identity is GID-only. |
| `originatorUUID` | string | `message.originator_uuid` | `ANDROID-*` UUID of the originator. `""` when missing. |
| `loggingUserLocation` | object | `message.logging_user_location` | `{lat, long, alt}` — the logging device's own GPS at log time. Present on every message record. Used as the **receiver dot position** in the Hop Count Map. |
| `transmittedLocation` | object | `message.transmitted_location` | `{lat, long, alt}` — location embedded in the message payload. Present on `pli`/`fileTransfer`/`mapObject`; **absent on `textChat`** (stored as `null`). Used as the **sender endpoint of RF link lines** in the Hop Count Map. |
| `senderCallsign` | string | `message.sender_callsign` | **Populated starting with ATAK plugin v3.0** (was always empty string in earlier plugin versions/samples). Used as a fallback for `device.callsign` when the filename doesn't yield one — see `docs/atak_v3_early_integration_notes.md`. |
| `senderUUID` | string | *(not used)* | **Always empty string** in this log format. |
| `receiverCallsign` | string | *(not used)* | **Always empty string** in this log format. |

**Delivery statuses:**

| Status | Meaning |
|--------|---------|
| `SUCCESS` | **Sender-side** confirmed delivery — sender received the final ACK (GRIP confirmed). Only on `isSender=true` `fileTransfer` records. Distinct from `FULLY_RECEIVED`. |
| `FULLY_RECEIVED` | Receiver assembled all segments |
| `SENT` | Sent by this device |
| `DELIVERED` | Unicast confirmed delivery |
| `PARTIALLY_RECEIVED` | Some segments missing — typically file transfers |

> ⚠️ **`deliveryTimeInMillis` is only meaningful on the sender side** (`isSender=true` + `SUCCESS`). Receiver-side `fileTransfer` records report `0`, a placeholder — not a real delivery time.

> ⚠️ **Negative `delivery_time_ms`** occurs when the receiver's clock is behind the sender's. Observed in 18% of records in sample data, most common at hop counts 3–4. These records are preserved — not discarded.
>
> ⚠️ **RSSI on sent messages is always 0.** When `isSender = true`, `rssi = 0` is a placeholder. The `rssi_is_valid` property returns `false` for these. Never include sent-message RSSI in signal quality analysis.
>
> ⚠️ **Callsign and UUID fields are always empty.** Node identity in ATAK logs is GID-only. Callsigns cannot be resolved from this format.
>
> ⚠️ **`mapObject` subtypes are conditional.** A subtype only appears if a user actually sent that object type during the session. The parser must not fail on unknown `objectType` values.

---

### Record Type: Event

Lifecycle and configuration events.

| Raw Field | Parsed As | Model Field | Notes |
|-----------|-----------|-------------|-------|
| `timestampInMillis` | Unix epoch ms → datetime | `event.timestamp` | |
| `event.type` | string | `event.event_type` | See event types below |
| `event.serialNumber` | string | `event.serial_number` | Present on `deviceConnected` only |
| `event.connectionType` | string | `event.connection_type` | Present on connect/disconnect events |
| `event.power` | float | `event.power_watts` | Watts. Present on `powerLevelUpdated` and `frequencyUpdated` |
| `event.isDistance` | bool | `event.pli_is_distance` | Present on `pliSettingUpdated` |
| `event.interval` | integer | `event.pli_interval_sec` | Seconds. Present on `pliSettingUpdated` |
| `event.isAutoSend` | bool | `event.pli_auto_send` | Present on `pliSettingUpdated` |
| `event.bandwidth` | float | `event.bandwidth_khz` | kHz. Present on `frequencyUpdated` (regular log only) |
| `event.channels` | list | `event.channels` | List of `{frequency: float, isControlChannel: bool}`. Present on `frequencyUpdated`. |
| `event.location` | object | `event.location` | `{lat, long, alt}` at disconnect time. Present on `deviceDisconnected` only. |
| `event.updateStatus` | string | `event.update_status` | e.g. `"STARTED"`. Present on `firmwareUpdate` only. |
| `event.updateTimeInMillis` | int | `event.update_time_ms` | Present on `firmwareUpdate` only. |
| `event.isRelayModeEnabled` | bool | `event.relay_mode_enabled` | Present on `relayModeUpdated` only. Observed 2026-06-04 (DARE log). |

**Event types:**

| `event.type` | Meaning |
|-------------|---------|
| `deviceConnected` | Radio connected via BLE |
| `deviceDisconnected` | Radio disconnected |
| `powerLevelUpdated` | TX power changed |
| `pliSettingUpdated` | PLI interval or mode changed |
| `frequencyUpdated` | Frequency set changed (regular log only — not observed in enhanced log) |
| `firmwareUpdate` | Radio firmware update lifecycle (e.g. `updateStatus="STARTED"`). A significant QA event — an update mid-session can explain degraded behavior. |
| `relayModeUpdated` | Relay mode toggled (`isRelayModeEnabled`). Relay mode extends a goTenna network via a relay node. Observed 2026-06-04. |

> ⚠️ **Other known radio modes not yet observed as app-level events:** goTenna
> radios also support **Limited Mode** (device physically off, connected to
> external power — microcontroller monitors hardware/battery only) and
> **Tether Mode** (phone tethered to the radio via USB rather than BLE, with
> its own power-management logic). Neither has been observed as an
> `event.type` in any log reviewed so far. Limited Mode is plausibly never
> loggable this way at all, since the device isn't meaningfully "on" from
> the plugin's perspective. Tether Mode's *polled* state (not a change
> event) has been observed via SDK Logging 2.0 `clientRequest` records — see
> the `TetherMode` row in the SDK Error / clientRequest section below.

---

### Record Type: SDK Error (SDK Logging 2.0)

New structured-log record type (the dominant record type in enhanced field logs —
56,179 across 7 logs in the 2026-06-03 session, outnumbering message records 3:1).
Despite the `sdkError` name, these are **general structured SDK log events**, not
error-only records; the name reflects the `"ERROR"` entry in `tags`.

| Raw Field | Parsed As | Model Field | Notes |
|-----------|-----------|-------------|-------|
| `id` | string | `sdk_error.id` | Record UUID (sample only) |
| `timestamp` | string | `sdk_error.timestamp` | ISO 8601 UTC, microsecond precision (more precise than `timestampInMillis`) |
| `tags` | string array | `sdk_error.tags` / `counts_by_tag` | e.g. `["ERROR","BLE"]`, `["ERROR","RADIO"]` |
| `message.deviceState.platformType` | string | `sdk_error.platform_type` | `"ANDROID"` |
| `message.deviceState.connectionType` | string | `sdk_error.connection_type` | `"BLE"` |
| `message.deviceState.serialNumber` | string | `sdk_error.serial_number` / `serial_numbers` | |
| `message.deviceState.address` | string | `sdk_error.address` | BLE MAC |
| `message.deviceState.connectionState` | string | `sdk_error.connection_state` / `connection_states` | `"CONNECTING"`, `"DISCONNECTED"` observed |
| `message.deviceState.personalGid` | integer | `sdk_error.personal_gid` | |
| `message.deviceState.batteryLevel` | integer | `sdk_error.battery_level` | |
| `message.deviceState.firmwareVersion` | string | `sdk_error.firmware_version` | |
| `message.deviceState.radioType` | string | `sdk_error.radio_type` / `radio_types` | e.g. `"PRO_X_2"` — **surfaced nowhere else in the format**; used for device classification |
| `message.deviceState.mcuuuid` | string | `sdk_error.mcuuuid` | MCU UUID |
| `message.deviceState.endorsements` | string | `sdk_error.endorsements` | e.g. `"PREMIUM"` |
| `message.event.additionalInfo` | string | `sdk_error.additional_info` / `counts_by_info` | Human-readable event description. **Also checked at `message.clientRequest.additionalInfo` when `.event` doesn't have it** — clientRequest-shaped records (below) carry their own additionalInfo there. |

> ⚠️ **DATA LIMITATION — aggregated, never stored per-record.** Because of the
> extreme volume, the parser does **not** keep one object per `sdkError` record.
> It emits a single `AtakSdkErrorSummary` (`result.atak_sdk_error_summary`) holding
> `total_count`, `counts_by_tag`, `counts_by_info`, `radio_types`, `serial_numbers`,
> `connection_states`, and one retained `sample`. A `DATA LIMITATION` entry is added
> to `parse_errors` noting that the baseline volume for a healthy session is unknown
> — the total count (`sdk_error_count`) is informational, not a pass/fail signal.
>
> **Exception — BLE health:** the `ERROR|BLE` subset of `counts_by_tag` is the one
> place this aggregate drives a pass/fail signal. `_result_to_dict()` sums those
> entries into `summary.ble_fail_count` (falling back to the `deviceDisconnected`
> event count only when no SDK 2.0 summary is present — a summary that exists but has
> zero `ERROR|BLE` entries is a genuine `0`, not a fallback trigger) to feed the BLE
> Health Score dimension. The `> 0 = fail` threshold is an initial estimate pending
> field validation, consistent with the other Health Score thresholds.

---

### Record Type: SDK Error — `clientRequest` shape (raw radio commands)

A second shape of SDK Error record, observed 2026-06-04 across 9 of 10 field
logs reviewed. Instead of `message.event`, these carry `message.clientRequest`
— a **raw BLE command attempt** sent to the radio (frequency changes, mode
queries, etc.), with its own lifecycle and outcome. This is the raw
radio-command layer, distinct from (and more granular than) app-level
`event` records: a command can be `QUEUED`, then `COMPLETED` or `FAILED` —
and a `FAILED` command likely never produces a corresponding app-level event
at all, since those typically only fire on a *confirmed* change.

`rawRequest`/`sanitizedRequest` are a Kotlin/Java `toString()` of the command
object, not structured JSON — parsed with regex, not `json.loads`.

| Raw Field | Parsed As | Model Field | Notes |
|-----------|-----------|-------------|-------|
| `message.clientRequest.sequenceNumber` | integer | *(not currently stored)* | |
| `message.clientRequest.status` | string | `.status` on the relevant model below | Observed: `QUEUED`, `COMPLETED`, `FAILED`, `CANCELLED`, `TIMEOUT` — treat as an open set, not exhaustive. `TIMEOUT` surfaced in the MESMER log only after the first four were documented, which is itself evidence the set keeps growing |
| `message.clientRequest.rawRequest` | string | parsed via regex | Command object `toString()`; command type determined by its prefix (`Frequency(`, `NetworkMode(`, `TetherMode(`) |
| `message.clientRequest.additionalInfo` | string | feeds `counts_by_info` | e.g. `"Request is not valid for reason atakplugin.gotennaproag.fh1$c"` on a FAILED Frequency SET |

**`Frequency(channels=[...], action=SET, ...)` → `AtakFrequencySetAttempt`**
(`result.atak_frequency_set_attempts`) — a frequency **SET** attempt at the
radio-command level. Channel frequencies are in Hz in the raw string;
converted to MHz on parse (`464550000hz` → `464.55`).

| Field | Type | Notes |
|-------|------|-------|
| `timestamp` | string | From the SDK Error record's own `timestamp`, not `timestampInMillis`. **Note this is the raw ISO-8601 `…Z` form**, unlike most ATAK timestamps which are normalized to `YYYY-MM-DD HH:MM:SS.ffffff` — UI consumers must handle both |
| `status` | string | Open set — QUEUED / COMPLETED / FAILED / CANCELLED / TIMEOUT observed |
| `action` | string | `SET` and `GET` both observed — MESMER has 28 Frequency commands, 16 SET and 12 GET. Every `Frequency(channels=` command is stored here regardless of action (GETs are not dropped — that would lose real observations); **consumers must split on `action`**, since a GET is a query, not a change attempt. The UI renders SET and GET as separate labelled rows |
| `channels` | list | `[{"frequency": float (MHz), "isControlChannel": bool}]` |

**`NetworkMode(listenOnly=<bool>, action=GET, ...)` and
`TetherMode(enabled=<bool>, batteryThreshold=<int>, action=GET, ...)` →
`AtakRadioModeQuery`** (`result.atak_radio_mode_queries`) — mostly the app
**polling** current listen-only or tether-mode state. `action=GET` was the only
value in the samples reviewed when this was first written, but `action=SET` has
since been observed (MESMER: 2,028 mode records — 2,016 GET polls and 12
`NetworkMode` SETs, 6 of them COMPLETED, which are real mode-change commands).
The parser stores both in this one list; the UI splits on `action` and labels
them separately (`polls` vs `change cmds`) so a change command is never counted
as a poll. Neither is confirmed state.
The *confirmed* mode (as opposed to a poll of it) comes from the Device Health
record's own `mode` field instead (see below) — `LISTEN_ONLY` has been
observed there directly, distinct from these polls.

| Field | Type | Notes |
|-------|------|-------|
| `timestamp` | string | Raw ISO-8601 `…Z` form, as with `AtakFrequencySetAttempt` |
| `mode_type` | string | `"listenOnly"` (from `NetworkMode`) or `"tether"` (from `TetherMode`) |
| `value` | bool | The polled state at query time |
| `status` | string | Open set — QUEUED / COMPLETED / FAILED / CANCELLED / TIMEOUT observed |
| `battery_threshold` | integer | Tether only. Absent key → `None`, never `0` — a real 0% threshold must stay distinguishable from "not reported" |
| `action` | string | `GET` and `SET` both observed — see note above |

---

### Filename Convention (ATAK)

```
diagnostic_ATAK_<CALLSIGN>_<GID>_<YYYY-MM-DD>_<HH_MM_SS_mmm>.log
```

The parser extracts `CALLSIGN` and `GID` from the filename. These are the **only source of callsign** for ATAK logs since all callsign fields in the JSON are empty.

---

### Session Gap Detection (ATAK)

Gaps are detected from `atak_messages` and `atak_health_samples` timestamps combined. Gap threshold: 30 minutes.

> ⚠️ **Regular ATAK logs span multiple app launches.** Multiple App Info records indicate multiple launches. Gaps between launches are expected and do not indicate errors.

---

## Format 4: Relay Firmware (UART/USB Debug) Log

**File type:** `.log` / `.txt` (serial console capture)
**Platform:** Relay radio (direct UART/USB, not an app)
**Structure:** `[<ts_abs>-<delta_ms>, <MODULE>, <LEVEL>] <message>`, plus raw
`bucket[...]` lines outside the bracket pattern.

> Timestamps are **relative milliseconds from boot**, not wall clock. `delta_ms`
> (gap since previous line) is matched but unused. Only `INFO`/`ERROR`/`WARN`
> lines are parsed; `DEBUG` is skipped and counted.

Parsed into `FwLogResult` (attached to `ParseResult.fw_log_result`). All Fw*
dataclasses live in `parser/models.py`.

### Identity & Session

| Raw Field | Parsed As | Model Field | Notes |
|-----------|-----------|-------------|-------|
| `rhc_build_resp: using origin hash 0x<hash>` | strip `0x` | `fw_log_result.origin_hash` | Authoritative short address; also `device.callsign` |
| First `RELAY` `prevSdr=<hash>` | hex string | `fw_log_result.origin_hash` (fallback) | Best-effort only — `prevSdr` is the previous sender, may be a neighbor's hash. Used only when no RHC origin line appears |
| `rhc_build_resp: version 0x<v>` | string | `fw_log_result.fw_format_version` | RHC response format version (e.g. `0x10`), **not** radio firmware version |
| `rhc_build_resp: enter` | count | `fw_log_result.rhc_poll_count` | One per health poll |
| min/max bracket `ts_abs` | int ms | `first_ts_ms` / `last_ts_ms` / `duration_ms` | Relative ms; `session_start`/`session_end` are these as strings |

### RF Configuration (`FwRfConfig`, from `TRX INFO` config block)

| Raw Field | Parsed As | Model Field | Notes |
|-----------|-----------|-------------|-------|
| `RF Configuration for <device>` | string | `rf_config.device_type` | Block start, e.g. `goTenna Pro` |
| `Tx power: <n>` | int | `rf_config.tx_power` | |
| `bit_rate=<n>` | int | `rf_config.bit_rate` | bps; **ends** the config block |
| `Region <n>` | int | `rf_config.region` | |
| `<9-digit>Hz` | int list | `rf_config.frequencies_hz` | De-duplicated in order |
| `Control channels (n): a b` | int list | `rf_config.control_channels` | |
| `Data channels (n): a b` | int list | `rf_config.data_channels` | |

### Buckets (`FwBucket`)

| Raw Field | Parsed As | Model Field | Notes |
|-----------|-----------|-------------|-------|
| `bucket[N] HH - HH hours ago: X messages rx'd Y messages relayed Z messages tx'd` | ints | `buckets[]` (`bucket_index`, `hrs_start`, `hrs_end`, `rx`, `relayed`, `tx`) | RHC history repeats per poll; highest-rx snapshot per index kept, sorted newest-first |

### Signal, Routing, Neighbors

| Raw Field | Parsed As | Model Field | Notes |
|-----------|-----------|-------------|-------|
| `Energy on chn=N: last_rssi=-XdBm > avg_rssi=-YdBm (cnt=Z)` | int (`last_rssi`) | `energy_samples[]` | RSSI proxy surfaced in the UI |
| `RSSI[N]: avg=… last=… [min=… max=…] num=…` | `FwRssiSample` | `rssi_samples[]` | **DEBUG-level → always empty.** Matcher wired ahead of a future INFO-level RSSI build |
| `Msg-N cmd=N: transmitMsg=… flooding=… echo=… vine= …` | counts per `=1` | `routing.transmit` / `.flood` / `.echo` / `.vine` | `FwRoutingDecision` |
| `msg already Rx` / `msg already TX` | counts | `routing.skip_rx` / `routing.skip_tx` | Duplicate-suppression on rx/tx paths |
| `neighborAdd[N]: update hash=<h>, …` | unique hashes | `neighbor_hashes[]` | |

### Errors & Warnings

| Raw Field | Parsed As | Model Field | Notes |
|-----------|-----------|-------------|-------|
| `ERROR` `Battery stabilization …` | count | `battery_error_count` | Counted **separately** — known firmware quirk, not a real error |
| Other `ERROR` lines | count by module + unique msgs | `error_counts{}`, `error_messages[]` | Up to 20 unique messages |
| `WARN` lines | count by module + unique msgs | `warn_counts{}`, `warn_messages[]` | Up to 20 unique messages |
| `DEBUG` lines | count only | `skipped_debug` | Not parsed |

> **Serialized but not displayed:** `rssi_summary` and `summary.rssi_ch0/ch1_avg_dbm`
> exist in the `_result_to_dict()` output but are always empty/`None` because
> `rssi_samples` is (RSSI[] is DEBUG-only). The UI shows channel energy instead.

---

## Format 5: TAK Server CoT Event Stream

**File type:** `.json`
**Platform:** TAK server (server-side — **not** a device or app log)
**Structure:** A single JSON array of pre-parsed Cursor-on-Target event records.

> The server has already extracted the useful fields; the original CoT XML stays
> in `raw`. This is the server's JSON export, **not** a raw multicast/UDP CoT
> capture — that would need a separate ingestion path.

Parsed into `TakEvent` records on `ParseResult.tak_events`, plus one optional
`TakServerInfo` on `ParseResult.tak_server_info`. Both live in `parser/models.py`.

### Event Fields (`TakEvent`)

| Raw Field | Parsed As | Model Field | Notes |
|-----------|-----------|-------------|-------|
| `time` | ISO-8601 → `%Y-%m-%d %H:%M:%S.%f` | `timestamp` | Device-generated event time. **Required** — record skipped and counted if missing/unparseable |
| `receivedAt` | same normalization | `received_at` | TAK server receipt time. `""` when absent |
| — | `round((receivedAt − time) × 1000)` | `latency_ms` | `None` when `receivedAt` absent. **Negative is valid data** — device clock ahead of server (P8) |
| `category` | verbatim | `category` | `PLI` \| `Marker` \| `Chat` \| `Other` — pre-computed server-side. Defaults to `Other` only when the field is absent |
| `type` | verbatim | `cot_type` | CoT type code: `a-f-G-U-C` (PLI), `a-f-G-U-C-I` (Marker), `b-t-f` (Chat), `t-x-takp-v` (handshake) |
| `uid` | verbatim | `uid` | `ANDROID-<hex>`, bare UUID (WebTAK), or `GeoChat.ANDROID-<hex>` |
| `callsign` | verbatim | `callsign` | `None` for server plumbing. **The only operator identity available** |
| `nodeType` | verbatim | `node_type` | `Android` \| `WebTAK` \| `Other` |
| `platform` | verbatim | `platform` | `ATAK-CIV` \| `WebTAK` \| `None`. Often absent (18 of 91 in sample) — never guessed |
| `parentCallsign` | verbatim | `parent_callsign` | Always `null` in observed samples |
| `lat` / `lon` | float, `0.0` default | `lat` / `lon` | Meaningless when `has_gps_fix` is False |
| `lat == 0 and lon == 0` | inverted | `has_gps_fix` | CoT no-fix sentinel (paired with a `999999.0`-family `hae`/`ce`/`le` in the raw XML). **Single source of truth — the UI must not re-derive it** |
| `raw` | verbatim | `raw_cot` | Full CoT XML. Holds everything not promoted to a field: `<status battery=…>`, `<takv device=… os=…>`, `<track speed=… course=…>`, GeoChat `<remarks>` |

### Server Info (`TakServerInfo`)

| Raw Source | Parsed As | Model Field | Notes |
|-----------|-----------|-------------|-------|
| `serverVersion="…"` in the `raw` XML of the first `Other` record | regex | `tak_server_info.server_version` | e.g. `5.6-RELEASE-57-HEAD` |
| `apiVersion="…"` in the same record | regex | `tak_server_info.api_version` | e.g. `3` |

> A stream with no `t-x-takp-v` handshake record yields `tak_server_info = None`.
> Both fields come from **one** record — the handshake is not repeated.

### Derived Collections (`ParseResult` properties)

| Property | Definition | Notes |
|----------|-----------|-------|
| `tak_pli_events` | `category == "PLI"` | |
| `tak_chat_events` | `category == "Chat"` | Envelope only — bodies not extracted |
| `tak_no_fix_events` | `not has_gps_fix` **and** `category in ("PLI", "Marker")` | **Deliberately scoped** to the categories expected to carry a position. Chat/server-control events have none to miss |
| `tak_unique_callsigns` | distinct non-empty `callsign` | Operator count; excludes the handshake record |
| `tak_latency_ms_values` | non-`None` `latency_ms` | Feeds avg/max/min and the negative count |

> **Not extracted from `raw_cot`:** GeoChat `<remarks>` message bodies, `<status
> battery>`, `<takv>` device/OS strings, and `<track>` speed/course. All present
> in the XML, none promoted to fields in this version. Both gaps are reported in
> `parse_errors` as `DATA LIMITATION —` entries; the telemetry entry names only
> the elements a given stream actually carries, with per-element counts.

### Parsed but not serialized

`raw_cot` is populated by the parser and declared on `TakEvent`, but
`_result_to_dict()` **deliberately omits it** — the full CoT XML would dominate
the payload for no consumer, and `tests/test_parse_route.py` pins the exact
serialized key set so it can't drift back in. The practical consequence is that
everything listed in the note above is unreachable from the UI *and* from an
export, not merely un-promoted: surfacing any of it means extracting it in the
parser first. Both `DATA LIMITATION` entries say so.

---

## Derived / Computed Fields

These fields are computed by the parser or API layer — they do not appear directly in the raw log.

| Field | Source | Computation | Notes |
|-------|--------|-------------|-------|
| `rssi_dbm` (diagnostic) | `rssi_raw` | `rssi_raw − 256` | Converts unsigned byte to real dBm |
| `pa_temp_f` | `pa_temp_c` | `(pa_temp_c × 9/5) + 32` | All temperatures displayed in °F |
| `system_temp_f` | `system_temp_c` | `(system_temp_c × 9/5) + 32` | Null if source is null |
| `lifetime_uptime_hours` | `lifetime_uptime_tenths_hrs` | `value / 10` | Diagnostic stat block only |
| `session_start` | All timestamps | Minimum timestamp in file | |
| `session_end` | All timestamps | Maximum timestamp in file | |
| `session_gaps` | All timestamps sorted | Gaps > 30 min between consecutive timestamps | |
| `summary.avg_hop_count` | `hop_count` on received messages | Mean of all non-null hop counts | |
| `summary.peak_temp_f` | `pa_temp_f` on system samples | Maximum °F across all samples | |
| `summary.min_battery_pct` | `battery_pct` on system samples | Minimum % across all samples | |
| `summary.avg_rssi` | ATAK: `rssi` on received messages where `rssi_is_valid`; diagnostic/rsdk: mean of GRIP incoming `rssi` (same value as `grip_avg_rssi`) | Mean dBm. Feeds the Health Score RSSI dimension; `None` when no RSSI data (e.g. diagnostic) → dimension shown N/A | |
| `summary.unique_sender_gids` (ATAK) | `sender_gid` on all messages | Count of distinct GIDs | |
| `summary.negative_delivery_time_count` (ATAK) | `delivery_time_ms` | Count of records where value < 0 | Clock skew indicator |
| `summary.success_count` (ATAK) | `delivery_status == "SUCCESS"` | Count of sender-confirmed deliveries | Sender-side ACK; distinct from FULLY_RECEIVED |
| `summary.file_transfer_count` (ATAK) | `message_type == "fileTransfer"` | Count of fileTransfer records | |
| `summary.file_transfer_named_count` (ATAK) | `file_name` not empty/`"UNKNOWN"` | Count of completed (named) transfers | |
| `summary.sdk_error_count` (ATAK) | `atak_sdk_error_summary.total_count` | Total sdkError records | Informational — baseline unknown |
| `summary.radio_types` (ATAK) | `atak_sdk_error_summary.radio_types` | Sorted distinct radioType values | e.g. `["PRO_X_2"]` |
| `summary.ble_fail_count` | ATAK: `counts_by_tag` `ERROR\|BLE` entries, else `deviceDisconnected` count only when no SDK 2.0 summary; diagnostic/rsdk: `len(ble_fail_events)`; relay_manager: absent | BLE failures for the Health Score | Feeds BLE dimension; `> 0 = fail` threshold pending validation |
| `summary.total_events` (TAK) | `len(tak_events)` | Count of parsed CoT records | Skipped malformed records are not included |
| `summary.pli_count` / `chat_count` / `marker_count` / `other_count` (TAK) | `category` counts | One per category | `marker_count` and `other_count` use the `is_marker` / `is_server_control` properties |
| `summary.unique_callsigns` (TAK) | `len(tak_unique_callsigns)` | Distinct operators on the server | Not a radio count — one operator may change radios |
| `summary.no_fix_count` (TAK) | `len(tak_no_fix_events)` | **PLI/Marker only** | ⚠️ The `parse_errors` no-fix sentence counts **all** categories, so the two numbers differ legitimately (1 vs 5 in the sample). See the parsing-requirements limitation — the error wording is an open fix |
| `summary.avg_latency_ms` / `max_latency_ms` / `min_latency_ms` (TAK) | `tak_latency_ms_values` | Mean (1 dp) / max / min | `None` when no record has both timestamps. All three are read by the TAK tab's KPI row — it must not re-derive them from `tak_events`, which is how the displayed average and the exported one came to round differently |
| `summary.negative_latency_count` (TAK) | `latency_ms < 0` | Clock-skew indicator | Device clock ahead of server — real data, not an error (P8) |

---

## Cross-Format Notes

| Topic | Diagnostic | RSDK | ATAK |
|-------|-----------|------|------|
| **Temperature unit in log** | Celsius | Celsius | Celsius |
| **Temperature display** | °F (convert) | °F (convert) | °F (convert) |
| **RSSI storage** | Unsigned byte (137–237) | Real dBm (signed) | Real dBm (signed) |
| **RSSI conversion needed** | Yes: `value − 256` | No | No |
| **Hop count reliability** | ✅ Genuine RF routing data | ✅ Genuine when from `GRIP_Receiver` incoming fields (`grip_messages.hops`); ❌ legacy `SendMessageResponse` counter still excluded | ✅ Genuine RF routing data |
| **Callsign availability** | ✅ Present in received messages | ✅ Via ContactManager lines (not yet parsed) | ❌ Always empty — filename only |
| **Sent message records** | ❌ Not recorded | Partial (TX outcomes only) | ✅ `isSender = true` records |
| **PLI sent counter** | ❌ Always 0 | N/A | ✅ `SENT` delivery status |
| **Platform** | iOS only | iOS or Android | Android only |
| **Timestamps include year** | ✅ | ✅ | ✅ (ATAK) / ❌ (Relay Health Manager ADB logs) |

### TAK Server — why it sits outside that table

The three columns above all describe **one radio's view of itself**. A TAK
stream is the server's view of many clients, so most rows have no counterpart
rather than a different value:

| Topic | TAK Server |
|-------|-----------|
| **Temperature / battery / thermal** | ❌ Not present — no device telemetry at all |
| **RSSI / hop count** | ❌ Not present — application layer, after mesh delivery |
| **Radio identity** | ❌ No serial, GID or firmware version. Callsign + CoT `uid` only |
| **Callsign availability** | ✅ Populated (`None` only on the server handshake record) |
| **Sent vs received** | N/A — the server receives everything; there is no sender/receiver split |
| **Position** | ✅ On PLI and Marker; `(0,0)` sentinel means no fix |
| **Timestamps include year** | ✅ ISO-8601 UTC, wall clock. Two of them: device `time` and server `receivedAt` |
| **Health Score** | ❌ Excluded (`HEALTH_FORMATS`) — carries none of the five dimension inputs |

---

_Last updated: 2026-08-24_
