import { useEffect, useState, useSyncExternalStore } from 'react'
import { api } from './api.js'
import { connectRealtime } from './realtime.js'

import { SessionContext } from './session-context.js'

export function SessionProvider({ children, client = api, Socket }) {
  const session = useSyncExternalStore(client.subscribe, client.getSession)
  const [ready, setReady] = useState(!session)
  const [error, setError] = useState(null)
  const [revision, setRevision] = useState(0)
  const [event, setEvent] = useState(null)
  const [connection, setConnection] = useState('conectando')
  useEffect(() => {
    let active = true
    client.restore().catch((err) => { if (active) setError(err) }).finally(() => { if (active) setReady(true) })
    return () => { active = false }
  }, [client])
  useEffect(() => {
    if (!session?.usuario.id || !ready) return
    const base = new URL(import.meta.env.VITE_API_BASE_URL || '/api', window.location.origin)
    base.protocol = base.protocol === 'https:' ? 'wss:' : 'ws:'
    base.pathname = `${base.pathname.replace(/\/$/, '')}/ws/estado`
    return connectRealtime({ api: client, Socket, url: base.href, onStatus: setConnection, onEvent: (message) => { setEvent(message); setRevision((value) => value + 1) } })
  }, [session?.usuario.id, ready, client, Socket])
  function invalidate() { setRevision((value) => value + 1) }
  useEffect(() => {
    window.addEventListener('thesora:refresh', invalidate)
    return () => window.removeEventListener('thesora:refresh', invalidate)
  }, [])
  return <SessionContext.Provider value={{ session, user: session?.usuario, ready, error, client, revision, event, connection, invalidate }}>{children}</SessionContext.Provider>
}
