import { Shell, PageHeader } from '../components.jsx'
import { Link, navigate, useAutoAdvance } from '../router.jsx'
import { USUARIO } from '../data.js'

export function Acceso() {
  return (
    <Shell sinNav>
      <PageHeader titulo="Identifícate para continuar" subtitulo="Accede al stand con tu credencial universitaria." />
      <div className="container content">
        <div className="opciones">
          <section className="card opcion">
            <h2>Opción 1 · QR</h2>
            <p className="note">Abre la cámara y escanea tu credencial.</p>
            <Link to="/acceso/qr" className="btn btn--primary">
              Escanear QR
            </Link>
          </section>
          <form
            className="card opcion"
            onSubmit={(e) => {
              e.preventDefault()
              navigate('/inicio')
            }}
          >
            <h2>Opción 2 · ID universitario</h2>
            <p className="note">Escribe el número de tu credencial.</p>
            <label className="label label--sm" htmlFor="id-universitario">
              ID universitario
            </label>
            <input id="id-universitario" className="field" inputMode="numeric" defaultValue={USUARIO.id} />
            <button className="btn btn--secondary">Ingresar con ID</button>
          </form>
        </div>
      </div>
    </Shell>
  )
}

export function AccesoQR() {
  // La maqueta simula una lectura correcta y pasa a Inicio.
  const pausa = useAutoAdvance('/inicio')
  return (
    <Shell sinNav>
      <PageHeader titulo="Escanea tu credencial" subtitulo="Coloca el código QR dentro del recuadro." />
      <div className="container content">
        <div className="col-principal">
          <div className="visor" aria-label="Vista de cámara simulada">
            <div className="visor__marco">
              <span className="visor__qr" />
            </div>
          </div>
          <p className="note" role="status">
            Esperando la lectura del código QR…
          </p>
          <div className="actions" {...pausa}>
            <Link to="/acceso" className="btn btn--secondary">
              Usar ID universitario
            </Link>
          </div>
        </div>
      </div>
    </Shell>
  )
}
