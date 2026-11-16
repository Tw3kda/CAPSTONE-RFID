// @vitest-environment jsdom
import { afterEach, expect, it, vi } from 'vitest'
import { StrictMode } from 'react'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import App from '../App.jsx'
import { SessionProvider } from '../session.jsx'
import { createApi } from '../api.js'

afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals() })

function setup(path = '/acceso', { rejectQr = false } = {}) {
  window.location.hash = path
  const requests = []
  const client = createApi({ storage: null, fetcher: async (url, options) => {
    if (url.endsWith('/auth/login')) {
      const body = JSON.parse(options.body)
      requests.push(body)
      const allowed = body.metodo === 'qr' ? !rejectQr : body.clave === 'correct-test-password'
      return new Response(JSON.stringify(allowed ? { usuario: { id: 1, nombre: 'Cuenta de prueba', rol: 'usuario', activo: true }, tokens: { access_token: 'test', refresh_token: 'test-refresh', token_type: 'bearer', expires_in: 900 } } : { detail: 'Invalid credentials' }), { status: allowed ? 200 : 401 })
    }
    return new Response('[]', { status: 200 })
  } })
  class Socket { close() {} }
  render(<StrictMode><SessionProvider client={client} Socket={Socket}><App /></SessionProvider></StrictMode>)
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
  const manual = await screen.findByText('Ingresar QR manualmente')
  expect(manual.closest('details').open).toBe(false)
  await user.click(manual)
  await user.type(await screen.findByLabelText(/Contenido del QR/), 'E000000000123456ABCDEF')
  await user.click(screen.getByRole('button', { name: 'Ingresar con QR' }))
  await screen.findByRole('heading', { name: 'Hola, Cuenta de prueba' })
  expect(requests[0]).toEqual({ metodo: 'qr', credencial: 'E000000000123456ABCDEF' })
})

it('abre la cámara una vez desde Escanear QR, enfoca el rechazo y libera el stream al salir', async () => {
  const track = { stop: vi.fn(), readyState: 'live' }
  const stream = { getTracks: () => [track] }
  const getUserMedia = vi.fn(async () => stream)
  Object.defineProperty(navigator, 'mediaDevices', { configurable: true, value: { getUserMedia } })
  vi.stubGlobal('BarcodeDetector', class {
    static getSupportedFormats = async () => ['qr_code']
    detect = async () => [{ rawValue: 'E000000000123456ABCDEF' }]
  })
  vi.spyOn(HTMLMediaElement.prototype, 'play').mockResolvedValue()
  const scroll = vi.fn()
  Element.prototype.scrollIntoView = scroll
  const { user, requests } = setup('/acceso', { rejectQr: true })
  await user.click(screen.getByRole('button', { name: 'Escanear QR' }))
  const error = await screen.findByRole('alert')
  await waitFor(() => expect(document.activeElement.contains(error)).toBe(true))
  expect(scroll).toHaveBeenCalledTimes(1)
  expect(getUserMedia).toHaveBeenCalledTimes(1)
  expect(requests).toHaveLength(1)
  expect(screen.queryByRole('button', { name: 'Detener cámara' })).toBeNull()
  expect(track.stop).toHaveBeenCalledTimes(1)
  await user.click(screen.getByRole('link', { name: 'Usar ID universitario' }))
  await screen.findByLabelText('Clave')
})

it('explica un permiso denegado y permite continuar con ID sin volver a pedirlo automáticamente', async () => {
  const denied = new Error('Camera denied'); denied.name = 'NotAllowedError'
  const getUserMedia = vi.fn(async () => { throw denied })
  Object.defineProperty(navigator, 'mediaDevices', { configurable: true, value: { getUserMedia } })
  vi.stubGlobal('BarcodeDetector', class { static getSupportedFormats = async () => ['qr_code'] })
  Element.prototype.scrollIntoView = vi.fn()
  const { user } = setup()
  await user.click(screen.getByRole('button', { name: 'Escanear QR' }))
  expect((await screen.findByRole('alert')).textContent).toContain('No se permitió')
  expect(getUserMedia).toHaveBeenCalledTimes(1)
  expect(screen.getByRole('link', { name: 'Usar ID universitario' })).toBeTruthy()
  expect(screen.getByText('Ingresar QR manualmente').closest('details').open).toBe(false)
})
