// @vitest-environment jsdom
import { afterEach, expect, it, vi } from 'vitest'
import { createQrDecoder } from './qr-decoder.js'
// Generated once with qrcode 1.5.4; synthetic card only, no runtime/test generator dependency.
import matrix from './test-fixtures/qr-symbol.json'

afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals() })

export function qrFrame() {
  const scale = 4
  const size = matrix.length * scale
  const data = new Uint8ClampedArray(size * size * 4)
  for (let y = 0; y < size; y++) for (let x = 0; x < size; x++) {
    const index = (y * size + x) * 4
    const color = matrix[Math.floor(y / scale)][Math.floor(x / scale)] === '1' ? 0 : 255
    data[index] = color; data[index + 1] = color; data[index + 2] = color; data[index + 3] = 255
  }
  return { data, size }
}

function frameVideo() {
  const { data, size } = qrFrame()
  const context = { drawImage: vi.fn(), getImageData: vi.fn(() => ({ data })) }
  vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue(context)
  return { video: { readyState: 2, videoWidth: size, videoHeight: size }, context }
}

it.each(['absent', 'formats', 'constructor', 'detect'])('decodifica un QR real con JS si el detector nativo falla en %s', async (failure) => {
  const detect = vi.fn(async () => { throw new DOMException('Unsupported', 'NotSupportedError') })
  vi.stubGlobal('BarcodeDetector', failure === 'absent' ? undefined : class {
    static getSupportedFormats = async () => failure === 'formats' ? ['ean_13'] : ['qr_code']
    constructor() { if (failure === 'constructor') throw new DOMException('Unsupported', 'NotSupportedError') }
    detect = detect
  })
  const { video } = frameVideo()
  const decode = await createQrDecoder()
  expect(await decode(video)).toBe('E000000000123456ABCDEF')
  expect(await decode(video)).toBe('E000000000123456ABCDEF')
  if (failure === 'detect') expect(detect).toHaveBeenCalledTimes(1)
})

it('conserva la detección nativa cuando funciona sin leer canvas', async () => {
  const getContext = vi.spyOn(HTMLCanvasElement.prototype, 'getContext')
  const detect = vi.fn(async () => [{ rawValue: 'native-code' }])
  vi.stubGlobal('BarcodeDetector', class {
    static getSupportedFormats = async () => ['qr_code']
    detect = detect
  })
  const decode = await createQrDecoder()
  expect(await decode({ readyState: 2, videoWidth: 640, videoHeight: 480 })).toBe('native-code')
  expect(getContext).not.toHaveBeenCalled()
})

it('espera un frame real y limita el trabajo de canvas a 640 píxeles por lado', async () => {
  vi.stubGlobal('BarcodeDetector', undefined)
  const context = { drawImage: vi.fn(), getImageData: vi.fn(() => ({ data: new Uint8ClampedArray(640 * 360 * 4) })) }
  vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue(context)
  const video = { readyState: 0, videoWidth: 1920, videoHeight: 1080 }
  const decode = await createQrDecoder()
  expect(await decode(video)).toBeNull()
  expect(context.drawImage).not.toHaveBeenCalled()
  video.readyState = 2
  expect(await decode(video)).toBeNull()
  expect(context.drawImage).toHaveBeenCalledWith(video, 0, 0, 640, 360)
})
