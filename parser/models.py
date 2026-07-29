"""
parser/models.py
Shared dataclasses used by the diagnostic, RSDK, ATAK, Relay Manager, and
firmware-log (fw_log) parsers.
Includes GRIP transfer primitives (GripMessage, GripTransfer) for RSDK logs.
Every parser returns a ParseResult; the API and UI only need to know this shape.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


# ── Shared primitives ─────────────────────────────────────────────────────────

@dataclass
class DeviceInfo:
    """Identity and software version for one logging device."""
    callsign: str = ""
    gid: str = ""
    device_model: str = ""
    app_version: str = ""
    build_number: str = ""
    log_version: str = ""
    radio_firmware: str = ""
    radio_serial: str = ""
    platform: str = ""          # "ios" | "android" | "unknown"


@dataclass
class SystemSample:
    """One periodic radio health snapshot (battery, temp, firmware)."""
    timestamp: str
    battery_pct: Optional[int] = None
    pa_temp_c: Optional[int] = None     # Celsius from log; UI converts to °F
    firmware: str = ""


@dataclass
class ReceivedMessage:
    """A single received RF message (PLI or chat/map)."""
    timestamp: str
    message_id: str = ""
    data_type: str = ""         # "broadcast" | "1to1"
    message_type: str = ""      # "location" | "text"
    hop_count: Optional[int] = None
    rssi_raw: Optional[int] = None      # unsigned byte; real dBm = rssi_raw - 256
    frequency_set: str = ""
    frames_used: Optional[int] = None
    originator_callsign: str = ""
    originator_gid: str = ""
    originator_location: str = ""
    originator_pli_interval: str = ""
    originator_timestamp: str = ""
    receiver_callsign: str = ""
    receiver_gid: str = ""
    receiver_location: str = ""
    receiver_pli_interval: str = ""
    receiver_timestamp: str = ""

    @property
    def rssi_dbm(self) -> Optional[int]:
        """Convert raw unsigned RSSI byte to real dBm."""
        return (self.rssi_raw - 256) if self.rssi_raw is not None else None

    @property
    def is_pli(self) -> bool:
        return self.message_type == "location"

    @property
    def is_chat(self) -> bool:
        return self.message_type == "text"


@dataclass
class MessageCountSnapshot:
    """Cumulative app-level message counter at one point in time."""
    timestamp: str
    pli_sent: int = 0
    pli_received: int = 0
    chat_sent: int = 0
    chat_received: int = 0


@dataclass
class RadioStatSnapshot:
    """Firmware lifetime + session counters captured at stat-query time."""
    timestamp: str
    # Lifetime counters (all-time firmware, never reset)
    lifetime_uptime_tenths_hrs: Optional[int] = None    # divide by 10 for hours
    lifetime_msgs_originated: Optional[int] = None
    lifetime_msgs_received: Optional[int] = None
    lifetime_msgs_relayed: Optional[int] = None
    lifetime_msgs_rejected: Optional[int] = None
    lifetime_uhf_tx_5w_sec: Optional[int] = None
    lifetime_uhf_rx_sec: Optional[int] = None
    commands_errored: Optional[int] = None
    temp_threshold_events: Optional[int] = None
    avg_uhf_rssi_db: Optional[int] = None
    avg_uhf_ant_quality_db: Optional[int] = None
    avg_ble_rssi: Optional[int] = None
    # Session/pairing counters (reset on BLE re-pair — use with caution)
    session_msgs_sent: Optional[int] = None
    session_msgs_received: Optional[int] = None
    session_msgs_relayed: Optional[int] = None
    session_msgs_rejected: Optional[int] = None

    @property
    def lifetime_uptime_hours(self) -> Optional[float]:
        if self.lifetime_uptime_tenths_hrs is not None:
            return self.lifetime_uptime_tenths_hrs / 10
        return None


@dataclass
class FrequencySet:
    """Radio frequency configuration snapshot."""
    timestamp: str
    name: str = ""
    power_watts: str = ""
    bandwidth_khz: str = ""
    control_channels: str = ""
    data_channels: str = ""


@dataclass
class SessionGap:
    """A detected break in activity > 30 minutes."""
    from_timestamp: str
    to_timestamp: str
    gap_minutes: float
    note: str = ""


# ── RSDK-specific primitives ──────────────────────────────────────────────────

@dataclass
class BleFailEvent:
    """One BLE reconnection failure cycle (iOS only)."""
    timestamp: str
    radio_serial: str
    hour: int


@dataclass
class TxEvent:
    """A unicast TX attempt with its outcome."""
    timestamp: str
    message_id: str
    outcome: str    # "final_ack" | "nack" | "timeout" | "keepalive_ack"
    radio_serial: str = ""


# ── ATAK-specific primitives ──────────────────────────────────────────────────

@dataclass
class AtakMessage:
    """
    A single RF message record from an ATAK plug-in log.

    RSSI here is real dBm (already signed, not an unsigned byte like
    the diagnostic format). originator_callsign/originator_uuid are always
    empty strings in observed samples — identity for those is GID-only.
    sender_callsign, however, IS populated starting with ATAK plugin v3.0
    (was always "" in earlier plugin versions/samples).
    """
    timestamp: str                          # ISO 8601 converted to _TS_FMT_OUT
    log_id: Optional[int] = None           # Can be negative (signed 32-bit int)
    message_timestamp: str = ""            # Originator send time
    is_sender: bool = False
    sender_gid: Optional[int] = None
    sender_callsign: str = ""              # "" in pre-v3.0 plugin logs; populated in v3.0+
    delivery_status: str = ""              # FULLY_RECEIVED | SENT | DELIVERED |
                                           # PARTIALLY_RECEIVED
    segment_count: int = 1
    open_segments: Optional[int] = None    # > 0 means partially received;
                                           # -99 sentinel → None (count unknown)
    retry_count: int = 0
    delivery_time_ms: Optional[int] = None # Can be negative (clock skew)
    message_protocol: str = ""             # BROADCAST | UNICAST
    message_type: str = ""                 # pli | textChat | mapObject | fileTransfer
    message_object_type: str = ""          # PIN | SHAPE | CIRCLE | ROUTE |
                                           # VEHICLE | CASEVAC | etc.
    pli_interval: str = ""                 # PLI messages only
    file_name: str = ""                    # fileTransfer messages only
    receiver_gid: Optional[int] = None
    hop_count: Optional[int] = None        # 0 when is_sender=True
    rssi: Optional[int] = None             # Real dBm (signed); 0 when is_sender=True

    # Enhanced (SDK Logging 2.0) location + originator fields
    logging_user_location: Optional[dict] = None  # {lat, long, alt} — logger's own GPS
    transmitted_location: Optional[dict] = None    # {lat, long, alt} in payload;
                                                   # None on textChat
    originator_uuid: str = ""              # ANDROID-* UUID; "" when missing
    originator_callsign: str = ""          # always empty in observed samples

    @property
    def is_pli(self) -> bool:
        return self.message_type == "pli"

    @property
    def is_chat(self) -> bool:
        return self.message_type == "textChat"

    @property
    def is_map_object(self) -> bool:
        return self.message_type == "mapObject"

    @property
    def is_file_transfer(self) -> bool:
        return self.message_type == "fileTransfer"

    @property
    def rssi_is_valid(self) -> bool:
        """RSSI of 0 on sent messages is a placeholder, not a real reading."""
        return self.rssi is not None and not self.is_sender


@dataclass
class AtakDeviceHealth:
    """
    One periodic radio health poll from an ATAK plug-in log (~every 30s).

    Temperatures are Celsius from the log; UI must convert to °F.
    transmit_power_differential=255 and system_temperature=0 during
    CONNECTING state are sentinel/placeholder values — treat as None.
    """
    timestamp: str
    serial_number: str = ""
    connection_state: str = ""             # CONNECTED | CONNECTING
    battery_pct: Optional[int] = None
    is_charging: bool = False
    connection_type: str = ""              # BLE
    mode: str = ""                         # NORMAL
    firmware_version: str = ""
    stored_messages: int = 0
    pa_temp_c: Optional[int] = None        # Celsius; UI converts to °F
    system_temp_c: Optional[int] = None    # Celsius; UI converts to °F
                                           # 0 during CONNECTING = placeholder
    transmit_power_differential: Optional[int] = None  # 255 = not yet valid
    hardware_version: Optional[int] = None
    bootloader_version: Optional[int] = None
    chip_architecture: str = ""
    error_code: str = ""
    gid: Optional[int] = None


@dataclass
class AtakEvent:
    """
    A lifecycle or configuration event from an ATAK plug-in log.

    event_type covers: deviceConnected | deviceDisconnected |
    powerLevelUpdated | pliSettingUpdated | frequencyUpdated
    """
    timestamp: str
    event_type: str = ""

    # deviceConnected
    serial_number: str = ""
    connection_type: str = ""

    # powerLevelUpdated
    power_watts: Optional[float] = None

    # pliSettingUpdated
    pli_interval_sec: Optional[int] = None
    pli_is_distance: Optional[bool] = None
    pli_auto_send: Optional[bool] = None

    # frequencyUpdated (regular log) — full channel list
    bandwidth_khz: Optional[float] = None
    channels: list = field(default_factory=list)  # list of {"frequency": float,
                                                   #          "isControlChannel": bool}

    # deviceDisconnected — device location at disconnect (enhanced log)
    location: Optional[dict] = None        # {lat, long, alt}

    # firmwareUpdate (enhanced log)
    update_status: str = ""                # e.g. "STARTED"
    update_time_ms: Optional[int] = None


@dataclass
class AtakAppInfo:
    """
    App launch record from an ATAK plug-in log.
    One record per app launch; regular logs accumulate multiple over time.
    """
    launch_timestamp: str
    app_version: str = ""
    build_number: Optional[int] = None
    atak_version: str = ""
    device_model: str = ""
    android_api_version: Optional[int] = None


@dataclass
class AtakSdkErrorSample:
    """
    One retained sdkError record — a representative sample of the aggregated
    SDK Logging 2.0 records, which are never stored individually due to volume.

    radioType is surfaced nowhere else in the ATAK format, so the sample is the
    only place per-record deviceState detail survives.
    """
    id: str = ""
    timestamp: str = ""                    # ISO 8601 UTC, microsecond precision
    tags: list = field(default_factory=list)
    platform_type: str = ""
    connection_type: str = ""
    serial_number: str = ""
    address: str = ""                      # BLE MAC
    connection_state: str = ""
    personal_gid: Optional[int] = None
    battery_level: Optional[int] = None
    firmware_version: str = ""
    radio_type: str = ""                   # e.g. "PRO_X_2"
    mcuuuid: str = ""
    endorsements: str = ""                 # e.g. "PREMIUM"
    additional_info: str = ""              # human-readable event description


@dataclass
class AtakSdkErrorSummary:
    """
    Aggregated summary of SDK Logging 2.0 (sdkError) records from an ATAK
    enhanced log.

    These records (identified by 'id', 'timestamp', 'tags' fields) are the
    dominant record type in enhanced field logs — thousands per session. They
    are NOT stored individually. Despite the 'ERROR' tag value, they are general
    structured SDK log events, not error-only records.

    Captured aggregates:
      - total_count:       total records of this type in the log
      - counts_by_tag:     count per tag combination (e.g. {'ERROR|BLE': 412})
      - counts_by_info:    count per additionalInfo string
      - radio_types:       sorted distinct radioType values (e.g. ['PRO_X_2'])
      - serial_numbers:    sorted distinct serialNumber values
      - connection_states: sorted distinct connectionState values
      - first/last_timestamp: ISO 8601 UTC timestamps bounding the records
      - sample:            one retained record for per-field detail

    The volume baseline for a healthy session is unknown — the count is
    informational, not a pass/fail signal (see DATA LIMITATION in parse_errors).
    Whether this record type appears in regular (non-enhanced) logs from the
    same firmware version is currently unknown — see parsing-requirements.md.
    """
    total_count: int = 0
    counts_by_tag: dict = field(default_factory=dict)       # {'ERROR|BLE': 412}
    counts_by_info: dict = field(default_factory=dict)      # {additionalInfo: count}
    radio_types: list = field(default_factory=list)         # sorted distinct
    serial_numbers: list = field(default_factory=list)      # sorted distinct
    connection_states: list = field(default_factory=list)   # sorted distinct
    first_timestamp: str = ""    # ISO 8601 UTC
    last_timestamp: str = ""     # ISO 8601 UTC
    sample: Optional[AtakSdkErrorSample] = None


# ── Relay Manager-specific primitives ─────────────────────────────────────────

@dataclass
class RelayHealthRequest:
    """
    One confirmed relay health request fired by the Relay Manager app.

    Recorded whenever "Command relayHealthRequestCall" appears in a
    Services Plugin log line from the relay manager process.

    ble_payload holds the raw hex bytes of the BLE write immediately
    following the command — the actual relay health attribute values
    (SNR, battery, temperature, uptime, firmware version) are encoded
    here but NOT yet decoded.  See DATA LIMITATION notice in parse_errors.
    """
    timestamp: str                        # Android logcat wall-clock (local TZ)
    internal_timestamp: Optional[str] = None  # UTC timestamp from System.out
    ble_payload: Optional[str] = None         # raw hex; None until decoded


@dataclass
class RelayNotificationEvent:
    """
    One firmware notification received from a relay node over BLE.

    Notification type codes observed in stage logs:
      8   BLE keepalive            (scheduledHealthRequest logs)
      9   BLE secondary event      (scheduledHealthRequest logs)
      72  BLE poll heartbeat       (networkPolling logs)
      73  Health response ready — perform get/delete on firmware
      74  Device alert — pull required
      75  Device alert variant
      104 Battery/charging state changed

    NOTE: The parser tracks notification counts in
    relay_manager_notification_counts (dict[int, int]) rather than
    emitting one object per notification, because types 72/8 fire
    thousands of times per log file. This class is reserved for
    future use if per-event detail is needed.
    """
    timestamp: str
    notification_type: int
    hex_value: str


@dataclass
class RelayManagerEvent:
    """
    A named relay manager application event (excluding BLE write noise).

    event_type values:
      health_response_ready   — relay responded; app should get/delete from firmware
      device_alert            — relay sent an unsolicited alert; pull required
      battery_state_changed   — relay battery or charging state changed
      empty_sender_uuid       — ContactManager skipped update (empty UUID); benign
    """
    timestamp: str
    internal_timestamp: Optional[str]
    event_type: str
    raw_message: str = ""


# ── GRIP transfer primitives ──────────────────────────────────────────────────

@dataclass
class GripMessage:
    """
    One structured GRIP message fields log line from GRIP_SENDER or GRIP_Receiver.

    GRIP_SENDER emits these for outgoing messages (no hops/rssi).
    GRIP_Receiver emits these for incoming messages (hops and rssi present —
    genuine RF routing data).

    MsgType values: 0 = private/unicast · 2 = broadcast
    SRC/DST are hashed GID values (signed 32-bit integers).
    rep_counter > 0 indicates a retransmission; firmware cancels after 3 attempts.
    """
    timestamp: str
    direction: str                    # "outgoing" | "incoming"
    msg_type: int                     # 0 = private, 2 = broadcast
    msg_type_label: str               # "private" | "broadcast" | "unknown(N)"
    msg_id: int
    src_gid: int                      # hashed GID — signed 32-bit
    dst_gid: int                      # 0 for broadcast
    app_id: int
    seq_no: int
    is_first_packet: bool
    is_ack: bool
    requires_ack: bool
    is_periodic: bool
    rep_counter: int                  # retransmission count; max 3 before cancel
    segment_size: int
    hops: Optional[int] = None        # incoming only; genuine RF hop count
    rssi: Optional[int] = None        # incoming only; real dBm (signed)
    radio_serial: str = ""


@dataclass
class GripTransfer:
    """
    One complete GRIP file transfer lifecycle (sender perspective).

    Aggregated from COMMANDHANDLER File transmission started/delivered lines
    and GRIP_SENDER sent file stopped line.

    delivery_ms is the time from 'File transmission started' to
    'File has been successfully delivered' on the sender side.
    outcome is 'delivered', 'cancelled' (earlyCancel=true), or 'incomplete'
    (transfer was still open at end of log file).
    max_rep_counter is the highest retransmission count seen across all
    segments of this transfer — 0 = clean delivery, 2 = near-cancel.
    """
    msg_id: int
    radio_serial: str
    start_timestamp: str
    end_timestamp: str
    delivery_ms: Optional[int]        # None if transfer did not complete
    outcome: str                      # "delivered" | "cancelled" | "incomplete"
    max_rep_counter: int              # 0–2; firmware cancels at 3
    segment_count: Optional[int]      # from receiver-side "Full grip file received"



# ── Firmware log (fw_log) ──────────────────────────────────────────────────────

@dataclass
class FwBucket:
    """One 6-hour message count window from the RHC bucket history."""
    bucket_index: int
    hrs_start:    int
    hrs_end:      int
    rx:           int
    relayed:      int
    tx:           int


@dataclass
class FwRssiSample:
    """One RSSI[] detailed sample from TRX INFO."""
    channel:  int
    avg_dbm:  int
    last_dbm: int
    min_dbm:  int
    max_dbm:  int
    num:      int


@dataclass
class FwRoutingDecision:
    """Aggregated routing decision counts."""
    transmit:  int = 0
    echo:      int = 0
    vine:      int = 0
    flood:     int = 0
    skip_rx:   int = 0
    skip_tx:   int = 0


@dataclass
class FwRfConfig:
    """RF radio configuration extracted from TRX INFO config block."""
    device_type:      str = ""
    region:           int = 0
    tx_power:         int = 0
    bit_rate:         int = 0
    frequencies_hz:   list = field(default_factory=list)
    control_channels: list = field(default_factory=list)
    data_channels:    list = field(default_factory=list)


@dataclass
class FwLogResult:
    """All structured data extracted from a firmware log."""
    origin_hash:          str = ""
    fw_format_version:    str = ""
    rf_config:            Optional["FwRfConfig"] = None
    first_ts_ms:          int = 0
    last_ts_ms:           int = 0
    duration_ms:          int = 0
    buckets:              list = field(default_factory=list)
    rssi_samples:         list = field(default_factory=list)
    energy_samples:       list = field(default_factory=list)
    routing:              Optional["FwRoutingDecision"] = None
    neighbor_hashes:      list = field(default_factory=list)
    battery_error_count:  int = 0
    error_counts:         dict = field(default_factory=dict)
    error_messages:       list = field(default_factory=list)
    warn_counts:          dict = field(default_factory=dict)
    warn_messages:        list = field(default_factory=list)
    rhc_poll_count:       int = 0
    total_lines:          int = 0
    parsed_lines:         int = 0
    skipped_debug:        int = 0


# ── Top-level parse result ────────────────────────────────────────────────────

@dataclass
class ParseResult:
    """
    The complete output of parsing one log file.
    diagnostic.py, rsdk.py, atak.py, relay_manager.py, and fw_log.py all return
    this shape.
    """
    # Metadata
    log_format: str = ""        # "diagnostic" | "rsdk" | "atak" | "relay_manager" | "fw_log"
    source_filename: str = ""
    parse_errors: list[str] = field(default_factory=list)

    # Identity
    device: DeviceInfo = field(default_factory=DeviceInfo)

    # Time bounds
    session_start: str = ""
    session_end: str = ""
    session_gaps: list[SessionGap] = field(default_factory=list)

    # Health time series
    system_samples: list[SystemSample] = field(default_factory=list)

    # RF messages
    received_messages: list[ReceivedMessage] = field(default_factory=list)

    # App counters
    message_count_snapshots: list[MessageCountSnapshot] = field(default_factory=list)

    # Radio stats
    radio_stat_snapshots: list[RadioStatSnapshot] = field(default_factory=list)

    # Frequency config
    frequency_sets: list[FrequencySet] = field(default_factory=list)

    # RSDK only
    ble_fail_events: list[BleFailEvent] = field(default_factory=list)
    tx_events: list[TxEvent] = field(default_factory=list)
    contacts: dict[str, str] = field(default_factory=dict)  # {uuid: callsign} from ContactManager

    # ATAK only
    atak_messages: list[AtakMessage] = field(default_factory=list)
    atak_health_samples: list[AtakDeviceHealth] = field(default_factory=list)
    atak_events: list[AtakEvent] = field(default_factory=list)
    atak_app_launches: list[AtakAppInfo] = field(default_factory=list)
    atak_sdk_error_summary: Optional[AtakSdkErrorSummary] = None  # None if no SDK 2.0 records present

    # RSDK only — GRIP transfer data
    grip_messages: list[GripMessage] = field(default_factory=list)
    grip_transfers: list[GripTransfer] = field(default_factory=list)

    # Firmware log only
    fw_log_result: Optional[FwLogResult] = None

    # Relay Manager only
    relay_health_requests: list[RelayHealthRequest] = field(default_factory=list)
    relay_manager_events: list[RelayManagerEvent] = field(default_factory=list)
    relay_manager_notification_counts: dict[int, int] = field(default_factory=dict)
    relay_manager_subtype: str = ""       # "networkPolling" | "scheduledHealthRequest" | "unknown"
    relay_manager_environment: str = ""   # "stage" | "unknown" (prod TBD)
    relay_manager_app_pid: str = ""       # Android process ID of com.gotenna.relaymanager
    relay_manager_ble_address: str = ""   # BLE MAC of the connected relay node

    # ── Convenience properties ────────────────────────────────────────────────

    @property
    def pli_messages(self) -> list[ReceivedMessage]:
        return [m for m in self.received_messages if m.is_pli]

    @property
    def chat_messages(self) -> list[ReceivedMessage]:
        return [m for m in self.received_messages if m.is_chat]

    @property
    def unique_originators(self) -> dict[str, str]:
        """Returns {callsign: gid} for every originator seen."""
        seen = {}
        for m in self.received_messages:
            if m.originator_callsign and m.originator_callsign not in seen:
                seen[m.originator_callsign] = m.originator_gid
        return seen

    @property
    def hop_counts(self) -> list[int]:
        return [m.hop_count for m in self.received_messages if m.hop_count is not None]

    @property
    def rssi_values(self) -> list[int]:
        return [m.rssi_raw for m in self.received_messages if m.rssi_raw is not None]

    @property
    def final_message_counts(self) -> Optional[MessageCountSnapshot]:
        return self.message_count_snapshots[-1] if self.message_count_snapshots else None

    # ── ATAK convenience properties ───────────────────────────────────────────

    @property
    def atak_pli_messages(self) -> list[AtakMessage]:
        return [m for m in self.atak_messages if m.is_pli]

    @property
    def atak_chat_messages(self) -> list[AtakMessage]:
        return [m for m in self.atak_messages if m.is_chat]

    @property
    def atak_unique_sender_gids(self) -> set[int]:
        return {m.sender_gid for m in self.atak_messages if m.sender_gid is not None}

    @property
    def atak_received_messages(self) -> list[AtakMessage]:
        return [m for m in self.atak_messages if not m.is_sender]

    @property
    def atak_sent_messages(self) -> list[AtakMessage]:
        return [m for m in self.atak_messages if m.is_sender]
