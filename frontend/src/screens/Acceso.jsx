import { useCallback, useEffect, useRef, useState } from 'react'
import { Shell, PageHeader, Field, ErrorNotice } from '../components.jsx'
import { Link } from '../router.jsx'
import { navigate } from '../navigation.js'
import { useSession } from '../hooks.js'
import { prepareQrCamera, retainQrCamera, releaseQrCamera, stopQrCamera, getQrCameraError, hasQrCamera } from '../qr-camera.js'
import { createQrDecoder } from '../qr-decoder.js'

function useErrorFocus(error) {
  const target = useRef(null)
  useEffect(() => {
    if (!error || !target.current) return
    target.current.focus({ preventScroll: true })
    target.current.scrollIntoView?.({
      block: 'center',
      behavior: window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth',
    })
  }, [error])
  return target
}

function useMounted() {
  const mounted = useRef(true)
  useEffect(() => { mounted.current = true; return () => { mounted.current = false } }, [])
  return mounted
}

export function Acceso() {
  const { client } = useSession()
  const [credential, setCredential] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const [opening, setOpening] = useState(false)
  const mounted = useMounted()
  const errorTarget = useErrorFocus(error)

  async function submit(event) {
    event.preventDefault(); setBusy(true); setError(null)
    try { await client.login('id', credential, password); navigate('/inicio') }
    catch (err) { setError(err.status === 401 ? new Error('ID o clave incorrectos. Revisa los datos y vuelve a intentar.') : err) }
    finally { setBusy(false) }
  }
  async function scanQr() {
    setOpening(true)
    try { await prepareQrCamera() } catch { /* The reader view presents the camera error and alternatives. */ }
    if (mounted.current) navigate('/acceso/qr')
    else stopQrCamera()
    if (mounted.current) setOpening(false)
  }

  return <Shell sinNav>
    <PageHeader titulo="Identifícate para continuar" subtitulo="Accede al laboratorio con tu credencial universitaria." />
    <div className="container content"><div className="opciones">
      <section className="card opcion">
        <h2>Opción 1 · QR</h2>
        <p className="note">Abre la cámara y escanea tu credencial registrada.</p>
        <button className="btn btn--primary" disabled={opening || busy} onClick={scanQr}>{opening ? 'Abriendo cámara…' : 'Escanear QR'}</button>
      </section>
      <form className="card opcion" onSubmit={submit}>
        <h2>Opción 2 · ID universitario</h2>
        <p className="note">Escribe tu identificador institucional y tu clave.</p>
        <Field label="ID universitario"><input className="field" value={credential} onChange={(event) => setCredential(event.target.value)} required maxLength={256} autoComplete="username" /></Field>
        <Field label="Clave"><input className="field" type="password" value={password} onChange={(event) => setPassword(event.target.value)} required minLength={12} maxLength={128} autoComplete="current-password" /></Field>
        {error && <div ref={errorTarget} tabIndex="-1" className="access-error"><ErrorNotice error={error} /></div>}
        <button className="btn btn--secondary" disabled={busy || opening}>{busy ? 'Identificando…' : 'Ingresar con ID'}</button>
      </form>
    </div></div>
  </Shell>
}

export function AccesoQR() {
  const { client } = useSession()
  const video = useRef(null)
  const identifying = useRef(false)
  const mounted = useMounted()
  const [cameraVersion, setCameraVersion] = useState(0)
  const [running, setRunning] = useState(hasQrCamera)
  const [opening, setOpening] = useState(false)
  const [credential, setCredential] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(getQrCameraError)
  const errorTarget = useErrorFocus(error)

  const identify = useCallback(async (value) => {
    if (identifying.current) return
    identifying.current = true
    setBusy(true); setError(null); setRunning(false); stopQrCamera()
    try { await client.login('qr', value); navigate('/inicio') }
    catch (err) {
      if (mounted.current) setError(err.status === 401
        ? new Error('No se pudo validar el QR. Revisa la credencial o usa tu ID universitario.')
        : err)
    } finally {
      identifying.current = false
      if (mounted.current) setBusy(false)
    }
  }, [client, mounted])

  useEffect(() => {
    const media = retainQrCamera()
    if (!media) return
    let active = true
    let timer
    const element = video.current
    element.srcObject = media
    async function start() {
      try {
        await element.play()
        if (!active) return
        const decode = await createQrDecoder()
        if (!active) return
        async function scan() {
          if (!active || !hasQrCamera()) return
          try {
            const value = await decode(element)
            if (value) {
              if (active && hasQrCamera()) await identify(value)
              return
            }
          } catch (err) {
            if (err.name !== 'InvalidStateError') {
              if (active) { stopQrCamera(); setRunning(false); setError(err) }
              return
            }
          }
          if (active) timer = setTimeout(scan, 250)
        }
        scan()
      } catch {
        if (active) {
          stopQrCamera(); setRunning(false)
          setError(new Error('No se pudo mostrar la cámara. Reintenta o usa tu ID universitario.'))
        }
      }
    }
    start()
    window.addEventListener('pagehide', stopQrCamera)
    return () => {
      active = false; clearTimeout(timer); element.srcObject = null
      window.removeEventListener('pagehide', stopQrCamera)
      releaseQrCamera()
    }
  }, [cameraVersion, identify])

  async function retryCamera() {
    setOpening(true); setError(null)
    try {
      await prepareQrCamera()
      if (mounted.current) { setRunning(true); setCameraVersion((value) => value + 1) }
      else stopQrCamera()
    } catch (err) { if (mounted.current) setError(err) }
    finally { if (mounted.current) setOpening(false) }
  }

  return <Shell sinNav>
    <PageHeader titulo="Escanea tu credencial" subtitulo="Coloca el código QR dentro del recuadro." />
    <div className="container content"><div className="col-principal pila qr-reader">
      <div className="visor"><video ref={video} muted playsInline aria-label="Vista de cámara" /></div>
      <p className="note" role="status">{busy ? 'Validando credencial…' : running ? 'Esperando la lectura del código QR…' : 'La cámara no está iniciada. Puedes reintentar o usar otra forma de acceso.'}</p>
      {error && <div ref={errorTarget} tabIndex="-1" className="access-error"><ErrorNotice error={error} /></div>}
      <div className="actions">
        {!running && <button className="btn btn--secondary" disabled={busy || opening} onClick={retryCamera}>{opening ? 'Abriendo cámara…' : 'Reintentar cámara'}</button>}
        <Link to="/acceso" className="btn btn--secondary">Usar ID universitario</Link>
      </div>
      <details className="qr-manual">
        <summary>Ingresar QR manualmente</summary>
        <form className="pila" onSubmit={(event) => { event.preventDefault(); identify(credential) }}>
          <Field label="Contenido del QR" hint="Para una credencial digital o un lector externo."><input className="field" value={credential} onChange={(event) => setCredential(event.target.value)} required maxLength={256} autoComplete="off" /></Field>
          <button className="btn btn--secondary" disabled={busy}>{busy ? 'Identificando…' : 'Ingresar con QR'}</button>
        </form>
      </details>
    </div></div>
  </Shell>
}
