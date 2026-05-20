import { useCallback } from 'react'
import { useDropzone } from 'react-dropzone'

export default function FileUpload({ onFiles, loading, error }) {
  const onDrop = useCallback((accepted) => {
    if (accepted.length > 0) onFiles(accepted)
  }, [onFiles])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'text/plain': ['.txt'] },
    multiple: true,
    disabled: loading,
  })

  return (
    <div style={{ maxWidth: 640, margin: '40px auto', width: '100%' }}>
      <div
        {...getRootProps()}
        style={{
          border: `2px dashed ${isDragActive ? 'var(--accent)' : 'var(--border2)'}`,
          borderRadius: 10,
          padding: '52px 32px',
          textAlign: 'center',
          cursor: loading ? 'not-allowed' : 'pointer',
          background: isDragActive ? 'var(--accent)08' : 'var(--panel)',
          transition: 'border-color 0.15s, background 0.15s',
        }}
      >
        <input {...getInputProps()} />
        <div style={{ fontSize: 36, marginBottom: 12 }}>📂</div>
        <div style={{ fontSize: 16, fontWeight: 700, color: '#c8ddf4', marginBottom: 6 }}>
          {loading ? 'Parsing…' : isDragActive ? 'Drop files here' : 'Drop log files or click to browse'}
        </div>
        <div style={{ fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--muted)' }}>
          Accepts .txt files · diagnostic and RSDK formats · multiple files supported
        </div>
      </div>

      {error && (
        <div style={{
          marginTop: 12, padding: '10px 14px', background: 'var(--red)15',
          border: '1px solid var(--red)40', borderRadius: 6,
          fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--red)',
        }}>
          ⚠ {error}
        </div>
      )}
    </div>
  )
}
