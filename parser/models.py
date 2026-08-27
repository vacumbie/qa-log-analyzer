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
    mode: str = ""                         # NORMAL | LISTEN_ONLY observed so far
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
    powerLevelUpdated | pliSettingUpdated | frequencyUpdated | relayModeUpdated
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

    # relayModeUpdated — observed 2026-06-04 (DARE log); not yet documented
    # elsewhere prior to this
    relay_mode_enabled: Optional[bool] = None


@dataclass
class AtakFrequencySetAttempt:
    """
    A frequency-set command attempt, extracted from an SDK Logging 2.0
    clientRequest record whose rawRequest embeds a Frequency(...) command —
    e.g. 'Frequency(channels=[Frequency: 464550000hz isControlChannel: YES,
    ...], action=SET, ...)'.

    This is the RAW RADIO COMMAND layer, distinct from the app-level
    `frequencyUpdated` event: a SET attempt can be QUEUED, then COMPLETED,
    FAILED, CANCELLED, and so on. A FAILED attempt would likely never produce a
    corresponding `frequencyUpdated` event, since the app-level event only fires
    on a confirmed change. Treat every attempt as "attempted," not "confirmed"
    — including COMPLETED, which is a command-layer ack, NOT evidence the radio
    is operating on that config. Confirmed frequency comes from
    `frequencyUpdated` only; the UI deliberately does not promote a COMPLETED
    attempt into its confirmed timeline.

    Status is an open set — QUEUED, COMPLETED, FAILED, CANCELLED, and TIMEOUT
    observed so far. Do not assume that list is exhaustive.
    """
    timestamp: str
    status: str = ""                        # open set — see docstring
    action: str = ""                        # e.g. "SET"
    channels: list = field(default_factory=list)  # [{"frequency": float (MHz),
                                                    #   "isControlChannel": bool}]


@dataclass
class AtakRadioModeQuery:
    """
    A NetworkMode/TetherMode clientRequest record — the app polling (GET) the
    radio's current listen-only or tether-mode state. Distinct from
    AtakFrequencySetAttempt: this doesn't request a change, it's asking
    "what mode are you in right now." Observed action so far: GET only.

    mode_type: "listenOnly" (from NetworkMode) or "tether" (from TetherMode).
    Confirmed mode CHANGES (not polls) come from AtakDeviceHealth.mode
    instead — e.g. "LISTEN_ONLY" has been observed there directly.
    """
    timestamp: str
    mode_type: str = ""                     # "listenOnly" | "tether"
    value: Optional[bool] = None
    status: str = ""                        # QUEUED | COMPLETED | FAILED
    battery_threshold: Optional[int] = None  # tether only
    action: str = ""                        # e.g. "GET"


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


# ── TAK server primitives ──────────────────────────────────────────────────────

