export function connectRealtime({ api, Socket = WebSocket, url, onEvent, onStatus }) {
  let stopped = false
  let socket
  let retryTimer
  let renewTimer
  let attempts = 0
  async function connect(renew = false) {
    if (stopped || !api.getSession()) return
    onStatus('conectando')
    try {
      if (renew || (api.getSession().expiresAt || 0) - Date.now() < 30000) await api.refresh()
      if (stopped || !api.getSession()) return
      socket = new Socket(url)
      socket.onopen = () => {
        attempts = 0
        onStatus('conectado')
        onEvent({ tipo: 'sincronizar' })
        // Refresh renews the HttpOnly session cookie used by the next handshake.
        renewTimer = setTimeout(() => { socket.close(); }, Math.max(1000, (api.getSession()?.expiresAt || Date.now()) - Date.now() - 15000))
      }
      socket.onmessage = ({ data }) => {
        try { const event = JSON.parse(data); if (event.tipo) onEvent(event) } catch { /* Ignore malformed transport messages. */ }
      }
      socket.onerror = () => onStatus('desconectado')
      socket.onclose = ({ code }) => {
        clearTimeout(renewTimer)
        if (stopped) return
        onStatus('desconectado')
        retryTimer = setTimeout(() => connect(code === 1008), Math.min(1000 * 2 ** attempts++, 15000))
      }
    } catch {
      if (stopped) return
      onStatus('desconectado')
      retryTimer = setTimeout(() => connect(), Math.min(1000 * 2 ** attempts++, 15000))
    }
  }
  connect()
  return () => {
    stopped = true
    clearTimeout(retryTimer)
    clearTimeout(renewTimer)
    if (socket) {
      socket.onopen = socket.onmessage = socket.onclose = socket.onerror = null
      socket.close()
    }
  }
}
