const C = { accent:'#00d4ff', green:'#00e5a0', yellow:'#ffd166', red:'#ff4757', muted:'#4a6080', purple:'#c77dff' }

// Format color per log type
const FMT_COLOR = {
  diagnostic: '#00d4ff',
  rsdk:       '#ffd166',
  atak:       '#c77dff',
}

function Stat({ label, value, color = '#c8ddf4', sub }) {
  return (
    <div style={{ background: '#080c18', borderRadius: 5, padding: '8px 11px' }}>
      <div style={{ fontFamily: 'var(--mono)', fontSize: 8, color: C.muted, textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 3 }}>{label}</div>
      <div style={{ fontFamily: "'Barlow Condensed', sans-serif", fontSize: 20, fontWeight: 700, color, lineHeight: 1 }}>{value ?? '—'}</div>
      {sub && <div style={{ fontFamily: 'var(--mono)', fontSize: 8, color: '#2a3a52', marginTop: 2 }}>{sub}</div>}
    </div>
  )
}

function WarningBadge({ text }) {
  return (
    <div style={{ fontFamily: 'var(--mono)', fontSize: 8, color: C.yellow, background: '#ffd16615', border: '1px solid #ffd16630', borderRadius: 3, padding: '2px 7px', display: 'inline-block', marginTop: 4 }}>
      ⚠ {text}
    </div>
  )
}

export default function DeviceSummary({ result }) {
  const d   = result.device  || {}
  const s   = result.summary || {}
  const fmt = result.log_format
  const fmtColor = FMT_COLOR[fmt] || C.accent

  const tempF = s.peak_temp_f
  const tempColor = tempF >= 131 ? C.red : tempF >= 113 ? C.yellow : C.green

  const isAtak = fmt === 'atak'
  const isRsdk = fmt === 'rsdk'

  return (
    <div style={{
      background: 'var(--panel)', border: '1px solid var(--border)',
      borderLeft: `3px solid ${fmtColor}`, borderRadius: 8, padding: '14px 16px',
    }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12, flexWrap: 'wrap' }}>
        <div style={{ fontFamily: "'Barlow Condensed', sans-serif", fontSize: 16, fontWeight: 700, letterSpacing: '0.05em', textTransform: 'uppercase', color: fmtColor }}>
          {d.callsign || result.source_filename}
        </div>
        <div style={{ fontFamily: 'var(--mono)', fontSize: 8, color: C.muted }}>
          {fmt?.toUpperCase()} · {d.platform?.toUpperCase()} · {d.device_model}
        </div>
        {d.app_version && (
          <div style={{ marginLeft: 'auto', fontFamily: 'var(--mono)', fontSize: 9, color: C.green, border: '1px solid #00e5a030', padding: '1px 7px', borderRadius: 3 }}>
            v{d.app_version}{d.build_number ? ` b${d.build_number}` : ''}
          </div>
        )}
      </div>

      {/* Stats grid — shared */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(100px, 1fr))', gap: 6 }}>
        <Stat label="Messages"  value={s.total_messages}  color={fmtColor} />
        <Stat label="PLI"       value={s.pli_count}        color={C.muted}  />
        <Stat label="Chat"      value={s.chat_count}       color={fmtColor} />

        {/* diagnostic / rsdk */}
        {!isAtak && (
          <Stat label="Originators" value={s.unique_originators} color={fmtColor} />
        )}

        {/* ATAK-specific */}
        {isAtak && (
          <Stat label="Senders" value={s.unique_sender_gids} color={fmtColor}
                sub="unique GIDs" />
        )}
        {isAtak && (
          <Stat label="Sent"     value={s.sent_count}     color={fmtColor} />
        )}
        {isAtak && (
          <Stat label="Received" value={s.received_count} color={fmtColor} />
        )}
        {isAtak && s.session_count > 1 && (
          <Stat label="Launches" value={s.session_count} color={C.yellow}
                sub="app launches" />
        )}

        <Stat label="Avg Hops"  value={s.avg_hop_count}  color={fmtColor} />
        <Stat label="Max Hops"  value={s.max_hop_count}  color={fmtColor} />
        <Stat label="Peak Temp" value={tempF ? `${tempF}°F` : null} color={tempColor} />
        <Stat
          label="Min Batt"
          value={s.min_battery_pct != null ? `${s.min_battery_pct}%` : null}
          color={s.min_battery_pct < 30 ? C.red : s.min_battery_pct < 50 ? C.yellow : C.green}
        />

        {/* RSDK only */}
        {isRsdk && (
          <Stat label="BLE Fails" value={s.ble_fail_count} color={s.ble_fail_count > 0 ? C.red : C.green} />
        )}

        {/* ATAK only — delivery quality */}
        {isAtak && s.partially_received > 0 && (
          <Stat label="Partial RX" value={s.partially_received} color={C.yellow}
                sub="incomplete msgs" />
        )}

        {d.radio_firmware && (
          <Stat label="Radio FW" value={d.radio_firmware} color={C.muted} />
        )}
        {d.radio_serial && (
          <Stat label="Serial" value={d.radio_serial} color={C.muted} />
        )}
      </div>

      {/* ATAK clock skew warning */}
      {isAtak && s.negative_delivery_time_count > 0 && (
        <div style={{ marginTop: 8 }}>
          <WarningBadge text={`${s.negative_delivery_time_count} msgs with negative delivery time (clock skew)`} />
        </div>
      )}

      {/* ATAK avg RSSI */}
      {isAtak && s.avg_rssi != null && (
        <div style={{ marginTop: 6, fontFamily: 'var(--mono)', fontSize: 9, color: C.muted }}>
          Avg RSSI (received): <span style={{ color: s.avg_rssi > -70 ? C.green : s.avg_rssi > -90 ? C.yellow : C.red }}>{s.avg_rssi} dBm</span>
        </div>
      )}

      {/* Session info */}
      {result.session_start && (
        <div style={{ marginTop: 10, fontFamily: 'var(--mono)', fontSize: 9, color: C.muted }}>
          {result.session_start?.slice(0, 16)} → {result.session_end?.slice(0, 16)}
          {result.session_gaps?.length > 0 && (
            <span style={{ color: C.yellow, marginLeft: 8 }}>
              {result.session_gaps.length} gap{result.session_gaps.length > 1 ? 's' : ''}
            </span>
          )}
        </div>
      )}

      {/* GID */}
      {d.gid && (
        <div style={{ marginTop: 4, fontFamily: 'var(--mono)', fontSize: 8, color: '#2a3a52' }}>
          GID: {d.gid}
        </div>
      )}

      {/* Parse errors */}
      {result.parse_errors?.length > 0 && (
        <div style={{ marginTop: 8, fontFamily: 'var(--mono)', fontSize: 8, color: C.red }}>
          ⚠ {result.parse_errors.length} parse warning{result.parse_errors.length > 1 ? 's' : ''}
        </div>
      )}
    </div>
  )
}
