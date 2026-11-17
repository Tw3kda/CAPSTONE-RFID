// @vitest-environment jsdom
import { afterEach, expect, it, vi } from 'vitest'
import { prepareQrCamera, retainQrCamera, releaseQrCamera, stopQrCamera } from './qr-camera.js'

afterEach(() => { stopQrCamera(); vi.unstubAllGlobals() })

it('comparte una petición de permiso y no detiene el stream durante el montaje doble de React', async () => {
  const track = { stop: vi.fn(), readyState: 'live' }
  const stream = { getTracks: () => [track] }
  const getUserMedia = vi.fn(async () => stream)
  vi.stubGlobal('navigator', { mediaDevices: { getUserMedia } })
  vi.stubGlobal('BarcodeDetector', class { static getSupportedFormats = async () => ['qr_code'] })
  expect(await Promise.all([prepareQrCamera(), prepareQrCamera()])).toEqual([stream, stream])
  expect(getUserMedia).toHaveBeenCalledTimes(1)
  expect(retainQrCamera()).toBe(stream)
  releaseQrCamera()
  expect(retainQrCamera()).toBe(stream)
  await Promise.resolve()
  expect(track.stop).not.toHaveBeenCalled()
  releaseQrCamera()
  await Promise.resolve()
  expect(track.stop).toHaveBeenCalledTimes(1)
  expect(retainQrCamera()).toBeNull()
})

it('pide cámara desde el gesto aunque el navegador no tenga BarcodeDetector', async () => {
  const stream = { getTracks: () => [{ stop: vi.fn(), readyState: 'live' }] }
  const getUserMedia = vi.fn(async () => stream)
  vi.stubGlobal('navigator', { mediaDevices: { getUserMedia } })
  vi.stubGlobal('BarcodeDetector', undefined)
  const opening = prepareQrCamera()
  const requestedDuringGesture = getUserMedia.mock.calls.length
  expect(await opening).toBe(stream)
  expect(requestedDuringGesture).toBe(1)
})

it('no espera detección de formatos antes de pedir permiso de cámara', async () => {
  const stream = { getTracks: () => [{ stop: vi.fn(), readyState: 'live' }] }
  const getUserMedia = vi.fn(async () => stream)
  const supportedFormats = vi.fn(async () => ['qr_code'])
  vi.stubGlobal('navigator', { mediaDevices: { getUserMedia } })
  vi.stubGlobal('BarcodeDetector', class { static getSupportedFormats = supportedFormats })
  const opening = prepareQrCamera()
  const requestedDuringGesture = getUserMedia.mock.calls.length
  expect(await opening).toBe(stream)
  expect(requestedDuringGesture).toBe(1)
  expect(supportedFormats).not.toHaveBeenCalled()
})

it('libera una cámara concedida después de cancelar su apertura', async () => {
  let grant
  const getUserMedia = vi.fn(() => new Promise((resolve) => { grant = resolve }))
  const stop = vi.fn()
  vi.stubGlobal('navigator', { mediaDevices: { getUserMedia } })
  vi.stubGlobal('BarcodeDetector', class { static getSupportedFormats = async () => ['qr_code'] })
  const opening = prepareQrCamera()
  await Promise.resolve()
  stopQrCamera()
  grant({ getTracks: () => [{ stop, readyState: 'live' }] })
  await expect(opening).rejects.toThrow('canceló')
  expect(stop).toHaveBeenCalledTimes(1)
  expect(retainQrCamera()).toBeNull()
})

it.each([
  ['NotAllowedError', 'No se permitió'],
  ['NotFoundError', 'No se encontró'],
  ['NotReadableError', 'No se pudo acceder'],
])('explica %s sin volver a solicitar permiso automáticamente', async (name, message) => {
  const getUserMedia = vi.fn(async () => { throw new DOMException('Browser detail', name) })
  vi.stubGlobal('navigator', { mediaDevices: { getUserMedia } })
  vi.stubGlobal('BarcodeDetector', class { static getSupportedFormats = async () => ['qr_code'] })
  await expect(prepareQrCamera()).rejects.toThrow(message)
  expect(getUserMedia).toHaveBeenCalledTimes(1)
})

it('explica HTTPS cuando el contexto no es seguro', async () => {
  const getUserMedia = vi.fn()
  vi.stubGlobal('isSecureContext', false)
  vi.stubGlobal('navigator', { mediaDevices: { getUserMedia } })
  await expect(prepareQrCamera()).rejects.toThrow('HTTPS')
  expect(getUserMedia).not.toHaveBeenCalled()
})