@dataclass
class TakEvent:
    """
    One Cursor-on-Target (CoT) event captured from a TAK server stream.

    category arrives pre-computed from the TAK server and is copied verbatim —
    this parser derives nothing from the CoT `type` attribute. Treat the set as
    open: an unrecognised value is stored as-is, never mapped through an
    allow-list. The values observed so far correspond to `type` as follows:
      PLI     — a-f-G-U-* position/location report from a friendly ground unit
      Marker  — a-f-G-U-C-I "I" (icon/marker) variant, seen from WebTAK clients
      Chat    — b-t-f GeoChat text message
      Other   — server plumbing (e.g. t-x-takp-v TAK protocol/version handshake);
                carries no device identity or position

    has_gps_fix is False in two cases, and consumers should treat lat/lon as
    meaningless in both:
      - the 0.0/0.0 sentinel pair, paired with a 9999999.0-family hae/ce/le
        placeholder — the CoT convention for "no GPS fix", not a real position
        at (0,0). A *single* zero coordinate is a real position (the equator or
        the prime meridian) and keeps its fix.
      - lat/lon is None because the record carried only one of them, or a
        non-numeric value. The missing half is never defaulted to 0.0, which
        would fabricate a position and pass the sentinel test above.
    The two are counted separately in parse_errors: a sentinel means the device
    had no fix, a None means the record was incomplete.

    latency_ms is receivedAt (TAK server receipt time) minus time (device-
    generated event time) — the KNOT-style cross-device skew backlog item
    (P8), but measured server-side. Can be negative if the source device's
    clock is running fast relative to the TAK server; the sample data has
    reproduced this (see parse_errors note in parse_tak_log).

    raw_cot retains the original CoT XML for cases the promoted fields don't
    cover (e.g. WebTAK-specific detail children). It stops at the parser: the
    API deliberately does not serialize it, so it is not reachable from the UI
    or an export — see the DATA LIMITATION entry in parse_tak_log for the
    fields that live only in there.
    """
    timestamp: str                          # event 'time' (device-generated), _TS_FMT_OUT
    category: str                           # "PLI" | "Marker" | "Chat" | "Other"
    cot_type: str                           # raw CoT type code, e.g. "a-f-G-U-C"
    uid: str = ""
    callsign: Optional[str] = None          # None for server plumbing / some chat senders
    node_type: str = ""                     # "Android" | "WebTAK" | "Other"
    platform: Optional[str] = None          # "ATAK-CIV" | "WebTAK" | None
    parent_callsign: Optional[str] = None
    lat: Optional[float] = None            # None when the record carried no usable pair
    lon: Optional[float] = None
    has_gps_fix: bool = True
    received_at: str = ""                   # TAK server receipt timestamp, _TS_FMT_OUT
    latency_ms: Optional[int] = None
    raw_cot: str = ""

    @property
    def is_pli(self) -> bool:
        return self.category == "PLI"

    @property
    def is_chat(self) -> bool:
        return self.category == "Chat"

    @property
    def is_marker(self) -> bool:
        return self.category == "Marker"

    @property
    def is_server_control(self) -> bool:
        return self.category == "Other"

    @property
    def is_unrecognized_category(self) -> bool:
        """True for a category outside the four seen so far.

        The set is open — the server computes it, and a future TAK release can
        add one. Such an event gets its own bucket rather than being folded into
        Other, the same call made for ATAK's unparsed `action` values: folding
        would hide a new category behind a label that says "server control",
        and dropping it would break the arithmetic (the category counts must sum
        to total_events).
        """
        return self.category not in ("PLI", "Marker", "Chat", "Other")


@dataclass
class TakServerInfo:
    """
    TAK server identity, extracted from a t-x-takp-v TakControl/
    TakServerVersionInfo handshake record, if present in the stream.
    """
    server_version: str = ""    # e.g. "5.6-RELEASE-57-HEAD"
    api_version: str = ""       # e.g. "3"


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


# ── Next-Gen Radio — ht-modem primitives ───────────────────────────────────────
# See docs/parsing-requirements.md "Next-Gen Radio — Modem (ht-modem) Log" and
# docs/log-field-definitions.md Format 5 for the full field-by-field spec this
# mirrors.

@dataclass
class HtModemTxPacket:
    """
    One TX packet lifecycle, from `Received packet for encoding` through its
    outcome (queued or dropped).

    `dropped` is True when a `CSMA QUEUE is Full, dropping packet` line
    followed this packet's encoding block — that line carries no packetID of
    its own, so it is attributed to the most recently seen packet (see
    htmodem.py parsing notes). If a drop line appears with no preceding
    packet in the current session, it is counted in
    `HtModemResult.orphaned_drop_count` instead of fabricating a packet.
    """
    packet_id:      int
    timestamp:      str = ""
    chdesc:         int = 0
    mod_mode:       int = 0
    fec_mode:       int = 0
    priority:       int = 0
    local_flag:     int = 0
    data_length:    int = 0
    symbol_count:   Optional[int] = None
    sample_count:   Optional[int] = None
    encoded_len:    Optional[int] = None
    bch_val:        str = ""
    payload_extended_from: Optional[int] = None
    payload_extended_to:   Optional[int] = None
    queued:         Optional[bool] = None   # True = added to xmit queue, False = dropped, None = outcome not seen
    numinqueue:     Optional[int] = None
    # RF transmission confirmations — a separate, later event from "queued."
    # A LIST, not a single scalar: real captures show some packets get
    # confirmed more than once (42 of 2,585 in one real session) — genuine
    # RF-layer retransmissions, not duplicate log lines. Overwriting with the
    # latest would silently discard evidence of a retry. Attribution follows
    # the same "attach to whichever packet is current" rule as drops, since
    # confirmation does not always immediately follow "Added packet to xmit
    # queue" (other lines can intervene).
    transmissions:  list["HtModemTransmitConfirmation"] = field(default_factory=list)

    @property
    def transmitted(self) -> bool:
        return len(self.transmissions) > 0

    @property
    def retransmit_count(self) -> int:
        return max(0, len(self.transmissions) - 1)


