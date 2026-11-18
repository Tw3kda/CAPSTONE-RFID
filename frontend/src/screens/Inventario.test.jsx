// @vitest-environment jsdom
import { afterEach, expect, it } from 'vitest'
import { act, cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import App from '../App.jsx'
import { SessionProvider } from '../session.jsx'
import { createApi } from '../api.js'

afterEach(cleanup)
const position = { posicion_id: 1, espacio: 'Laboratorio', gabinete: 'A', estante: '2', codigo: 'P3' }
const original = { id: 1, nombre: 'Equipo de prueba', codigo: 'ACT-001', categoria_id: 1, categoria: 'Medición', estado: 'disponible', presente: true, disponible: true, condicion: 'Operativo', ultima_revision_at: null, ubicacion: position }

async function setup(path = '/recurso/1', presence = true) {
  window.location.hash = path
  let asset = { ...original, presente: presence }
  let history = []
  let socket
  const requests = []
  const person = { id: 7, nombre: 'Persona de prueba', rol: 'usuario', activo: true }
  const client = createApi({ storage: null, fetcher: async (url, options) => {
    requests.push([url, options])
    let result
    if (url.endsWith('/auth/login')) result = { usuario: person, tokens: { access_token: 'test', refresh_token: 'test-refresh', token_type: 'bearer', expires_in: 900 } }
    else if (url.endsWith('/auth/me')) result = person
    else if (url.endsWith('/activos/1/historial')) result = history
    else if (url.endsWith('/activos/1/ubicacion')) result = { asignada: position, posiciones_estante: [position] }
    else if (url.endsWith('/activos/1')) result = asset
    else if (url.includes('/activos')) result = url.includes('estado=disponible') && !asset.disponible ? [] : [asset]
    else if (url.endsWith('/categorias')) result = [{ id: 1, nombre: 'Medición' }]
    else result = []
    return new Response(JSON.stringify(result), { status: 200 })
  } })
  await client.login('qr', 'synthetic-test-qr')
  class Socket { constructor() { socket = this } close() {} }
  render(<SessionProvider client={client} Socket={Socket}><App /></SessionProvider>)
  await waitFor(() => expect(socket?.onmessage).toBeTypeOf('function'))
  return {
    requests,
    async presence(present) {
      asset = { ...asset, presente: present, disponible: present }
      history = [{ id: 1, tipo: present ? 'INGRESO' : 'RETIRADO', ocurrido_at: '2026-11-17T12:00:00Z', ubicacion: position }]
      await act(async () => socket.onmessage({ data: JSON.stringify({ tipo: 'inventario_actualizado', activo_id: 1, prestamo_id: null, estado: null, detalle: { presente: present, ...(!present ? { error: 'retiro_sin_prestamo' } : {}) } }) }))
    },
  }
}
async function go(path) { await act(async () => { window.location.hash = path }) }

it('actualiza ficha, ubicación y filtro desde el servidor al retirar y reponer sin préstamo', async () => {
  const state = await setup()
  const user = userEvent.setup()
  await screen.findByText('Disponible', { selector: 'dd' })
  expect(screen.getByRole('link', { name: 'Registrar préstamo' })).toBeTruthy()
  await state.presence(false)
  await screen.findByText('No disponible', { selector: 'dd' })
  expect(screen.queryByRole('link', { name: 'Registrar préstamo' })).toBeNull()
  expect((await screen.findByRole('alert')).textContent).toContain('Retirado sin préstamo registrado')
  await screen.findByText('RETIRADO')
  await go('/recurso/1/ubicacion')
  await screen.findByRole('button', { name: 'Señalar posición' })
  expect(screen.queryByRole('link', { name: 'Registrar préstamo' })).toBeNull()
  await go('/inventario')
  await screen.findByText('No disponible')
  await user.click(screen.getByRole('button', { name: 'Disponibles', exact: true }))
  await screen.findByText(/Ningún recurso coincide/)
  await state.presence(true)
  await screen.findByText('Disponible')
  expect(screen.queryByRole('alert')).toBeNull()
  await go('/recurso/1')
  await screen.findByRole('link', { name: 'Registrar préstamo' })
  expect(state.requests.some(([url, options]) => url.endsWith('/prestamos') && options.method === 'POST')).toBe(false)
})

it('avisa del retiro sin tener abierto un flujo de préstamo ni la ficha', async () => {
  const state = await setup('/inicio')
  await screen.findByRole('heading', { name: /Hola, Persona de prueba/ })
  await state.presence(false)
  expect((await screen.findByRole('alert')).textContent).toContain('Retirado sin préstamo registrado')
  expect(screen.getByRole('link', { name: 'Ver recurso retirado' }).getAttribute('href')).toBe('#/recurso/1')
  expect(state.requests.some(([url, options]) => url.endsWith('/prestamos') && options.method === 'POST')).toBe(false)
})

it('presenta presencia desconocida sin afirmar que el recurso está detectado', async () => {
  await setup('/recurso/1', null)
  await screen.findByText('Sin observación RFID registrada')
  expect(screen.getByText('Disponible', { selector: 'dd' })).toBeTruthy()
  expect(screen.getByRole('link', { name: 'Registrar préstamo' })).toBeTruthy()
})
