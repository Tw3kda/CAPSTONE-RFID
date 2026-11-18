// Camera permission is independent of this optional native decoder.
export async function createQrDecoder() {
  let native = null
  try {
    const Detector = globalThis.BarcodeDetector
    if (Detector && (!Detector.getSupportedFormats || (await Detector.getSupportedFormats()).includes('qr_code'))) {
      native = new Detector({ formats: ['qr_code'] })
    }
  } catch { /* Unsupported native implementations use the same JS fallback. */ }

  let fallback
  let canvas
  let context
  return async (video) => {
    if (video.readyState < 2 || !video.videoWidth || !video.videoHeight) return null
    if (native) {
      try { return (await native.detect(video))[0]?.rawValue || null }
      catch { native = null }
    }
    // Load QR-only decoding after consent, and only when native decoding is unavailable.
    fallback ||= import('jsqr').then((module) => module.default)
    const jsQR = await fallback
    canvas ||= document.createElement('canvas')
    context ||= canvas.getContext('2d', { willReadFrequently: true })
    if (!context) throw new Error('No se pudo leer la imagen de la cámara. Reintenta o usa tu ID universitario.')
    const scale = Math.min(1, 640 / Math.max(video.videoWidth, video.videoHeight))
    canvas.width = Math.max(1, Math.round(video.videoWidth * scale))
    canvas.height = Math.max(1, Math.round(video.videoHeight * scale))
    context.drawImage(video, 0, 0, canvas.width, canvas.height)
    const frame = context.getImageData(0, 0, canvas.width, canvas.height)
    return jsQR(frame.data, canvas.width, canvas.height)?.data || null
  }
}