@dataclass
class HtModemTransmitConfirmation:
    """
    One "Packet Transmitted" RF confirmation line. Units are the radio's own
    raw scale, not independently verified against a hardware spec — Rev/Fwd
    are almost certainly reflected/forward power in raw ADC counts (VSWR /
    return-loss related, alongside the explicit S11 dB figure). temp_val is
    on its own scale — NOT the same units/sensor as the LPD/FPD/PL
    temp_samples elsewhere in this result; do not merge or compare them.
    """
    rev_val:  int
    fwd_val:  int
    s11_db:   int
    temp_val: int


@dataclass
class HtModemFreqChange:
    """One TX or RX frequency change command."""
    timestamp: str
    direction: str   # "TX" | "RX"
    hz:        int


@dataclass
class HtModemPowerChange:
    """One TX power level change command."""
    timestamp:  str
    xmit_level: float


@dataclass
class HtModemTempSample:
    """One periodic Zynq MPSoC thermal reading. Raw log is Celsius."""
    timestamp: str
    lpd_c:     float
    fpd_c:     float
    pl_c:      float


@dataclass
class HtModemResult:
    """All structured data extracted from a next-gen radio modem (ht-modem) log."""
    fpga_version_ok:        Optional[bool] = None   # None if the check line never appears
    libiio_version:         str = ""
    filter_bank:            str = ""
    filter_range_mhz:       str = ""
    ad936x_init_error_count: int = 0   # collapsed count of the init-failure cascade, not per-line
    iio_devices_found:      Optional[int] = None   # "Found <N> devices" seen before AD5592 init
    ad5592_devices_found:   Optional[int] = None   # "Found <N> devices" seen after "Starting AD5592 init"
    clock_cal_offset:       Optional[int] = None
    si4460_cal_offset:      Optional[int] = None
    gpsd_connect_error:     bool = False
    freq_changes:           list[HtModemFreqChange] = field(default_factory=list)
    power_changes:          list[HtModemPowerChange] = field(default_factory=list)
    tx_packets:             list[HtModemTxPacket] = field(default_factory=list)
    orphaned_drop_count:    int = 0   # CSMA-full drop lines with no preceding TX packet block
    orphaned_transmitted_count: int = 0   # "Packet Transmitted" lines with no preceding TX packet block
    temp_samples:           list[HtModemTempSample] = field(default_factory=list)
    total_lines:            int = 0

    @property
    def dropped_count(self) -> int:
        return sum(1 for p in self.tx_packets if p.queued is False) + self.orphaned_drop_count

    @property
    def queued_count(self) -> int:
        return sum(1 for p in self.tx_packets if p.queued is True)


# ── Next-Gen Radio — ht-router primitives ──────────────────────────────────────
# See docs/parsing-requirements.md "Next-Gen Radio — Router (ht-router) Log" and
# docs/log-field-definitions.md Format 6 for the full field-by-field spec this
# mirrors. Two real captures showed genuinely different snapshot schemas (one
# session had zero modem-transmit activity, so several output.* fields never
# appeared at all) — every snapshot field below is Optional for that reason,
# not just defensive style.

@dataclass
class RouterHistogramBucket:
    """One bucket from an output.overhead[N] / output.xmit_completion[N] line."""
    bucket:      int
    range_min:   int
    range_max:   int
    count:       int


