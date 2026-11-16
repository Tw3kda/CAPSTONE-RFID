const STORAGE_KEY = 'thesora.session'
const messages = {
  401: 'La sesión terminó. Identifícate de nuevo.',
  403: 'Tu cuenta no tiene permiso para realizar esta operación.',
  404: 'El registro ya no está disponible. Vuelve a consultar el listado.',
  409: 'El estado cambió o los datos ya están registrados. Revisa la información y vuelve a intentar.',
  422: 'Revisa los campos indicados y vuelve a intentar.',
}

export class ApiError extends Error {
  constructor(status, detail) {
    const fields = Array.isArray(detail) ? detail.map((e) => `${e.loc?.filter((x) => x !== 'body').join('.')}: ${e.msg}`).join('; ') : ''
    super(`${messages[status] || 'No se pudo completar la solicitud. Intenta de nuevo.'}${fields ? ` ${fields}` : ''}`)
    this.status = status
    this.detail = detail
  }
}

export function createApi({ base = '/api', fetcher = (...args) => fetch(...args), storage = globalThis.sessionStorage } = {}) {
  let session = null
  try { session = JSON.parse(storage?.getItem(STORAGE_KEY) || 'null') } catch { /* Storage can be unavailable. */ }
  if (!session?.tokens?.refresh_token || !session?.usuario) session = null
  let refreshing = null
  let generation = 0
  const listeners = new Set()
  function update(value) {
    session = value
    try { if (value) storage?.setItem(STORAGE_KEY, JSON.stringify(value)); else storage?.removeItem(STORAGE_KEY) } catch { /* In-memory sessions still work. */ }
    listeners.forEach((listener) => listener())
  }
  function logout() { generation++; update(null) }
  async function send(path, { body, headers, ...options } = {}, token) {
    let response
    try {
      response = await fetcher(`${base}${path}`, {
        ...options, credentials: 'same-origin',
        headers: { ...(body !== undefined ? { 'Content-Type': 'application/json' } : {}), ...(token ? { Authorization: `Bearer ${token}` } : {}), ...headers },
        ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
      })
    } catch (error) {
      if (error.name === 'AbortError') throw error
      throw new ApiError(0, 'Network unavailable')
    }
    const data = response.status === 204 ? null : await response.json().catch(() => null)
    if (!response.ok) throw new ApiError(response.status, data?.detail)
    return data
  }
  async function refresh() {
    if (!session) throw new ApiError(401)
    if (!refreshing) {
      const current = generation
      const previous = session
      refreshing = send('/auth/refresh', { method: 'POST', body: { refresh_token: previous.tokens.refresh_token } })
        .then((tokens) => {
          if (generation !== current) throw new ApiError(401)
          update({ ...previous, tokens, expiresAt: Date.now() + tokens.expires_in * 1000 })
          return tokens
        }).catch((error) => {
          if (generation === current && error.status === 401) logout()
          throw error
        }).finally(() => { refreshing = null })
    }
    return refreshing
  }
  async function request(path, options = {}) {
    const token = session?.tokens.access_token
    try { return await send(path, options, token) } catch (error) {
      if (error.status !== 401 || !session) throw error
      // Another request may have refreshed while this response was in flight.
      if (token === session.tokens.access_token) await refresh()
      try { return await send(path, options, session?.tokens.access_token) } catch (retryError) {
        if (retryError.status === 401) logout()
        throw retryError
      }
    }
  }
  return {
    request, refresh, logout,
    getSession: () => session,
    subscribe(listener) { listeners.add(listener); return () => listeners.delete(listener) },
    async login(metodo, credencial, clave) {
      const current = ++generation
      const data = await send('/auth/login', { method: 'POST', body: { metodo, credencial: credencial.trim(), ...(metodo === 'id' ? { clave } : {}) } })
      if (current === generation) update({ ...data, expiresAt: Date.now() + data.tokens.expires_in * 1000 })
      return data
    },
    async restore() {
      if (!session) return null
      const usuario = await request('/auth/me')
      if (session) update({ ...session, usuario })
      return usuario
    },
  }
}

export const api = createApi({ base: import.meta.env?.VITE_API_BASE_URL || '/api' })

export function queryString(values) {
  const params = new URLSearchParams(Object.entries(values).filter(([, value]) => value !== '' && value != null))
  return params.size ? `?${params}` : ''
}
