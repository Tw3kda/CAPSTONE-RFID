import { Shell, PageHeader, Summary, ShelfMap, Esperando, Aviso } from '../components.jsx'
import { Link, useAutoAdvance } from '../router.jsx'
import { RECURSO_REFERENCIA, USUARIO, buscarRecurso } from '../data.js'

// El recorrido transaccional de referencia usa siempre el multímetro ACT-004.
const r = buscarRecurso(RECURSO_REFERENCIA)

export function MisRecursos() {
  return (
    <Shell activo="mis-recursos">
      <PageHeader titulo="Mis recursos" subtitulo="Consulta pendientes por devolver e historial." />
      <div className="container content">
        <p className="pildora">Pendientes por devolver · 1</p>
        <div className="dos-col">
          <div className="pila">
            <Link to="/mis-recursos/prestamo" className="card card--link">
              <h2 className="h-sm">{r.nombre}</h2>
              <p className="flechita" aria-hidden="true">›</p>
              <p className="note">Desde: 27 sep, 2:35 p. m. · Devolver: 30 sep, 5:00 p. m.</p>
            </Link>
            <h2 className="seccion seccion--sm">Historial</h2>
            <section className="card">
              <h2 className="h-sm">Kit de electrónica #07</h2>
              <p className="note">Devuelto: 23 sep · Sin pendientes</p>
            </section>
            <div className="actions">
              <Link to="/devolucion" className="btn btn--secondary">
                Devolver recurso
              </Link>
            </div>
          </div>
          <Summary
            titulo="Tus préstamos"
            items={[
              ['Activos', '1 pendiente'],
              ['Historial', 'Movimientos anteriores'],
              ['Devolución', 'Consulta ubicación'],
            ]}
          />
        </div>
      </div>
    </Shell>
  )
}

export function DetallePrestamo() {
  return (
    <Shell activo="mis-recursos">
      <PageHeader titulo="Detalle del préstamo" subtitulo={`${r.nombre} · Préstamo activo`} />
      <div className="container content">
        <div className="col-principal">
          <dl className="card ficha">
            <div>
              <dt className="sr-only">Estado</dt>
              <dd className="ficha__estado ficha__estado--revision">Pendiente por devolver</dd>
            </div>
            <div>
              <dt>Responsable</dt>
              <dd>
                {USUARIO.completo} · ID {USUARIO.id}
              </dd>
            </div>
            <div>
              <dt>Movimiento registrado</dt>
              <dd>Retirado: 27 sep, 2:35 p. m. · Entrega prevista: 30 sep</dd>
            </div>
            <div>
              <dt>Ubicación asignada</dt>
              <dd>
                Gabinete {r.gab} → Estante {r.estante} → Posición {r.pos}
              </dd>
            </div>
          </dl>
          <div className="actions">
            <Link to="/devolucion/lectura" className="btn btn--primary">
              Devolver recurso
            </Link>
            <Link to={`/recurso/${r.id}/ubicacion`} className="btn btn--secondary">
              Ver ubicación asignada
            </Link>
            <Link to="/mis-recursos" className="btn btn--ghost">
              Volver a mis recursos
            </Link>
          </div>
        </div>
      </div>
    </Shell>
  )
}

export function DevolucionSeleccion() {
  return (
    <Shell activo="mis-recursos">
      <PageHeader titulo="Devolver recurso" subtitulo="Selecciona uno de tus préstamos pendientes." />
      <div className="container content">
        <div className="dos-col">
          <div className="pila">
            <Link to="/devolucion/lectura" className="card card--link">
              <h2 className="h-sm">{r.nombre}</h2>
              <p className="flechita" aria-hidden="true">›</p>
              <p className="note">Préstamo activo · Responsable: {USUARIO.completo}</p>
            </Link>
            <p className="note">Selecciona el préstamo y presenta el objeto al lector RFID.</p>
            <div className="actions">
              <Link to="/mis-recursos" className="btn btn--secondary">
                Volver a mis recursos
              </Link>
            </div>
          </div>
          <Summary
            titulo="Selecciona un préstamo"
            items={[
              ['Activos', '1 pendiente'],
              ['Recurso', r.nombre],
              ['Siguiente', 'Preséntalo al stand'],
            ]}
          />
        </div>
      </div>
    </Shell>
  )
}

