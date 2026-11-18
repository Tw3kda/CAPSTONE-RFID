let stream = null
let pending = null
let readers = 0
let cameraError = null
let generation = 0

export function prepareQrCamera() {
  if (hasQrCamera()) return Promise.resolve(stream)
  if (pending) return pending
  cameraError = null
  const requestedGeneration = generation
  pending = (async () => {
    if (globalThis.isSecureContext === false) {
      throw new Error('La cámara requiere HTTPS. Abre el enlace seguro de Thesora o usa tu ID universitario.')
    }
    if (!navigator.mediaDevices?.getUserMedia) {
      throw new Error('Este navegador no ofrece acceso a la cámara. Abre Thesora directamente en Chrome o Safari, fuera de otras aplicaciones, o usa tu ID universitario.')
    }
    // Camera consent belongs to the click, independently of the QR decoder.
    const media = await navigator.mediaDevices.getUserMedia({ video: { facingMode: { ideal: 'environment' } }, audio: false })
    if (generation !== requestedGeneration) {
      media.getTracks().forEach((track) => track.stop())
      throw new DOMException('Se canceló la apertura de la cámara. Pulsa Reintentar para abrirla.', 'AbortError')
    }
    stream = media
    return stream
  })().catch((error) => {
    const messages = {
      NotAllowedError: 'No se permitió el acceso a la cámara. Revisa el permiso del sitio y del navegador. Si abriste el enlace dentro de otra aplicación, ábrelo directamente en Chrome o Safari, o usa tu ID universitario.',
      SecurityError: 'El navegador bloqueó la cámara. Abre el enlace HTTPS directamente en Chrome o Safari y revisa sus permisos, o usa tu ID universitario.',
      NotFoundError: 'No se encontró una cámara disponible. Conecta o habilita una cámara, o usa tu ID universitario.',
      NotReadableError: 'No se pudo acceder a la cámara. Cierra otras aplicaciones que puedan estar usándola y reintenta, o usa tu ID universitario.',
      OverconstrainedError: 'No se pudo iniciar una cámara compatible. Abre el enlace directamente en Chrome o Safari, o usa tu ID universitario.',
    }
    cameraError = messages[error.name] ? new Error(messages[error.name]) : error
    throw cameraError
  }).finally(() => { pending = null })
  return pending
}

export const getQrCameraError = () => cameraError
export const hasQrCamera = () => Boolean(stream?.getTracks().some((track) => track.readyState !== 'ended'))

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
  generation++
  stream?.getTracks().forEach((track) => track.stop())
  stream = null
}
