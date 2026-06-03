# Log Field Definitions

> **Source of truth for every log field used in parsing and data point generation.**
> Each entry defines what the field means in the raw log, how it is parsed, what it becomes
> in the data model, and any known accuracy limitations or caveats.
>
> Last updated: 2026-06-03

---

## Table of Contents

- [Format 1: goTenna Pro+ Diagnostic Log](#format-1-gotenna-pro-diagnostic-log)
- [Format 2: RSDK iOS/Android SDK Log](#format-2-rsdk-iosandroid-sdk-log)
  - [GRIP Message Fields](#grip-message-fields-grip_sender--grip_receiver)
  - [GRIP Transfer Lifecycle](#grip-transfer-lifecycle)
- [Format 3: Android ATAK Plug-in Log](#format-3-android-atak-plug-in-log)
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
| `event` | Event |

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
| `mode` | string | `health.mode` | e.g. `NORMAL` |
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
| `numberOfOpenSegments` | integer | `message.open_segments` | Segments not yet received. `> 0` = partially received. |
| `retryCount` | integer | `message.retry_count` | Number of TX retries |
| `deliveryTimeInMillis` | integer | `message.delivery_time_ms` | ms from send to receive. **Can be negative** — see note. |
| `messageProtocol` | string | `message.message_protocol` | `BROADCAST` or `UNICAST` |
| `message.type` | string | `message.message_type` | `pli`, `textChat`, `mapObject`, `fileTransfer` |
| `message.objectType` | string | `message.message_object_type` | `PIN`, `SHAPE`, `CIRCLE`, `ROUTE`, `VEHICLE`, `CASEVAC`, etc. Only present on `mapObject` type. |
| `message.interval` | string | `message.pli_interval` | PLI interval in seconds. Only present on `pli` type. |
| `message.fileName` | string | `message.file_name` | Only present on `fileTransfer` type. |
| `receiverGid` | integer | `message.receiver_gid` | `0` when `isSender = true` |
| `hopCount` | integer | `message.hop_count` | RF hops. `0` when `isSender = true`. **Genuine RF routing data.** |
| `rssi` | integer | `message.rssi` | Real dBm (already signed). `0` when `isSender = true` — placeholder, not a real reading. |
| `senderCallsign` | string | *(not used)* | **Always empty string** in this log format. Identity is GID-only. |
| `senderUUID` | string | *(not used)* | **Always empty string** in this log format. |
| `originatorCallsign` | string | *(not used)* | **Always empty string** in this log format. |
| `receiverCallsign` | string | *(not used)* | **Always empty string** in this log format. |

**Delivery statuses:**

| Status | Meaning |
|--------|---------|
| `FULLY_RECEIVED` | All segments received |
| `SENT` | Sent by this device |
| `DELIVERED` | Unicast confirmed delivery |
| `PARTIALLY_RECEIVED` | Some segments missing — typically file transfers |

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

**Event types:**

| `event.type` | Meaning |
|-------------|---------|
| `deviceConnected` | Radio connected via BLE |
| `deviceDisconnected` | Radio disconnected |
| `powerLevelUpdated` | TX power changed |
| `pliSettingUpdated` | PLI interval or mode changed |
| `frequencyUpdated` | Frequency set changed (regular log only — not observed in enhanced log) |

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
| `summary.avg_rssi` (ATAK) | `rssi` on received messages where `rssi_is_valid` | Mean dBm, sent-message RSSI excluded | |
| `summary.unique_sender_gids` (ATAK) | `sender_gid` on all messages | Count of distinct GIDs | |
| `summary.negative_delivery_time_count` (ATAK) | `delivery_time_ms` | Count of records where value < 0 | Clock skew indicator |

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

---

_Last updated: 2026-06-03_
