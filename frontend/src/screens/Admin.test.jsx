// @vitest-environment jsdom
import { afterEach, expect, it } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import App from '../App.jsx'
import { SessionProvider } from '../session.jsx'
import { createApi } from '../api.js'

afterEach(cleanup)
const position = { posicion_id: 1, espacio: 'Lab', gabinete: 'A', estante: '2', codigo: '3' }
const asset = { id: 1, nombre: 'Equipo de prueba', codigo: 'ACT-001', categoria_id: 1, categoria: 'Medición', estado: 'disponible', condicion: 'Operativo', ultima_revision_at: null, ubicacion: position }
async function setup(section) {
  window.location.hash = `/admin/${section}`
  const requests = []
  const user = { id: 7, nombre: 'Administración de prueba', rol: 'administrador', activo: true }
  const lists = { usuarios: [user], activos: [asset], categorias: [{ id: 1, nombre: 'Medición' }], posiciones: [position], espacios: [{ id: 1, nombre: 'Lab' }], gabinetes: [{ id: 1, nombre: 'A', espacio_id: 1 }], lectores: [], dispositivos: [] }
  const client = createApi({ storage: null, fetcher: async (url, options) => {
    requests.push([url, options])
    let result
    const section = url.split('/').at(-1).split('?')[0]
    if (url.endsWith('/auth/login')) result = { usuario: user, tokens: { access_token: 'test', refresh_token: 'test-refresh', token_type: 'bearer', expires_in: 900 } }
    else if (url.endsWith('/auth/me')) result = user
    else if (options.method === 'POST' && section === 'dispositivos') result = { id: 'esp-test', api_key: 'once-only-test-key' }
    else if (options.method === 'POST') {
      result = { id: 8, activo: true, ...JSON.parse(options.body) }
      lists[section].push(result)
    } else if (options.method === 'PATCH') {
      result = { ...asset, ...JSON.parse(options.body) }
      lists.activos = [result]
    } else result = lists[section] || []
    return new Response(JSON.stringify(result), { status: 200 })
  } })
  await client.login('id', 'test-only')
  class Socket { close() {} }
  render(<SessionProvider client={client} Socket={Socket}><App /></SessionProvider>)
  await screen.findByRole('heading', { name: 'Administración' })
  return { requests, user: userEvent.setup() }
}

it('crea una cuenta con ID institucional obligatorio y permite omitir QR', async () => {
  const { user, requests } = await setup('usuarios')
  await user.click(await screen.findByRole('button', { name: 'Nuevo usuario' }))
  await user.type(screen.getByLabelText('Nombre'), 'Cuenta nueva')
  await user.type(screen.getByLabelText('ID universitario registrado'), 'test-institutional-id')
  await user.click(screen.getByRole('button', { name: 'Guardar' }))
  await screen.findByRole('cell', { name: 'Cuenta nueva' })
  const create = requests.find(([url, options]) => url.endsWith('/usuarios') && options.method === 'POST')
  expect(JSON.parse(create[1].body)).toEqual({ nombre: 'Cuenta nueva', rol: 'usuario', identificador_institucional: 'test-institutional-id' })
})

it('edita un activo sin reenviar ni inventar su RFID protegido', async () => {
  const { user, requests } = await setup('activos')
  await user.click(await screen.findByRole('button', { name: 'Editar Equipo de prueba' }))
  const input = await screen.findByLabelText('Nombre')
  await user.clear(input)
  await user.type(input, 'Equipo actualizado')
  await user.click(screen.getByRole('button', { name: 'Guardar' }))
  await screen.findByRole('cell', { name: 'Equipo actualizado' })
  const edit = requests.find(([url, options]) => url.endsWith('/activos/1') && options.method === 'PATCH')
  expect(JSON.parse(edit[1].body)).toMatchObject({ nombre: 'Equipo actualizado', categoria_id: 1, posicion_asignada_id: 1 })
  expect(JSON.parse(edit[1].body)).not.toHaveProperty('rfid_uid')
})

it('muestra credencial del dispositivo solo tras crearlo y la elimina al cerrar el resultado', async () => {
  const { user } = await setup('dispositivos')
  await user.click(await screen.findByRole('button', { name: 'Nuevo dispositivo' }))
  await user.type(screen.getByLabelText('Identificador del dispositivo'), 'esp-test')
  await user.click(screen.getByRole('button', { name: 'Guardar' }))
  expect((await screen.findByLabelText('Clave del dispositivo')).value).toBe('once-only-test-key')
  await user.click(screen.getByRole('button', { name: 'Ya guardé la clave' }))
  expect(screen.queryByLabelText('Clave del dispositivo')).toBeNull()
})
