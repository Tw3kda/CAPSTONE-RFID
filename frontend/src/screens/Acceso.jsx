import { useEffect, useRef, useState } from 'react'
import { Shell, PageHeader, Field, ErrorNotice } from '../components.jsx'
import { Link, navigate } from '../router.jsx'
import { useSession } from '../session.jsx'

export function Acceso() {
  const { client } = useSession()
  const [credential, setCredential] = useState('')
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  async function submit(event) {
    event.preventDefault(); setBusy(true); setError(null)
    try { await client.login('id', credential); navigate('/inicio') }
    catch (err) { setError(err.status === 401 ? new Error('ID no registrado o cuenta inactiva. Comprueba tu credencial o consulta al administrador.') : err) }
    finally { setBusy(false) }
  }
  return <Shell sinNav><PageHeader titulo="Identifícate para continuar" subtitulo="Accede al laboratorio con tu credencial universitaria." /><div className="container content"><div className="opciones"><section className="card opcion"><h2>Opción 1 · QR</h2><p className="note">Abre la cámara y escanea tu credencial registrada.</p><Link to="/acceso/qr" className="btn btn--primary">Escanear QR</Link></section><form className="card opcion" onSubmit={submit}><h2>Opción 2 · ID universitario</h2><p className="note">Escribe tu identificador institucional registrado.</p><Field label="ID universitario"><input className="field" value={credential} onChange={(event) => setCredential(event.target.value)} required maxLength={256} autoComplete="off" /></Field><ErrorNotice error={error} /><button className="btn btn--secondary" disabled={busy}>{busy ? 'Identificando…' : 'Ingresar con ID'}</button></form></div></div></Shell>
}

export function AccesoQR() {
  const { client } = useSession()
  const video = useRef(null)
  const stream = useRef(null)
  const [camera, setCamera] = useState(false)
  const [credential, setCredential] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [cameraMessage, setCameraMessage] = useState('')
  async function identify(value) {
    setBusy(true); setError(null); setCamera(false)
    try { await client.login('qr', value); navigate('/inicio') }
    catch (err) { setError(err.status === 401 ? new Error('QR no registrado o cuenta inactiva. Revisa la credencial o usa tu ID universitario.') : err) }
    finally { setBusy(false) }
  }
  useEffect(() => {
    if (!camera) return
    let active = true
    let timer
    async function start() {
      try {
        if (!navigator.mediaDevices?.getUserMedia || !window.BarcodeDetector || !(await window.BarcodeDetector.getSupportedFormats()).includes('qr_code')) {
          throw new Error('La lectura de QR con cámara no está disponible en este navegador. Usa tu ID universitario o pega el contenido del QR.')
        }
        const media = await navigator.mediaDevices.getUserMedia({ video: { facingMode: { ideal: 'environment' } }, audio: false })
        if (!active) { media.getTracks().forEach((track) => track.stop()); return }
        stream.current = media
        video.current.srcObject = media
        await video.current.play()
        const detector = new window.BarcodeDetector({ formats: ['qr_code'] })
        setCameraMessage('Esperando la lectura del código QR…')
        async function scan() {
          if (!active) return
          try {
            const codes = await detector.detect(video.current)
            if (codes[0]?.rawValue) { if (active) await identify(codes[0].rawValue); return }
          } catch { /* A frame may not yet be ready. */ }
          if (active) timer = setTimeout(scan, 250)
        }
        scan()
      } catch (err) { if (active) { setCameraMessage(err.name === 'NotAllowedError' ? 'No se permitió el acceso a la cámara. Usa tu ID universitario o pega el contenido del QR.' : err.message); setCamera(false) } }
    }
    start()
    return () => { active = false; clearTimeout(timer); stream.current?.getTracks().forEach((track) => track.stop()); stream.current = null }
  }, [camera])
  return <Shell sinNav><PageHeader titulo="Escanea tu credencial" subtitulo="Coloca el código QR dentro del recuadro." /><div className="container content"><div className="col-principal pila"><div className="visor"><video ref={video} muted playsInline aria-label="Vista de cámara" /></div><p className="note" role="status">{cameraMessage || 'Activa la cámara para leer tu credencial.'}</p><div className="actions"><button className="btn btn--primary" disabled={busy} onClick={() => { setCameraMessage('Abriendo cámara…'); setCamera((value) => !value) }}>{camera ? 'Detener cámara' : 'Activar cámara'}</button><Link to="/acceso" className="btn btn--secondary">Usar ID universitario</Link></div><form className="card pila" onSubmit={(event) => { event.preventDefault(); identify(credential) }}><Field label="Contenido del QR" hint="Alternativa para una credencial digital o un lector externo."><input className="field" value={credential} onChange={(event) => setCredential(event.target.value)} required maxLength={256} autoComplete="off" /></Field><button className="btn btn--secondary" disabled={busy}>{busy ? 'Identificando…' : 'Ingresar con QR'}</button></form><ErrorNotice error={error} /></div></div></Shell>
}

