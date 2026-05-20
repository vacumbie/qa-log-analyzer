import { useState } from 'react'
import FileUpload from './components/FileUpload.jsx'
import DeviceSummary from './components/DeviceSummary.jsx'
import DataPointSelector from './components/DataPointSelector.jsx'
import ChartPanel from './components/ChartPanel.jsx'
import useLogData from './hooks/useLogData.js'

export default function App() {
  const { results, loading, error, parseFiles, clearResults } = useLogData()
  const [selectedPoints, setSelectedPoints] = useState([])
  const [activeDevice, setActiveDevice] = useState(null)

  const hasResults = results.length > 0

  return (
    <div style={{ display: 'flex', flexDirection: 'column', minHeight: '100vh' }}>

      {/* Header */}
      <header style={{
        padding: '16px 28px',
        borderBottom: '1px solid var(--border2)',
        background: 'var(--bg2)',
        display: 'flex', alignItems: 'center', gap: 16,
      }}>
        <div>
          <div style={{ fontSize: 9, fontFamily: 'var(--mono)', color: 'var(--muted)', letterSpacing: '0.15em', textTransform: 'uppercase', marginBottom: 2 }}>
            goTenna Mesh · Log Analysis
          </div>
          <div style={{ fontSize: 22, fontWeight: 800, letterSpacing: '0.06em', textTransform: 'uppercase', color: '#e8f4ff' }}>
            Log <span style={{ color: 'var(--accent)' }}>Analyzer</span>
          </div>
        </div>
        {hasResults && (
          <button
            onClick={clearResults}
            style={{
              marginLeft: 'auto', background: 'none', border: '1px solid var(--border2)',
              color: 'var(--muted)', borderRadius: 5, padding: '6px 14px',
              cursor: 'pointer', fontFamily: 'var(--mono)', fontSize: 10,
              letterSpacing: '0.06em', textTransform: 'uppercase',
            }}
          >
            Clear / New Session
          </button>
        )}
      </header>

      {/* Main */}
      <main style={{ flex: 1, padding: '24px 28px', display: 'flex', flexDirection: 'column', gap: 20 }}>

        {/* Upload zone — always visible when no results */}
        {!hasResults && (
          <FileUpload onFiles={parseFiles} loading={loading} error={error} />
        )}

        {/* Results layout */}
        {hasResults && (
          <>
            {/* Device selector strip */}
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              {results.map((r, i) => (
                <button
                  key={i}
                  onClick={() => setActiveDevice(activeDevice === i ? null : i)}
                  style={{
                    background: activeDevice === i ? 'var(--accent)20' : 'var(--panel)',
                    border: `1px solid ${activeDevice === i ? 'var(--accent)' : 'var(--border)'}`,
                    color: activeDevice === i ? 'var(--accent)' : 'var(--text)',
                    borderRadius: 5, padding: '7px 14px', cursor: 'pointer',
                    fontFamily: 'var(--mono)', fontSize: 10, letterSpacing: '0.06em',
                    textTransform: 'uppercase',
                  }}
                >
                  {r.device?.callsign || r.source_filename}
                  <span style={{ marginLeft: 6, opacity: 0.5, fontSize: 9 }}>
                    {r.log_format}
                  </span>
                </button>
              ))}
            </div>

            {/* Device summary cards */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: 12 }}>
              {(activeDevice !== null ? [results[activeDevice]] : results).map((r, i) => (
                <DeviceSummary key={i} result={r} />
              ))}
            </div>

            {/* Data point selector + chart */}
            <DataPointSelector
              results={activeDevice !== null ? [results[activeDevice]] : results}
              selected={selectedPoints}
              onChange={setSelectedPoints}
            />
            <ChartPanel
              results={activeDevice !== null ? [results[activeDevice]] : results}
              selectedPoints={selectedPoints}
            />
          </>
        )}
      </main>
    </div>
  )
}