export function DevolucionLectura() {
  // Lectura coincidente: avanza sola a la guía de posición.
  const pausa = useAutoAdvance('/devolucion/ubicacion')
  return (
    <Shell activo="mis-recursos">
      <PageHeader titulo="Presenta el recurso al stand" />
      <div className="container content">
        <div className="col-principal">
          <section className="card">
            <h2>{r.nombre}</h2>
            <p className="note">{r.id}</p>
            <Esperando />
            <p className="note">Después de la lectura, sigue la guía de ubicación.</p>
          </section>
          <div className="actions" {...pausa}>
            <Link to="/mis-recursos" className="btn btn--secondary">
              Cancelar
            </Link>
            <Link to="/devolucion/incorrecto" className="btn btn--ghost btn--demo">
              Simular lectura distinta
            </Link>
          </div>
        </div>
      </div>
    </Shell>
  )
}

export function DevolucionUbicacion() {
  return (
    <Shell activo="mis-recursos">
      <PageHeader titulo="Colócalo en su posición" subtitulo="RFID validado. Confirma la ubicación después de colocar el recurso." />
      <div className="container content">
        <div className="col-principal">
          <ShelfMap recurso={r} leyenda={`Coloca el recurso en la posición ${r.pos} y confirma.`} />
          <div className="actions">
            <Link to="/devolucion/comprobante" className="btn btn--primary">
              Confirmar ubicación
            </Link>
            <Link to="/devolucion/no-confirmada" className="btn btn--secondary">
              Reportar problema
            </Link>
          </div>
        </div>
      </div>
    </Shell>
  )
}

export function ComprobanteDevolucion() {
  return (
    <Shell activo="mis-recursos">
      <PageHeader titulo="Devolución completada" subtitulo="El lector RFID verificó el recurso y confirmaste su ubicación." />
      <div className="container content">
        <div className="col-principal">
          <section className="card card--ok" role="status">
            <h2>{r.nombre}</h2>
            <p>
              Devuelto: 4:48 p. m. · Ubicación declarada: {r.gab}-{r.estante}-{r.pos}
            </p>
            <p className="texto-ok">Estado: Disponible</p>
          </section>
          <div className="actions">
            <Link to="/mis-recursos" className="btn btn--primary">
              Ver mis recursos
            </Link>
            <Link to="/inicio" className="btn btn--secondary">
              Ir al inicio
            </Link>
          </div>
        </div>
      </div>
    </Shell>
  )
}

export function RecursoIncorrecto() {
  return (
    <Shell activo="mis-recursos">
      <PageHeader titulo="Recurso incorrecto" />
      <div className="container content">
        <div className="col-principal">
          <Aviso
            ocurrio={['El préstamo sigue pendiente.', `Esperado: ${r.nombre}`, 'Detectado: Otro recurso']}
            paso="Presenta el recurso de este préstamo y reintenta la lectura."
          />
          <div className="actions">
            <Link to="/devolucion/lectura" className="btn btn--primary">
              Reintentar lectura
            </Link>
          </div>
        </div>
      </div>
    </Shell>
  )
}

export function UbicacionNoConfirmada() {
  return (
    <Shell activo="mis-recursos">
      <PageHeader titulo="Ubicación no confirmada" />
      <div className="container content">
        <div className="col-principal">
          <Aviso
            ocurrio={['No se confirmó la posición del recurso.', 'La devolución sigue pendiente.']}
            paso={`Consulta la guía y coloca el recurso en Gabinete ${r.gab}, Estante ${r.estante}, Posición ${r.pos}.`}
          />
          <div className="actions">
            <Link to="/devolucion/ubicacion" className="btn btn--primary">
              Ver ubicación
            </Link>
          </div>
        </div>
      </div>
    </Shell>
  )
}