@dataclass
class RouterStatSnapshot:
    """
    One periodic counter snapshot — the ~20 input.*/output.* lines emitted
    together roughly every 10s are grouped into ONE of these, never stored as
    flat per-line records (that was the core parsing requirement for this
    format). `connected` is the line that terminates and finalizes a group.

    Retention: every snapshot in the file is kept here — no downsampling at
    parse time. Trimming/aggregation for display is a UI/API-layer decision,
    deliberately deferred past this parser.

    IMPORTANT: every numeric field here is a cumulative session-lifetime
    counter, not a per-interval delta — verified strictly non-decreasing
    across real samples (e.g. output.modem_xmit_failed climbs 1, 1, 2, 2, ...
    to a final 59, matching the ht-modem's 59 dropped packets exactly). A
    per-interval rate must be computed as the difference between consecutive
    snapshots, never summed across all snapshots.
    """
    timestamp:                str = ""   # timestamp of the first line in this group
    # Link-layer validity/error counters — seen in captures with real RF
    # noise; absent (not zero) in a clean session, same absence convention
    # as the output.* transmit fields below.
    input_too_short_link_hdr:     Optional[int] = None
    input_too_short_link_payload: Optional[int] = None
    input_too_short_link_crc:     Optional[int] = None
    input_wrong_link_version:     Optional[int] = None
    input_crc_present:            Optional[int] = None
    input_bad_crc:                Optional[int] = None
    input_subframe_no_protocol:          Optional[int] = None
    input_subframe_logical_recv_error:   Optional[int] = None
    input_subframe_family_recv_error:    Optional[int] = None
    input_subframe_count:     Optional[int] = None
    input_traffic_ag:         Optional[int] = None
    input_ctl:                Optional[int] = None
    input_sts:                Optional[int] = None
    input_total_frames:       Optional[int] = None
    input_total_bytes:        Optional[int] = None
    input_total_m2m:          Optional[int] = None
    input_m2m_xmit:           Optional[int] = None
    input_m2m_control:        Optional[int] = None
    input_m2m_recv:           Optional[int] = None
    input_m2m_status:         Optional[int] = None
    input_m2m_xmit_status:    Optional[int] = None
    output_traffic_ag_ok:     Optional[int] = None
    output_traffic_ag_fail:   Optional[int] = None
    output_ctl_ok:            Optional[int] = None
    output_ctl_fail:          Optional[int] = None
    output_sts_ok:            Optional[int] = None
    output_sts_fail:          Optional[int] = None
    output_aggregation_subframes: Optional[int] = None
    output_aggregation_frames:    Optional[int] = None
    output_total_bytes:       Optional[int] = None
    # Only present in sessions with actual modem-transmit activity — absent
    # entirely (not zero) in a session that never transmitted.
    output_time_outs:         Optional[int] = None
    output_bottom_timed_out:  Optional[int] = None
    output_modem_xmit_failed: Optional[int] = None
    output_tap_frames:        Optional[int] = None
    output_overhead:          Optional[RouterHistogramBucket] = None
    output_xmit_completion:   Optional[RouterHistogramBucket] = None
    connected:                Optional[bool] = None


@dataclass
class RouterProtocolMessage:
    """One client-hdr/mgt-hdr protocol message (from a udp input/output line)."""
    timestamp:   str
    io_direction: str   # "input" | "output" — which way through the router
    udp_idx:     int
    peer:        Optional[str]   # only present on "udp input" lines
    dst:         str
    src:         str
    version:     int
    msg_type:    str
    direction:   str   # "request" | "response" — the protocol message's own direction


@dataclass
class RouterForwardEvent:
    """One mgt_hub_forward.548 send/skip event."""
    timestamp:     str
    request_type:  int
    dst:           str
    sent_count:    int
    skipped_count: int


@dataclass
class RouterTransmission:
    """One 'transmission <N> finished in <ns> ns' completion event — the
    router-side counterpart to the modem's TX packet lifecycle."""
    timestamp:    str
    transmission_id: int
    duration_ns:  int


