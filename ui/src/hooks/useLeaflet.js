import { useEffect, useState } from 'react'

// Leaflet is loaded from the unpkg CDN, not npm — see CLAUDE.md "Do not add npm
// packages". Both maps in the app (Hop Count Map and the TAK position map) share
// this loader, so the library is fetched once per page rather than once per map.
const LEAFLET_VERSION = '1.9.4'
const CSS_ID = 'leaflet-cdn-css'
const JS_ID = 'leaflet-cdn-js'

/**
 * Returns true once window.L is available.
 *
 * Both callers can mount at the same time, so the script tag is looked up by id
 * before being created — otherwise the second map would inject a duplicate
 * <script> and re-fetch the library.
 */
export function useLeaflet() {
  const [ready, setReady] = useState(!!window.L)

  useEffect(() => {
    if (window.L) { setReady(true); return }

    if (!document.getElementById(CSS_ID)) {
      const link = document.createElement('link')
      link.id = CSS_ID
      link.rel = 'stylesheet'
      link.href = `https://unpkg.com/leaflet@${LEAFLET_VERSION}/dist/leaflet.css`
      document.head.appendChild(link)
    }

    let script = document.getElementById(JS_ID)
    if (!script) {
      script = document.createElement('script')
      script.id = JS_ID
      script.src = `https://unpkg.com/leaflet@${LEAFLET_VERSION}/dist/leaflet.js`
      document.head.appendChild(script)
    }

    const onLoad = () => setReady(true)
    script.addEventListener('load', onLoad)
    return () => script.removeEventListener('load', onLoad)
  }, [])

  return ready
}
