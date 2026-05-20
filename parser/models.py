"""
parser/models.py
Shared dataclasses used by both the diagnostic and RSDK parsers.
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


# ── Top-level parse result ────────────────────────────────────────────────────

@dataclass
class ParseResult:
    """
    The complete output of parsing one log file.
    Both diagnostic.py and rsdk.py return this shape.
    """
    # Metadata
    log_format: str = ""        # "diagnostic" | "rsdk"
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
