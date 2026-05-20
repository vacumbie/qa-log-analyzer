import { useState, useCallback } from 'react'

export default function useLogData() {
  const [results, setResults]   = useState([])
  const [loading, setLoading]   = useState(false)
  const [error,   setError]     = useState(null)

  const parseFiles = useCallback(async (files) => {
    setLoading(true)
    setError(null)

    const formData = new FormData()
    for (const file of files) {
      formData.append('files', file)
    }

    try {
      const res = await fetch('/parse/', {
        method: 'POST',
        body: formData,
      })
      if (!res.ok) {
        const detail = await res.json().catch(() => ({}))
        throw new Error(detail?.detail || `Server error ${res.status}`)
      }
      const data = await res.json()
      setResults(prev => [...prev, ...data.results])
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [])

  const clearResults = useCallback(() => {
    setResults([])
    setError(null)
  }, [])

  return { results, loading, error, parseFiles, clearResults }
}
