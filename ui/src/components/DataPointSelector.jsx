// Available data points — grouped by category.
// Each entry defines what to chart and how to extract it from a ParseResult.
export const DATA_POINTS = [
  // ── Thermal ──────────────────────────────────────────────────────────────
  { id: 'temp_over_time',        group: 'Thermal',   label: 'PA Temp Over Time (°F)',          formats: ['diagnostic','rsdk','atak'] },
  { id: 'temp_peak',             group: 'Thermal',   label: 'Peak PA Temp per Device',         formats: ['diagnostic','rsdk','atak'] },

  // ── Battery ───────────────────────────────────────────────────────────────
  { id: 'battery_over_time',     group: 'Battery',   label: 'Battery % Over Time',             formats: ['diagnostic','rsdk','atak'] },
  { id: 'battery_min',           group: 'Battery',   label: 'Min Battery per Device',          formats: ['diagnostic','rsdk','atak'] },

  // ── Hop Count ─────────────────────────────────────────────────────────────
  { id: 'hop_distribution',      group: 'Hop Count', label: 'Hop Count Distribution',          formats: ['diagnostic','atak'] },
  { id: 'hop_avg',               group: 'Hop Count', label: 'Avg Hop Count per Device',        formats: ['diagnostic','atak'] },

  // ── RSSI ──────────────────────────────────────────────────────────────────
  { id: 'rssi_by_hop',           group: 'RSSI',      label: 'RSSI by Hop Count',               formats: ['diagnostic','atak'] },
  { id: 'rssi_avg_device',       group: 'RSSI',      label: 'Avg RSSI per Device',             formats: ['diagnostic','atak'] },

  // ── PLI ───────────────────────────────────────────────────────────────────
  { id: 'pli_intervals',         group: 'PLI',       label: 'PLI Intervals per Originator',    formats: ['diagnostic'] },
  { id: 'pli_vs_chat',           group: 'PLI',       label: 'PLI vs Chat Message Split',       formats: ['diagnostic','atak'] },

  // ── TX / RX ───────────────────────────────────────────────────────────────
  { id: 'chat_sent_recv',        group: 'TX / RX',   label: 'Chat Sent vs Received',           formats: ['diagnostic'] },
  { id: 'broadcast_vs_1to1',     group: 'TX / RX',   label: 'Broadcast vs Private Received',   formats: ['diagnostic'] },
  { id: 'tx_outcomes',           group: 'TX / RX',   label: 'TX Outcomes (ACK/NACK/Timeout)',  formats: ['rsdk'] },

  // ── ATAK Messages ─────────────────────────────────────────────────────────
  { id: 'atak_delivery_status',  group: 'ATAK',      label: 'Delivery Status Breakdown',       formats: ['atak'] },
  { id: 'atak_message_types',    group: 'ATAK',      label: 'Message Types Breakdown',         formats: ['atak'] },
  { id: 'atak_sent_vs_received', group: 'ATAK',      label: 'Sent vs Received',                formats: ['atak'] },
  { id: 'atak_partial_received', group: 'ATAK',      label: 'Partially Received Messages',     formats: ['atak'] },

  // ── ATAK Health ───────────────────────────────────────────────────────────
  { id: 'atak_connection_state', group: 'ATAK',      label: 'Connection State Over Time',      formats: ['atak'] },
  { id: 'atak_events_timeline',  group: 'ATAK',      label: 'Device Events Timeline',          formats: ['atak'] },

  // ── BLE (RSDK only) ───────────────────────────────────────────────────────
  { id: 'ble_fails_total',       group: 'BLE',       label: 'BLE Failures per Device',         formats: ['rsdk'] },
  { id: 'ble_fails_hourly',      group: 'BLE',       label: 'BLE Failures by Hour',            formats: ['rsdk'] },

  // ── Sessions ──────────────────────────────────────────────────────────────
  { id: 'session_lengths',       group: 'Sessions',  label: 'Session Lengths',                 formats: ['diagnostic','rsdk','atak'] },
]

const GROUP_COLORS = {
  'Thermal':  '#ff6b35',
  'Battery':  '#00e5a0',
  'Hop Count':'#00d4ff',
  'RSSI':     '#c77dff',
  'PLI':      '#ffd166',
  'TX / RX':  '#ff4757',
  'ATAK':     '#c77dff',
  'BLE':      '#ff6b9d',
  'Sessions': '#4a90e2',
}

export default function DataPointSelector({ results, selected, onChange }) {
  // Determine which formats are present
  const formats = [...new Set(results.map(r => r.log_format))]

  // Filter to relevant points
  const available = DATA_POINTS.filter(dp =>
    dp.formats.some(f => formats.includes(f))
  )

  const groups = [...new Set(available.map(dp => dp.group))]

  const toggle = (id) => {
    onChange(prev =>
      prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]
    )
  }

  const selectAll  = () => onChange(available.map(dp => dp.id))
  const selectNone = () => onChange([])

  return (
    <div style={{ background: 'var(--panel)', border: '1px solid var(--border)', borderRadius: 8, padding: '14px 18px' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
        <div style={{ fontFamily: "'Barlow Condensed', sans-serif", fontSize: 15, fontWeight: 700, letterSpacing: '0.05em', textTransform: 'uppercase', color: '#c8ddf4' }}>
          Data Points
        </div>
        <div style={{ fontFamily: 'var(--mono)', fontSize: 9, color: 'var(--muted)' }}>
          Select what to chart
        </div>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 6 }}>
          {['All', 'None'].map(label => (
            <button key={label}
              onClick={label === 'All' ? selectAll : selectNone}
              style={{
                background: 'none', border: '1px solid var(--border2)',
                color: 'var(--muted)', borderRadius: 4, padding: '3px 10px',
                cursor: 'pointer', fontFamily: 'var(--mono)', fontSize: 9,
              }}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {groups.map(group => {
        const points = available.filter(dp => dp.group === group)
        const color  = GROUP_COLORS[group] || '#888'
        return (
          <div key={group} style={{ marginBottom: 10 }}>
            <div style={{ fontFamily: 'var(--mono)', fontSize: 9, color, textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 5 }}>
              {group}
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5 }}>
              {points.map(dp => {
                const active = selected.includes(dp.id)
                return (
                  <button
                    key={dp.id}
                    onClick={() => toggle(dp.id)}
                    style={{
                      background: active ? `${color}20` : '#080c18',
                      border: `1px solid ${active ? color : 'var(--border)'}`,
                      color: active ? color : 'var(--muted)',
                      borderRadius: 4, padding: '4px 10px', cursor: 'pointer',
                      fontFamily: 'var(--mono)', fontSize: 9,
                      transition: 'all 0.1s',
                    }}
                  >
                    {dp.label}
                  </button>
                )
              })}
            </div>
          </div>
        )
      })}
    </div>
  )
}
