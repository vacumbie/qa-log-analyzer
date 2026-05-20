const C = { accent:'#00d4ff', green:'#00e5a0', yellow:'#ffd166', red:'#ff4757', muted:'#4a6080' }

function Stat({ label, value, color = '#c8ddf4', sub }) {
  return (
    <div style={{ background: '#080c18', borderRadius: 5, padding: '8px 11px' }}>
      <div style={{ fontFamily: 'var(--mono)', fontSize: 8, color: C.muted, textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 3 }}>{label}</div>
      <div style={{ fontFamily: "'Barlow Condensed', sans-serif", fontSize: 20, fontWeight: 700, color, lineHeight: 1 }}>{value ?? '—'}</div>
      {sub && <div style={{ fontFamily: 'var(--mono)', fontSize: 8, color: '#2a3a52', marginTop: 2 }}>{sub}</div>}
    </div>
  )
}

export default function DeviceSummary({ result }) {
  const d  = result.device   || {}
  const s  = result.summary  || {}
  const fmtColor = result.log_format === 'rsdk' ? C.yellow : C.accent

  const tempF = s.peak_temp_f
  const tempColor = tempF >= 131 ? C.red : tempF >= 113 ? C.yellow : C.green

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
          {result.log_format?.toUpperCase()} · {d.device_model}
        </div>
        {d.app_version && (
          <div style={{ marginLeft: 'auto', fontFamily: 'var(--mono)', fontSize: 9, color: C.green, border: '1px solid #00e5a030', padding: '1px 7px', borderRadius: 3 }}>
            v{d.app_version} b{d.build_number}
          </div>
        )}
      </div>

      {/* Stats grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(100px, 1fr))', gap: 6 }}>
        <Stat label="Messages"   value={s.total_messages}    color={fmtColor} />
        <Stat label="PLI"        value={s.pli_count}          color={C.muted}  />
        <Stat label="Chat"       value={s.chat_count}         color={fmtColor} />
        <Stat label="Originators" value={s.unique_originators} color={fmtColor} />
        <Stat label="Avg Hops"   value={s.avg_hop_count}      color={fmtColor} />
        <Stat label="Peak Temp"  value={tempF ? `${tempF}°F` : null} color={tempColor} />
        <Stat label="Min Batt"   value={s.min_battery_pct != null ? `${s.min_battery_pct}%` : null}
              color={s.min_battery_pct < 30 ? C.red : s.min_battery_pct < 50 ? C.yellow : C.green} />
        {result.log_format === 'rsdk' && (
          <Stat label="BLE Fails" value={s.ble_fail_count} color={s.ble_fail_count > 0 ? C.red : C.green} />
        )}
        {d.radio_firmware && (
          <Stat label="Radio FW" value={d.radio_firmware} color={C.muted} />
        )}
      </div>

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

      {/* Parse errors */}
      {result.parse_errors?.length > 0 && (
        <div style={{ marginTop: 8, fontFamily: 'var(--mono)', fontSize: 8, color: C.red }}>
          ⚠ {result.parse_errors.length} parse warning{result.parse_errors.length > 1 ? 's' : ''}
        </div>
      )}
    </div>
  )
}
