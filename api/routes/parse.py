"""
api/routes/parse.py
POST /parse  — upload one or more log files, get back structured JSON.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, HTTPException, UploadFile

# Add project root to path so the parser package is importable
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from parser.diagnostic import parse_diagnostic_log
from parser.rsdk import parse_rsdk_log
from parser.atak import parse_atak_log
from parser.relay_manager import parse_relay_manager_log
from parser.fw_log import parse_fw_log, is_fw_log
from parser.models import ParseResult

router = APIRouter(prefix="/parse", tags=["parse"])


def _detect_format(filename: str, content: str) -> str:
    """
    Heuristically detect log format from filename and content.
    Returns 'fw_log', 'atak', 'relay_manager', 'rsdk', or 'diagnostic'.

    Detection order:
      1. FW Log        — bracket pattern [digits-digits, MODULE, LEVEL] with TRX/RELAY/TPORT
      2. ATAK          — filename starts with 'diagnostic_ATAK_' (legacy), or
                         content is JSON with ATAK-specific fields (logId,
                         connectionState, atakVersion, deliveryStatus). ATAK
                         plugin v3.0 filenames drop the 'ATAK_' segment, so
                         those are detected by content here, not by filename.
      3. Relay Manager — filename or content signals the goTenna Relay Manager app
      4. RSDK          — filename contains 'rsdk' or content has RSDK line markers
      5. Diagnostic    — fallback (goTenna Pro+ block format)
    """
    name = filename.lower()
    snippet = content[:2000]   # wider window for relay manager detection

    # ── FW Log detection — first (most distinctive) ──────────────────────────
    if is_fw_log(content):
        return "fw_log"

    # ── ATAK detection ────────────────────────────────────────────────────────
    # Filename convention (legacy): diagnostic_ATAK_<CALLSIGN>_<GID>_<DATE>.log
    # v3.0 drops the ATAK_ segment — those files match the content check below.
    if "diagnostic_atak_" in name:
        return "atak"
    # Content: ATAK logs are JSON arrays/objects with these distinctive fields
    if (
        '"logId"' in snippet
        or '"connectionState"' in snippet
        or '"atakVersion"' in snippet
        or '"deliveryStatus"' in snippet
    ):
        return "atak"

    # ── Relay Manager detection ───────────────────────────────────────────────
    # Filename conventions used in the field:
    if any(kw in name for kw in (
        "networkpolling",
        "scheduledhealth",
        "relaymanager",
        "relay_manager",
        "relay_health",
    )):
        return "relay_manager"
    # Content signals: the Relay Manager package name or io_stats PID marker
    if "na.relaymanager(" in content or "com.gotenna.relaymanager" in content:
        return "relay_manager"
    # Secondary content signal: Services Plugin emitting relayHealthRequestCall
    if "relayHealthRequestCall" in content:
        return "relay_manager"
    # Tertiary: AndroidBleRadio + Services Plugin combination is present in both
    # RSDK and Relay Manager logs, but "Services Plugin" alone only appears in
    # Relay Manager logs (RSDK uses component tags like "Radio", "IosBleRadio").
    if "Services Plugin" in snippet and "AndroidBleRadio" in snippet:
        return "relay_manager"

    # ── RSDK detection ────────────────────────────────────────────────────────
    if "rsdk" in name or "rsdk_log" in name:
        return "rsdk"
    if "Device -" in snippet and "T" in snippet[:50]:
        return "rsdk"
    if "IosBleRadio" in content or "AndroidBleRadio" in content or "GRIP_SENDER" in content:
        return "rsdk"

    # ── Diagnostic detection (goTenna Pro+ block format) ─────────────────────
    if "Device & Application Info" in content or "Message Count Details" in content:
        return "diagnostic"

    # Default fallback
    return "diagnostic"


def _result_to_dict(r: ParseResult) -> dict[str, Any]:
    """Serialize a ParseResult to a JSON-safe dict."""
    base = {
        "log_format":      r.log_format,
        "source_filename": r.source_filename,
        "parse_errors":    r.parse_errors,
        "device": {
            "callsign":       r.device.callsign,
            "gid":            r.device.gid,
            "device_model":   r.device.device_model,
            "app_version":    r.device.app_version,
            "build_number":   r.device.build_number,
            "log_version":    r.device.log_version,
            "radio_firmware": r.device.radio_firmware,
            "radio_serial":   r.device.radio_serial,
            "platform":       r.device.platform,
        },
        "session_start": r.session_start,
        "session_end":   r.session_end,
        "session_gaps": [
            {
                "from":        g.from_timestamp,
                "to":          g.to_timestamp,
                "gap_minutes": g.gap_minutes,
                "note":        g.note,
            }
            for g in r.session_gaps
        ],
        "system_samples": [
            {
                "timestamp":   s.timestamp,
                "battery_pct": s.battery_pct,
                "pa_temp_c":   s.pa_temp_c,
                "pa_temp_f":   round(s.pa_temp_c * 9 / 5 + 32) if s.pa_temp_c is not None else None,
                "firmware":    s.firmware,
            }
            for s in r.system_samples
        ],
        "received_messages": [
            {
                "timestamp":               m.timestamp,
                "message_id":              m.message_id,
                "data_type":               m.data_type,
                "message_type":            m.message_type,
                "hop_count":               m.hop_count,
                "rssi_raw":                m.rssi_raw,
                "rssi_dbm":                m.rssi_dbm,
                "frequency_set":           m.frequency_set,
                "frames_used":             m.frames_used,
                "originator_callsign":     m.originator_callsign,
                "originator_gid":          m.originator_gid,
                "originator_location":     m.originator_location,
                "originator_pli_interval": m.originator_pli_interval,
                "originator_timestamp":    m.originator_timestamp,
                "receiver_callsign":       m.receiver_callsign,
                "receiver_gid":            m.receiver_gid,
                "receiver_location":       m.receiver_location,
                "receiver_pli_interval":   m.receiver_pli_interval,
                "receiver_timestamp":      m.receiver_timestamp,
            }
            for m in r.received_messages
        ],
        "message_count_snapshots": [
            {
                "timestamp":     s.timestamp,
                "pli_sent":      s.pli_sent,
                "pli_received":  s.pli_received,
                "chat_sent":     s.chat_sent,
                "chat_received": s.chat_received,
            }
            for s in r.message_count_snapshots
        ],
        "radio_stat_snapshots": [
            {
                "timestamp":              s.timestamp,
                "lifetime_uptime_hours":  s.lifetime_uptime_hours,
                "lifetime_msgs_received": s.lifetime_msgs_received,
                "lifetime_msgs_rejected": s.lifetime_msgs_rejected,
                "commands_errored":       s.commands_errored,
                "temp_threshold_events":  s.temp_threshold_events,
                "avg_uhf_rssi_db":        s.avg_uhf_rssi_db,
                "avg_ble_rssi":           s.avg_ble_rssi,
                "session_msgs_sent":      s.session_msgs_sent,
                "session_msgs_received":  s.session_msgs_received,
            }
            for s in r.radio_stat_snapshots
        ],
        "frequency_sets": [
            {
                "timestamp":        f.timestamp,
                "name":             f.name,
                "power_watts":      f.power_watts,
                "bandwidth_khz":    f.bandwidth_khz,
                "control_channels": f.control_channels,
                "data_channels":    f.data_channels,
            }
            for f in r.frequency_sets
        ],
        "ble_fail_events": [
            {
                "timestamp":    b.timestamp,
                "radio_serial": b.radio_serial,
                "hour":         b.hour,
            }
            for b in r.ble_fail_events
        ],
        "tx_events": [
            {
                "timestamp":    t.timestamp,
                "message_id":   t.message_id,
                "outcome":      t.outcome,
                "radio_serial": t.radio_serial,
            }
            for t in r.tx_events
        ],
        "contacts": r.contacts,
        "grip_messages": [
            {
                "timestamp":      g.timestamp,
                "direction":      g.direction,
                "msg_type":       g.msg_type,
                "msg_type_label": g.msg_type_label,
                "msg_id":         g.msg_id,
                "src_gid":        g.src_gid,
                "dst_gid":        g.dst_gid,
                "app_id":         g.app_id,
                "seq_no":         g.seq_no,
                "is_first_packet": g.is_first_packet,
                "is_ack":         g.is_ack,
                "requires_ack":   g.requires_ack,
                "is_periodic":    g.is_periodic,
                "rep_counter":    g.rep_counter,
                "segment_size":   g.segment_size,
                "hops":           g.hops,
                "rssi":           g.rssi,
                "radio_serial":   g.radio_serial,
            }
            for g in r.grip_messages
        ],
        "grip_transfers": [
            {
                "msg_id":          t.msg_id,
                "radio_serial":    t.radio_serial,
                "start_timestamp": t.start_timestamp,
                "end_timestamp":   t.end_timestamp,
                "delivery_ms":     t.delivery_ms,
                "outcome":         t.outcome,
                "max_rep_counter": t.max_rep_counter,
                "segment_count":   t.segment_count,
            }
            for t in r.grip_transfers
        ],
    }

    # ── ATAK-specific fields ──────────────────────────────────────────────────
    if r.log_format == "atak":
        base["atak_app_launches"] = [
            {
                "launch_timestamp":    a.launch_timestamp,
                "app_version":         a.app_version,
                "build_number":        a.build_number,
                "atak_version":        a.atak_version,
                "device_model":        a.device_model,
                "android_api_version": a.android_api_version,
            }
            for a in r.atak_app_launches
        ]
        base["atak_health_samples"] = [
            {
                "timestamp":                   h.timestamp,
                "serial_number":               h.serial_number,
                "connection_state":            h.connection_state,
                "battery_pct":                 h.battery_pct,
                "is_charging":                 h.is_charging,
                "connection_type":             h.connection_type,
                "mode":                        h.mode,
                "firmware_version":            h.firmware_version,
                "stored_messages":             h.stored_messages,
                "pa_temp_c":                   h.pa_temp_c,
                "pa_temp_f":                   round(h.pa_temp_c * 9 / 5 + 32) if h.pa_temp_c is not None else None,
                "system_temp_c":               h.system_temp_c,
                "system_temp_f":               round(h.system_temp_c * 9 / 5 + 32) if h.system_temp_c is not None else None,
                "transmit_power_differential": h.transmit_power_differential,
                "hardware_version":            h.hardware_version,
                "bootloader_version":          h.bootloader_version,
                "chip_architecture":           h.chip_architecture,
                "error_code":                  h.error_code,
                "gid":                         h.gid,
            }
            for h in r.atak_health_samples
        ]
        base["atak_messages"] = [
            {
                "timestamp":           m.timestamp,
                "log_id":              m.log_id,
                "message_timestamp":   m.message_timestamp,
                "is_sender":           m.is_sender,
                # sender_callsign intentionally NOT serialized — it is an internal
                # fallback source for device.callsign only (see log-field-definitions.md);
                # no UI consumer. device.callsign carries the resolved identity to the UI.
                "sender_gid":          m.sender_gid,
                "delivery_status":     m.delivery_status,
                "segment_count":       m.segment_count,
                "open_segments":       m.open_segments,
                "retry_count":         m.retry_count,
                "delivery_time_ms":    m.delivery_time_ms,
                "message_protocol":    m.message_protocol,
                "message_type":        m.message_type,
                "message_object_type": m.message_object_type,
                "pli_interval":        m.pli_interval,
                "file_name":           m.file_name,
                "receiver_gid":        m.receiver_gid,
                "hop_count":           m.hop_count,
                "rssi":                m.rssi,
                "rssi_is_valid":       m.rssi_is_valid,
                "logging_user_location": m.logging_user_location,
                "transmitted_location":  m.transmitted_location,
                "originator_uuid":     m.originator_uuid,
                "originator_callsign": m.originator_callsign,
            }
            for m in r.atak_messages
        ]
        base["atak_events"] = [
            {
                "timestamp":        e.timestamp,
                "event_type":       e.event_type,
                "serial_number":    e.serial_number,
                "connection_type":  e.connection_type,
                "power_watts":      e.power_watts,
                "pli_interval_sec": e.pli_interval_sec,
                "pli_is_distance":  e.pli_is_distance,
                "pli_auto_send":    e.pli_auto_send,
                "bandwidth_khz":    e.bandwidth_khz,
                "channels":         e.channels,
                "location":         e.location,
                "update_status":    e.update_status,
                "update_time_ms":   e.update_time_ms,
                "relay_mode_enabled": e.relay_mode_enabled,
            }
            for e in r.atak_events
        ]

        # Frequency SET command attempts — raw radio-command layer, distinct
        # from confirmed frequencyUpdated events (see AtakFrequencySetAttempt)
        base["atak_frequency_set_attempts"] = [
            {
                "timestamp": a.timestamp,
                "status":    a.status,
                "action":    a.action,
                "channels":  a.channels,
            }
            for a in r.atak_frequency_set_attempts
        ]

        base["atak_radio_mode_queries"] = [
            {
                "timestamp":          q.timestamp,
                "mode_type":          q.mode_type,
                "value":              q.value,
                "status":             q.status,
                "battery_threshold":  q.battery_threshold,
                "action":             q.action,
            }
            for q in r.atak_radio_mode_queries
        ]

        # SDK Logging 2.0 summary — None if no sdkError records were present
        if r.atak_sdk_error_summary:
            s = r.atak_sdk_error_summary
            base["atak_sdk_error_summary"] = {
                "total_count":       s.total_count,
                "counts_by_tag":     s.counts_by_tag,
                "counts_by_info":    s.counts_by_info,
                "radio_types":       s.radio_types,
                "serial_numbers":    s.serial_numbers,
                "connection_states": s.connection_states,
                "first_timestamp":   s.first_timestamp,
                "last_timestamp":    s.last_timestamp,
                "sample": {
                    "id":               s.sample.id,
                    "timestamp":        s.sample.timestamp,
                    "tags":             s.sample.tags,
                    "platform_type":    s.sample.platform_type,
                    "connection_type":  s.sample.connection_type,
                    "serial_number":    s.sample.serial_number,
                    "address":          s.sample.address,
                    "connection_state": s.sample.connection_state,
                    "personal_gid":     s.sample.personal_gid,
                    "battery_level":    s.sample.battery_level,
                    "firmware_version": s.sample.firmware_version,
                    "radio_type":       s.sample.radio_type,
                    "mcuuuid":          s.sample.mcuuuid,
                    "endorsements":     s.sample.endorsements,
                    "additional_info":  s.sample.additional_info,
                } if s.sample else None,
            }
        else:
            base["atak_sdk_error_summary"] = None

    # ── Relay Manager-specific fields ─────────────────────────────────────────
    if r.log_format == "relay_manager":
        base["relay_manager"] = {
            "subtype":             r.relay_manager_subtype,
            "environment":         r.relay_manager_environment,
            "app_pid":             r.relay_manager_app_pid,
            "ble_address":         r.relay_manager_ble_address,
            "relay_serial":        r.device.radio_serial,
            "health_request_count": len(r.relay_health_requests),
            "health_requests": [
                {
                    "timestamp":          req.timestamp,
                    "internal_timestamp": req.internal_timestamp,
                    "ble_payload":        req.ble_payload,
                }
                for req in r.relay_health_requests
            ],
            "notification_counts": {
                str(code): count
                for code, count in r.relay_manager_notification_counts.items()
            },
            "events": [
                {
                    "timestamp":          ev.timestamp,
                    "internal_timestamp": ev.internal_timestamp,
                    "event_type":         ev.event_type,
                    "raw_message":        ev.raw_message,
                }
                for ev in r.relay_manager_events
            ],
        }

    # ── Computed summaries for the UI ─────────────────────────────────────────
    if r.log_format == "atak":
        atak_received = r.atak_received_messages
        hop_counts = [m.hop_count for m in atak_received if m.hop_count]
        rssi_vals   = [m.rssi for m in atak_received if m.rssi_is_valid]

        # BLE health for ATAK: SDK Logging 2.0 surfaces BLE events as tag combos
        # in counts_by_tag. Any tag containing 'BLE' is counted regardless of
        # severity — fw 3.1.11 (MESMER) uses BLE|DEBUG while fw 3.2.10+ uses
        # ERROR|BLE. Both indicate BLE connectivity events that affect health.
        # When no SDK 2.0 records are present at all, fall back to the count
        # of deviceDisconnected events. A summary with zero BLE entries is a
        # genuine zero, not a reason to fall back.
        if r.atak_sdk_error_summary:
            ble_fail_count = 0
            for tag_key, count in r.atak_sdk_error_summary.counts_by_tag.items():
                tags = tag_key.split("|")
                # Count any tag containing BLE regardless of severity.
                # fw 3.1.11 uses BLE|DEBUG; fw 3.2.10+ uses ERROR|BLE.
                if "BLE" in tags:
                    ble_fail_count += count
        else:
            ble_fail_count = sum(1 for e in r.atak_events if e.event_type == "deviceDisconnected")

        base["summary"] = {
            "total_messages":     len(r.atak_messages),
            "pli_count":          len(r.atak_pli_messages),
            "chat_count":         len(r.atak_chat_messages),
            "sent_count":         len(r.atak_sent_messages),
            "received_count":     len(atak_received),
            "unique_sender_gids": len(r.atak_unique_sender_gids),
            "avg_hop_count":      round(sum(hop_counts) / len(hop_counts), 2) if hop_counts else None,
            "max_hop_count":      max(hop_counts) if hop_counts else None,
            "avg_rssi":           round(sum(rssi_vals) / len(rssi_vals), 1) if rssi_vals else None,
            "peak_temp_c":        max((s.pa_temp_c for s in r.system_samples if s.pa_temp_c), default=None),
            "peak_temp_f":        round(max((s.pa_temp_c for s in r.system_samples if s.pa_temp_c), default=0) * 9 / 5 + 32) if any(s.pa_temp_c for s in r.system_samples) else None,
            "min_battery_pct":    min((h.battery_pct for h in r.atak_health_samples if h.battery_pct is not None), default=None),
            # Full-session minimum, never narrowed by the UI time window. The
            # BatteryMin chart falls back to this when a window excludes all
            # health samples (min_battery_pct → null). Equal to min_battery_pct
            # here; the UI's windowed recompute carries this value over unchanged.
            "min_battery_unfiltered": min((h.battery_pct for h in r.atak_health_samples if h.battery_pct is not None), default=None),
            "session_count":      len(r.atak_app_launches),
            "partially_received": sum(1 for m in r.atak_messages if m.delivery_status == "PARTIALLY_RECEIVED"),
            "negative_delivery_time_count": sum(1 for m in r.atak_messages if m.delivery_time_ms is not None and m.delivery_time_ms < 0),
            "ble_fail_count":     ble_fail_count,
            # SDK Logging 2.0
            "sdk_error_count":      r.atak_sdk_error_summary.total_count if r.atak_sdk_error_summary else 0,
            "radio_types":          r.atak_sdk_error_summary.radio_types if r.atak_sdk_error_summary else [],
            # Radio message queue
            "max_stored_messages":  max((h.stored_messages for h in r.atak_health_samples if h.stored_messages), default=0),
        }

    elif r.log_format == "fw_log":
        fw = r.fw_log_result
        rf = fw.rf_config
        rf_dict = {
            "device_type":      rf.device_type if rf else "",
            "region":           rf.region if rf else 0,
            "tx_power":         rf.tx_power if rf else 0,
            "bit_rate":         rf.bit_rate if rf else 0,
            "frequencies_hz":   rf.frequencies_hz if rf else [],
            "control_channels": rf.control_channels if rf else [],
            "data_channels":    rf.data_channels if rf else [],
        }
        energy = fw.energy_samples or []
        energy_summary = {
            "avg_dbm": round(sum(energy)/len(energy), 1) if energy else None,
            "min_dbm": min(energy) if energy else None,
            "max_dbm": max(energy) if energy else None,
            "sample_count": len(energy),
        }
        rssi_by_ch = {}
        for s in (fw.rssi_samples or []):
            ch = str(s.channel)
            rssi_by_ch.setdefault(ch, {"avgs":[],"mins":[],"maxs":[]})
            rssi_by_ch[ch]["avgs"].append(s.avg_dbm)
            rssi_by_ch[ch]["mins"].append(s.min_dbm)
            rssi_by_ch[ch]["maxs"].append(s.max_dbm)
        rssi_summary = {
            ch: {
                "avg_dbm": round(sum(v["avgs"])/len(v["avgs"]), 1),
                "min_dbm": min(v["mins"]),
                "max_dbm": max(v["maxs"]),
                "sample_count": len(v["avgs"]),
            } for ch, v in rssi_by_ch.items()
        }
        rt = fw.routing
        buckets = [
            {"bucket_index": b.bucket_index, "hrs_start": b.hrs_start,
             "hrs_end": b.hrs_end, "rx": b.rx, "relayed": b.relayed, "tx": b.tx}
            for b in (fw.buckets or [])
        ]
        base["fw_log"] = {
            "origin_hash":         fw.origin_hash,
            "fw_format_version":   fw.fw_format_version,
            "rf_config":           rf_dict,
            "first_ts_ms":         fw.first_ts_ms,
            "last_ts_ms":          fw.last_ts_ms,
            "duration_ms":         fw.duration_ms,
            "buckets":             buckets,
            "rssi_summary":        rssi_summary,
            "energy_summary":      energy_summary,
            "routing": {"transmit": rt.transmit if rt else 0,
                        "echo": rt.echo if rt else 0,
                        "vine": rt.vine if rt else 0,
                        "flood": rt.flood if rt else 0,
                        "skip_rx": rt.skip_rx if rt else 0,
                        "skip_tx": rt.skip_tx if rt else 0},
            "neighbor_hashes":     fw.neighbor_hashes,
            "rhc_poll_count":      fw.rhc_poll_count,
            "battery_error_count": fw.battery_error_count,
            "error_counts":        fw.error_counts,
            "error_messages":      fw.error_messages,
            "warn_counts":         fw.warn_counts,
            "warn_messages":       fw.warn_messages,
            "total_lines":         fw.total_lines,
            "parsed_lines":        fw.parsed_lines,
            "skipped_debug":       fw.skipped_debug,
        }
        base["summary"] = {
            "origin_hash":         fw.origin_hash,
            "duration_ms":         fw.duration_ms,
            "rhc_poll_count":      fw.rhc_poll_count,
            "battery_error_count": fw.battery_error_count,
            "total_errors":        sum(fw.error_counts.values()),
            "total_warns":         sum(fw.warn_counts.values()),
            "neighbor_count":      len(fw.neighbor_hashes),
            "bucket_count":        len(fw.buckets),
            "routing_transmit":    rt.transmit if rt else 0,
            "routing_echo":        rt.echo if rt else 0,
            "routing_vine":        rt.vine if rt else 0,
            "energy_avg_dbm":      energy_summary.get("avg_dbm"),
            "rssi_ch0_avg_dbm":    rssi_summary.get("0", {}).get("avg_dbm"),
            "rssi_ch1_avg_dbm":    rssi_summary.get("1", {}).get("avg_dbm"),
        }

    elif r.log_format == "relay_manager":
        # Compute average polling interval for the summary
        avg_interval_sec: float | None = None
        reqs = r.relay_health_requests
        if len(reqs) >= 2:
            try:
                from datetime import datetime as _dt
                _fmt = "%Y-%m-%d %H:%M:%S.%f"
                dts = [_dt.strptime(req.timestamp, _fmt) for req in reqs]
                dts.sort()
                span = (dts[-1] - dts[0]).total_seconds()
                avg_interval_sec = round(span / (len(dts) - 1), 1)
            except (ValueError, ZeroDivisionError):
                pass

        ncounts = r.relay_manager_notification_counts
        base["summary"] = {
            "health_request_count":     len(reqs),
            "avg_interval_sec":         avg_interval_sec,
            "subtype":                  r.relay_manager_subtype,
            "environment":              r.relay_manager_environment,
            "response_ready_count":     sum(
                1 for e in r.relay_manager_events
                if e.event_type == "health_response_ready"
            ),
            "device_alert_count":       sum(
                1 for e in r.relay_manager_events
                if e.event_type == "device_alert"
            ),
            "battery_event_count":      sum(
                1 for e in r.relay_manager_events
                if e.event_type == "battery_state_changed"
            ),
            "dominant_notification_type": max(ncounts, key=ncounts.get) if ncounts else None,
            "total_notifications":       sum(ncounts.values()),
        }

    else:
        # GRIP incoming RSSI is the genuine RF signal for diagnostic/rsdk. It feeds
        # both the RSSI tab (grip_avg_rssi) and the Health Score RSSI dimension
        # (avg_rssi). diagnostic logs carry no GRIP messages, so avg_rssi stays None
        # and the Health tab shows RSSI as N/A (excluded from the score denominator).
        grip_rssi_vals = [g.rssi for g in r.grip_messages if g.rssi is not None]
        grip_rssi_avg = round(sum(grip_rssi_vals) / len(grip_rssi_vals), 1) if grip_rssi_vals else None

        base["summary"] = {
            "total_messages":     len(r.received_messages),
            "pli_count":          len(r.pli_messages),
            "chat_count":         len(r.chat_messages),
            "unique_originators": len(r.unique_originators),
            "avg_hop_count":      round(sum(r.hop_counts) / len(r.hop_counts), 2) if r.hop_counts else None,
            "max_hop_count":      max(r.hop_counts) if r.hop_counts else None,
            "peak_temp_c":        max((s.pa_temp_c for s in r.system_samples if s.pa_temp_c), default=None),
            "peak_temp_f":        round(max((s.pa_temp_c for s in r.system_samples if s.pa_temp_c), default=0) * 9 / 5 + 32) if any(s.pa_temp_c for s in r.system_samples) else None,
            "min_battery_pct":    min((s.battery_pct for s in r.system_samples if s.battery_pct), default=None),
            # Health Score RSSI dimension input — GRIP incoming RSSI (None for diagnostic)
            "avg_rssi":           grip_rssi_avg,
            "ble_fail_count":     len(r.ble_fail_events),
            "session_count":      len(r.session_gaps) + 1,
            "final_chat_sent":    r.final_message_counts.chat_sent if r.final_message_counts else None,
            "final_chat_recv":    r.final_message_counts.chat_received if r.final_message_counts else None,
            "contact_count":      len(r.contacts),
            "contact_names":      sorted(set(r.contacts.values())),
            # Radio message queue — only ATAK device health carries storedMessages;
            # SystemSample (diagnostic/rsdk/relay_manager) has no such field.
            "max_stored_messages": 0,
            "tx_final_ack":       sum(1 for t in r.tx_events if t.outcome == "final_ack"),
            "tx_nack":            sum(1 for t in r.tx_events if t.outcome == "nack"),
            "tx_timeout":         sum(1 for t in r.tx_events if t.outcome == "timeout"),
            # GRIP transfer summary
            "grip_transfer_count":     len(r.grip_transfers),
            "grip_delivered_count":    sum(1 for t in r.grip_transfers if t.outcome == "delivered"),
            "grip_cancelled_count":    sum(1 for t in r.grip_transfers if t.outcome == "cancelled"),
            "grip_incomplete_count":   sum(1 for t in r.grip_transfers if t.outcome == "incomplete"),
            "grip_avg_delivery_ms":    round(
                sum(t.delivery_ms for t in r.grip_transfers if t.delivery_ms is not None) /
                max(1, sum(1 for t in r.grip_transfers if t.delivery_ms is not None)), 1
            ) if any(t.delivery_ms is not None for t in r.grip_transfers) else None,
            "grip_retransmit_count":   sum(1 for g in r.grip_messages if g.rep_counter > 0),
            "grip_broadcast_count":    sum(1 for g in r.grip_messages if g.msg_type == 2 and g.direction == "outgoing"),
            "grip_private_count":      sum(1 for g in r.grip_messages if g.msg_type == 0 and g.direction == "outgoing"),
            # Incoming hop/rssi data (genuine RF routing data)
            "grip_avg_hops":  round(
                sum(g.hops for g in r.grip_messages if g.hops is not None) /
                max(1, sum(1 for g in r.grip_messages if g.hops is not None)), 2
            ) if any(g.hops is not None for g in r.grip_messages) else None,
            "grip_avg_rssi":  grip_rssi_avg,
        }

    return base


@router.post("/")
async def parse_logs(files: list[UploadFile] = File(...)) -> dict:
    """
    Upload one or more log files. Returns an array of parsed results.

    Supports goTenna Pro+ diagnostic logs, RSDK iOS/Android logs,
    ATAK plug-in logs (regular and enhanced), and Relay Manager logs
    (networkPolling and scheduledHealthRequest sub-types).

    Format is auto-detected from filename and content.
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded.")
    if len(files) > 20:
        raise HTTPException(status_code=400, detail="Maximum 20 files per request.")

    results = []
    for upload in files:
        content = await upload.read()
        text = content.decode("utf-8", errors="replace")

        fmt = _detect_format(upload.filename or "", text)

        # newline="" writes the decoded text verbatim. Without it, text mode
        # translates every "\n" to os.linesep on Windows, turning a CRLF upload's
        # "\r\n" into "\r\r\n"; Path.read_text()'s universal-newline decode then
        # reads that back as "\n\n", which prematurely splits the blank-line-
        # delimited diagnostic format and drops every Received Message block.
        suffix = ".log" if fmt == "atak" else ".txt"
        with tempfile.NamedTemporaryFile(
            suffix=suffix, delete=False, mode="w", encoding="utf-8", newline=""
        ) as tmp:
            tmp.write(text)
            tmp_path = Path(tmp.name)

        try:
            if fmt == "fw_log":
                result = parse_fw_log(tmp_path)
            elif fmt == "rsdk":
                result = parse_rsdk_log(tmp_path)
            elif fmt == "atak":
                result = parse_atak_log(tmp_path)
            elif fmt == "relay_manager":
                result = parse_relay_manager_log(tmp_path)
            else:
                result = parse_diagnostic_log(tmp_path)
            result.source_filename = upload.filename or result.source_filename
        finally:
            tmp_path.unlink(missing_ok=True)

        results.append(_result_to_dict(result))

    return {"results": results, "count": len(results)}
