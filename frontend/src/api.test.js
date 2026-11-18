import { describe, expect, it } from 'vitest'
import { createApi, ApiError } from './api.js'

const json = (body, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
const session = { usuario: { id: 7, nombre: 'Persona de prueba', rol: 'usuario', activo: true }, tokens: { access_token: 'old', refresh_token: 'refresh', token_type: 'bearer', expires_in: 900 } }

describe('cliente HTTP de sesión', () => {
  it('envía clave solo para ID, preserva sus espacios y no la guarda en la sesión', async () => {
    const stored = new Map()
    const storage = { getItem: (key) => stored.get(key), setItem: (key, value) => stored.set(key, value), removeItem: (key) => stored.delete(key) }
    const payloads = []
    const api = createApi({ storage, fetcher: async (_, options) => { payloads.push(JSON.parse(options.body)); return json(session) } })
    await api.login('id', ' test-institutional-id ', ' test-password-only ')
    expect(payloads[0]).toEqual({ metodo: 'id', credencial: 'test-institutional-id', clave: ' test-password-only ' })
    expect([...stored.values()].join('')).not.toContain('test-password-only')
    expect(api.getSession()).not.toHaveProperty('clave')
    await api.login('qr', 'qr-test-only', 'must-never-be-sent')
    expect(payloads[1]).toEqual({ metodo: 'qr', credencial: 'qr-test-only' })
  })

  it('identifica con credencial y renueva una sola vez peticiones concurrentes antes de repetirlas', async () => {
    let refreshes = 0
    const calls = []
    const api = createApi({ storage: null, fetcher: async (url, options) => {
      calls.push([url, options])
      if (url.endsWith('/auth/login')) return json(session)
      if (url.endsWith('/auth/refresh')) {
        refreshes++
        return json({ ...session.tokens, access_token: 'new' })
      }
      return options.headers.Authorization === 'Bearer new' ? json([{ id: 1 }]) : json({ detail: 'Token expired' }, 401)
    } })
    await api.login('id', 'credential-test')
    expect(api.getSession().usuario.id).toBe(7)
    expect(await Promise.all([api.request('/activos'), api.request('/categorias')])).toEqual([[{ id: 1 }], [{ id: 1 }]])
    expect(refreshes).toBe(1)
    expect(JSON.parse(calls[0][1].body)).toEqual({ metodo: 'id', credencial: 'credential-test' })
    expect(calls.every(([, options]) => options.credentials === 'same-origin')).toBe(true)
  })

  it('pierde la sesión si la renovación es rechazada y no repite una mutación sin autorización', async () => {
    const api = createApi({ storage: null, fetcher: async (url) => url.endsWith('/auth/login') ? json(session) : json({ detail: 'Invalid session' }, 401) })
    await api.login('qr', 'test-only')
    await expect(api.request('/prestamos', { method: 'POST', body: { activo_id: 3 } })).rejects.toMatchObject({ status: 401 })
    expect(api.getSession()).toBe(null)
  })

  it('conserva conflictos y errores de validación sin convertirlos en éxito ni cerrar sesión', async () => {
    const api = createApi({ storage: null, fetcher: async (url) => url.endsWith('/auth/login') ? json(session) : json({ detail: [{ loc: ['body', 'nombre'], msg: 'Field required' }] }, 422) })
    await api.login('id', 'test-only')
    await expect(api.request('/usuarios', { method: 'POST', body: {} })).rejects.toMatchObject({ status: 422, message: expect.stringContaining('nombre') })
    expect(api.getSession().usuario.id).toBe(7)
  })

  it.each([403, 409])('mantiene el error HTTP %s sin repetir la operación', async (status) => {
    let mutations = 0
    const api = createApi({ storage: null, fetcher: async (url) => {
      if (url.endsWith('/auth/login')) return json(session)
      mutations++
      return json({ detail: 'Rejected by backend' }, status)
    } })
    await api.login('id', 'test-only')
    await expect(api.request('/prestamos', { method: 'POST', body: {} })).rejects.toBeInstanceOf(ApiError)
    expect(mutations).toBe(1)
    expect(api.getSession().usuario.rol).toBe('usuario')
  })
})
