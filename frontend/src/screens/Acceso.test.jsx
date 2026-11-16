// @vitest-environment jsdom
import { afterEach, expect, it } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import App from '../App.jsx'
import { SessionProvider } from '../session.jsx'
import { createApi } from '../api.js'

afterEach(cleanup)

function setup(path = '/acceso') {
  window.location.hash = path
  const requests = []
  const client = createApi({ storage: null, fetcher: async (url, options) => {
    if (url.endsWith('/auth/login')) {
      const body = JSON.parse(options.body)
      requests.push(body)
      const allowed = body.metodo === 'qr' || body.clave === 'correct-test-password'
      return new Response(JSON.stringify(allowed ? { usuario: { id: 1, nombre: 'Cuenta de prueba', rol: 'usuario', activo: true }, tokens: { access_token: 'test', refresh_token: 'test-refresh', token_type: 'bearer', expires_in: 900 } } : { detail: 'Invalid credentials' }), { status: allowed ? 200 : 401 })
    }
    return new Response('[]', { status: 200 })
  } })
  class Socket { close() {} }
  render(<SessionProvider client={client} Socket={Socket}><App /></SessionProvider>)
  return { user: userEvent.setup(), requests }
}

it('requiere clave para ID, muestra rechazo genérico y permite corregirla', async () => {
  const { user, requests } = setup()
  await user.type(screen.getByLabelText('ID universitario'), 'test-institutional-id')
  const password = screen.getByLabelText('Clave')
  expect(password.type).toBe('password')
  expect(password.autocomplete).toBe('current-password')
  await user.click(screen.getByRole('button', { name: 'Ingresar con ID' }))
  expect(requests).toHaveLength(0)
  await user.type(password, 'incorrect-test-password')
  await user.click(screen.getByRole('button', { name: 'Ingresar con ID' }))
  expect((await screen.findByRole('alert')).textContent).toContain('ID o clave incorrectos')
  expect(screen.queryByRole('heading', { name: 'Hola, Cuenta de prueba' })).toBeNull()
  await user.clear(password)
  await user.type(password, 'correct-test-password')
  await user.click(screen.getByRole('button', { name: 'Ingresar con ID' }))
  await screen.findByRole('heading', { name: 'Hola, Cuenta de prueba' })
  expect(requests[1]).toEqual({ metodo: 'id', credencial: 'test-institutional-id', clave: 'correct-test-password' })
})

it('permite QR sin campo clave ni normalización del contenido en el cliente', async () => {
  const { user, requests } = setup('/acceso/qr')
  expect(screen.queryByLabelText('Clave')).toBeNull()
  await user.type(await screen.findByLabelText(/Contenido del QR/), 'E000000000123456ABCDEF')
  await user.click(screen.getByRole('button', { name: 'Ingresar con QR' }))
  await screen.findByRole('heading', { name: 'Hola, Cuenta de prueba' })
  expect(requests[0]).toEqual({ metodo: 'qr', credencial: 'E000000000123456ABCDEF' })
})
