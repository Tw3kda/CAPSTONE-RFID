// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it } from 'vitest'
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import App from './App.jsx'
import { SessionProvider } from './session.jsx'
import { createApi } from './api.js'

const location = { posicion_id: 1, espacio: 'Laboratorio', gabinete: 'A', estante: '2', codigo: 'P3' }
const asset = { id: 1, nombre: 'Equipo de prueba', codigo: 'ACT-001', categoria_id: 1, categoria: 'Medición', estado: 'disponible', condicion: 'Operativo', ultima_revision_at: null, ubicacion: location }
const person = { id: 7, nombre: 'Persona de prueba', rol: 'usuario', activo: true }
const tokens = { access_token: 'test', refresh_token: 'test-refresh', token_type: 'bearer', expires_in: 900 }
const initialLoan = { id: 11, activo_id: 1, responsable_id: 7, entregado_por_id: 7, activo_nombre: asset.nombre, responsable_nombre: person.nombre, entregado_por_nombre: person.nombre, ubicacion_asignada: location, retiro_at: null, devolucion_esperada_at: '2027-01-15T21:00:00Z', devolucion_at: null, estado: 'pendiente_retiro' }
let sockets
class Socket {
  constructor() { sockets.push(this) }
  close() {}
}
beforeEach(() => { sockets = []; window.location.hash = '/acceso' })
afterEach(cleanup)

function setup({ role = 'usuario', failCreate = false } = {}) {
  let loan = { ...initialLoan }
  const requests = []
  const client = createApi({ storage: null, fetcher: async (url, options) => {
    requests.push([url, options])
    let result
    if (url.endsWith('/auth/login')) result = { tokens, usuario: { ...person, rol: role } }
    else if (url.endsWith('/auth/me')) result = { ...person, rol: role }
    else if (url.includes('/activos/1/ubicacion')) result = { asignada: location, posiciones_estante: [location] }
    else if (url.endsWith('/activos/1/historial')) result = []
    else if (url.endsWith('/activos/1')) result = asset
    else if (url.includes('/activos')) result = [asset]
    else if (url.includes('/categorias')) result = [{ id: 1, nombre: 'Medición' }]
    else if (url.endsWith('/prestamos') && options.method === 'POST') {
      if (failCreate) return new Response(JSON.stringify({ detail: 'Asset is unavailable' }), { status: 409 })
      result = loan
    }
    else if (url.endsWith('/prestamos/11/devolucion')) { loan = { ...loan, estado: 'validando_devolucion' }; result = loan }
    else if (url.endsWith('/prestamos/11')) result = loan
    else if (url.includes('/prestamos')) result = [loan]
    else if (url.includes('/usuarios')) result = [{ ...person, rol: role }]
    else result = []
    return new Response(JSON.stringify(result), { status: 200, headers: { 'Content-Type': 'application/json' } })
  } })
  render(<SessionProvider client={client} Socket={Socket}><App /></SessionProvider>)
  return { requests, setLoan(value) { loan = { ...loan, ...value } } }
}
async function login() {
  const user = userEvent.setup()
  await user.clear(screen.getByLabelText('ID universitario'))
  await user.type(screen.getByLabelText('ID universitario'), 'test-institutional-id')
  await user.click(screen.getByRole('button', { name: 'Ingresar con ID' }))
  await screen.findByRole('heading', { name: /Hola, Persona de prueba/ })
  return user
}
async function go(path) { await act(async () => { window.location.hash = path }) }

it('prepara el préstamo en API y solo muestra comprobante al confirmar retiro el servidor', async () => {
  const state = setup()
  const user = await login()
  await go('/prestamo?id=1')
  await screen.findByRole('option', { name: /Equipo de prueba/ })
  fireEvent.change(screen.getByLabelText('Fecha prevista de devolución'), { target: { value: '2027-01-15T16:00' } })
  await user.click(screen.getByRole('button', { name: 'Continuar para mí' }))
  await screen.findByRole('heading', { name: 'Retira el recurso del stand' })
  expect(screen.queryByRole('heading', { name: 'Retiro confirmado' })).toBeNull()
  const create = state.requests.find(([url, options]) => url.endsWith('/prestamos') && options.method === 'POST')
  expect(JSON.parse(create[1].body)).toEqual({ activo_id: 1, responsable_id: 7, devolucion_esperada_at: new Date('2027-01-15T16:00').toISOString() })
  state.setLoan({ estado: 'activo', retiro_at: '2026-11-17T12:00:00Z' })
  await act(async () => sockets.at(-1).onmessage({ data: JSON.stringify({ tipo: 'prestamo_actualizado', prestamo_id: 11, estado: 'activo', detalle: {} }) }))
  await screen.findByRole('heading', { name: 'Retiro confirmado' })
})

it('muestra conflicto sin pasar a retiro y limita administración al rol real', async () => {
  setup({ failCreate: true })
  const user = await login()
  expect(screen.queryByRole('link', { name: 'Administración' })).toBeNull()
  await go('/prestamo?id=1')
  await screen.findByRole('option', { name: /Equipo de prueba/ })
  fireEvent.change(screen.getByLabelText('Fecha prevista de devolución'), { target: { value: '2027-01-15T16:00' } })
  await user.click(screen.getByRole('button', { name: 'Continuar para mí' }))
  expect((await screen.findByRole('alert')).textContent).toContain('estado')
  expect(screen.queryByRole('heading', { name: 'Retira el recurso del stand' })).toBeNull()
  await go('/admin/usuarios')
  await screen.findByRole('heading', { name: 'Acceso restringido' })
})

it('mantiene devolución abierta ante RFID incorrecto y confirma solo el estado devuelto consultado', async () => {
  const state = setup()
  state.setLoan({ estado: 'activo', retiro_at: '2026-11-17T12:00:00Z' })
  const user = await login()
  await go('/mis-recursos/prestamo?id=11')
  await user.click(await screen.findByRole('button', { name: 'Devolver recurso' }))
  await screen.findByRole('heading', { name: 'Presenta el recurso al lector' })
  await act(async () => sockets.at(-1).onmessage({ data: JSON.stringify({ tipo: 'prestamo_actualizado', prestamo_id: 11, estado: 'validando_devolucion', detalle: { error: 'rfid_incorrecto' } }) }))
  await screen.findByRole('heading', { name: 'Recurso incorrecto' })
  expect(screen.queryByRole('heading', { name: 'Devolución confirmada' })).toBeNull()
  await user.click(screen.getByRole('button', { name: 'Reintentar lectura' }))
  await screen.findByRole('heading', { name: 'Presenta el recurso al lector' })
  state.setLoan({ estado: 'devuelto', devolucion_at: '2026-11-17T13:00:00Z' })
  await act(async () => sockets.at(-1).onmessage({ data: JSON.stringify({ tipo: 'prestamo_actualizado', prestamo_id: 11, estado: 'devuelto', detalle: {} }) }))
  await screen.findByRole('heading', { name: 'Devolución confirmada' })
})
