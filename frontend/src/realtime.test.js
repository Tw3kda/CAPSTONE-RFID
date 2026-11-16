import { afterEach, expect, it, vi } from 'vitest'
import { connectRealtime } from './realtime.js'

afterEach(() => vi.useRealTimers())

it('invalida al reconectar, entrega errores RFID sin confirmar físicamente y cierra al salir', async () => {
  vi.useFakeTimers()
  const sockets = []
  class Socket {
    constructor(url) { this.url = url; sockets.push(this) }
    close() { this.closed = true }
  }
  const events = []
  const statuses = []
  const api = { getSession: () => ({ expiresAt: Date.now() + 900000 }), refresh: vi.fn() }
  const stop = connectRealtime({ api, Socket, url: 'ws://localhost/api/ws/estado', onEvent: (event) => events.push(event), onStatus: (value) => statuses.push(value) })
  await vi.advanceTimersByTimeAsync(0)
  expect(sockets).toHaveLength(1)
  expect(sockets[0].url).not.toContain('token')
  sockets[0].onopen()
  sockets[0].onmessage({ data: JSON.stringify({ tipo: 'prestamo_actualizado', prestamo_id: 2, estado: 'validando_devolucion', detalle: { error: 'rfid_no_coincide' } }) })
  expect(events.at(-1).detalle.error).toBe('rfid_no_coincide')
  expect(events.at(-1).estado).toBe('validando_devolucion')
  sockets[0].onclose({ code: 1006 })
  expect(statuses.at(-1)).toBe('desconectado')
  await vi.advanceTimersByTimeAsync(1000)
  expect(sockets).toHaveLength(2)
  sockets[1].onopen()
  expect(events.at(-1).tipo).toBe('sincronizar')
  stop()
  expect(sockets[1].closed).toBe(true)
  await vi.advanceTimersByTimeAsync(60000)
  expect(sockets).toHaveLength(2)
})
