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

it('rechaza una cámara no compatible sin pedir permisos innecesarios', async () => {
  const getUserMedia = vi.fn()
  vi.stubGlobal('navigator', { mediaDevices: { getUserMedia } })
  vi.stubGlobal('BarcodeDetector', undefined)
  await expect(prepareQrCamera()).rejects.toThrow('no está disponible')
  expect(getUserMedia).not.toHaveBeenCalled()
})
