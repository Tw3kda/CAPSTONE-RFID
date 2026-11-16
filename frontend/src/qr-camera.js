let stream = null
let pending = null
let readers = 0
let cameraError = null

export function prepareQrCamera() {
  if (stream?.getTracks().some((track) => track.readyState !== 'ended')) return Promise.resolve(stream)
  if (pending) return pending
  cameraError = null
  pending = (async () => {
    if (!navigator.mediaDevices?.getUserMedia || !globalThis.BarcodeDetector
      || !(await globalThis.BarcodeDetector.getSupportedFormats()).includes('qr_code')) {
      throw new Error('La lectura de QR con cámara no está disponible en este navegador. Usa tu ID universitario o ingresa el contenido del QR.')
    }
    stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: { ideal: 'environment' } }, audio: false })
    return stream
  })().catch((error) => {
    cameraError = error.name === 'NotAllowedError'
      ? new Error('No se permitió el acceso a la cámara. Revisa el permiso o usa tu ID universitario.')
      : error
    throw cameraError
  }).finally(() => { pending = null })
  return pending
}

export const getQrCameraError = () => cameraError
export const hasQrCamera = () => stream !== null

export function retainQrCamera() {
  if (stream) readers++
  return stream
}

export function releaseQrCamera() {
  readers = Math.max(0, readers - 1)
  // StrictMode mounts again in the same turn; release only after the last reader leaves.
  queueMicrotask(() => { if (readers === 0) stopQrCamera() })
}

export function stopQrCamera() {
  stream?.getTracks().forEach((track) => track.stop())
  stream = null
}