@dataclass
class HtRouterResult:
    """All structured data extracted from a next-gen radio router (ht-router) log."""
    session_start:       str = ""
    router_pid:          Optional[int] = None
    modem_pid:           Optional[int] = None
    udp_sockets:         list[str] = field(default_factory=list)
    socket_warning_count: int = 0
    aghub_init_addr:     str = ""
    rotation_markers:    list[str] = field(default_factory=list)
    protocol_messages:   list[RouterProtocolMessage] = field(default_factory=list)
    forward_events:      list[RouterForwardEvent] = field(default_factory=list)
    stat_snapshots:      list[RouterStatSnapshot] = field(default_factory=list)
    transmissions:       list[RouterTransmission] = field(default_factory=list)
    # Discrete event types seen but not deep-parsed (clinfo, bcast_hub_forward,
    # echo_info, etc.) — tallied by type so nothing is silently dropped.
    unparsed_event_counts: dict[str, int] = field(default_factory=dict)
    untimestamped_line_count: int = 0
    total_lines:         int = 0

    @property
    def connected_count(self) -> int:
        return sum(1 for s in self.stat_snapshots if s.connected is True)

    @property
    def disconnected_count(self) -> int:
        return sum(1 for s in self.stat_snapshots if s.connected is False)

    @property
    def total_modem_xmit_failed(self) -> Optional[int]:
        """
        All input.*/output.* snapshot fields are cumulative session-lifetime
        counters (verified: strictly non-decreasing across the real samples),
        NOT per-interval deltas. The correct "total" is therefore the last
        snapshot's value, not a sum across snapshots — summing would multiply
        the true count by roughly the number of snapshots taken.
        """
        for s in reversed(self.stat_snapshots):
            if s.output_modem_xmit_failed is not None:
                return s.output_modem_xmit_failed
        return None

    @property
    def total_timeouts(self) -> Optional[int]:
        """See total_modem_xmit_failed — same cumulative-counter caveat."""
        for s in reversed(self.stat_snapshots):
            if s.output_time_outs is not None:
                return s.output_time_outs
        return None


# ── Top-level parse result ────────────────────────────────────────────────────

@dataclass
class ParseResult:
    """
    The complete output of parsing one log file.
    diagnostic.py, rsdk.py, atak.py, relay_manager.py, and fw_log.py all return
    this shape.
    """
    # Metadata
    log_format: str = ""        # "diagnostic" | "rsdk" | "atak" | "relay_manager" | "fw_log" | "htmodem" | "htrouter"
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
    # Frequency SET command attempts extracted from SDK Logging 2.0
    # clientRequest records — the raw radio-command layer, distinct from (and
    # a superset of) confirmed frequencyUpdated app-level events. See
    # AtakFrequencySetAttempt docstring.
    atak_frequency_set_attempts: list[AtakFrequencySetAttempt] = field(default_factory=list)
    # NetworkMode/TetherMode GET-poll records — see AtakRadioModeQuery
    atak_radio_mode_queries: list[AtakRadioModeQuery] = field(default_factory=list)

    # RSDK only — GRIP transfer data
    grip_messages: list[GripMessage] = field(default_factory=list)
    grip_transfers: list[GripTransfer] = field(default_factory=list)

    # Firmware log only
    fw_log_result: Optional[FwLogResult] = None

    # Next-Gen Radio — ht-modem only
    htmodem_result: Optional[HtModemResult] = None

    # Next-Gen Radio — ht-router only
    htrouter_result: Optional[HtRouterResult] = None

    # Relay Manager only
    relay_health_requests: list[RelayHealthRequest] = field(default_factory=list)
    relay_manager_events: list[RelayManagerEvent] = field(default_factory=list)
    relay_manager_notification_counts: dict[int, int] = field(default_factory=dict)
    relay_manager_subtype: str = ""       # "networkPolling" | "scheduledHealthRequest" | "unknown"
    relay_manager_environment: str = ""   # "stage" | "unknown" (prod TBD)
    relay_manager_app_pid: str = ""       # Android process ID of com.gotenna.relaymanager
    relay_manager_ble_address: str = ""   # BLE MAC of the connected relay node

    # TAK server only
    tak_events: list[TakEvent] = field(default_factory=list)
    tak_server_info: Optional[TakServerInfo] = None

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

    # ── TAK convenience properties ────────────────────────────────────────────

    @property
    def tak_pli_events(self) -> list[TakEvent]:
        return [e for e in self.tak_events if e.is_pli]

    @property
    def tak_chat_events(self) -> list[TakEvent]:
        return [e for e in self.tak_events if e.is_chat]

    @property
    def tak_no_fix_events(self) -> list[TakEvent]:
        """PLI/Marker events reporting a position but with no real GPS fix."""
        return [e for e in self.tak_events if not e.has_gps_fix and e.category in ("PLI", "Marker")]

    @property
    def tak_unique_callsigns(self) -> set[str]:
        return {e.callsign for e in self.tak_events if e.callsign}

    @property
    def tak_latency_ms_values(self) -> list[int]:
        return [e.latency_ms for e in self.tak_events if e.latency_ms is not None]

    @property
    def atak_sent_messages(self) -> list[AtakMessage]:
        return [m for m in self.atak_messages if m.is_sender]
