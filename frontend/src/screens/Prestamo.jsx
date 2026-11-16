import { useState } from 'react'
import { Shell, PageHeader, Summary, Esperando, Aviso } from '../components.jsx'
import { Link, navigate, useAutoAdvance } from '../router.jsx'
import { RECURSOS, RECURSO_REFERENCIA, USUARIO, DESTINATARIO, buscarRecurso } from '../data.js'

// `prestamo` = { recursoId, modo: 'propio' | 'delegado' }. Vive en App mientras dura la sesión.

export function PrestamoForm({ id0, setPrestamo }) {
  const prestables = RECURSOS.filter((r) => r.estado === 'Disponible')
  const inicial = prestables.some((r) => r.id === id0) ? id0 : RECURSO_REFERENCIA
  const [recursoId, setRecursoId] = useState(inicial)
  const recurso = buscarRecurso(recursoId)

  const continuar = (modo) => {
    setPrestamo({ recursoId, modo })
    navigate('/prestamo/retiro')
  }

  return (
    <Shell activo="prestamos">
      <PageHeader titulo="Registrar préstamo" subtitulo="Prepara la operación antes de retirar el recurso." />
      <div className="container content">
        <div className="dos-col">
          <div>
            <label className="label label--sm" htmlFor="recurso">
              Recurso
            </label>
            <select id="recurso" className="field" value={recursoId} onChange={(e) => setRecursoId(e.target.value)}>
              {prestables.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.nombre} · {r.estado}
                </option>
              ))}
            </select>

            <h2 className="seccion seccion--sm">¿Para quién es el préstamo?</h2>
            <label className="label label--sm" htmlFor="destinatario">
              Destinatario (si es otra persona)
            </label>
            <input id="destinatario" className="field" placeholder="Opcional · escribe ID del destinatario" />

            <label className="label label--sm" htmlFor="fecha">
              Fecha prevista de devolución
            </label>
            <input id="fecha" className="field" defaultValue="30 sep 2026 · 5:00 p. m." />
            <p className="note">El responsable puede ser distinto de quien retira el objeto.</p>

            <div className="actions">
              <button type="button" className="btn btn--primary" onClick={() => continuar('propio')}>
                Continuar para mí
              </button>
              <button type="button" className="btn btn--secondary" onClick={() => continuar('delegado')}>
                Continuar para otra persona
              </button>
              <Link to={`/recurso/${recursoId}/ubicacion`} className="btn btn--secondary">
                Ver ubicación
              </Link>
            </div>
          </div>
          <Summary
            titulo="Resumen del préstamo"
            items={[
              ['Recurso', recurso.nombre],
              ['Responsable', 'Propio o destinatario'],
              ['Registro', 'Se confirma al retirar'],
            ]}
          />
        </div>
      </div>
    </Shell>
  )
}

export function Retiro({ prestamo }) {
  const r = buscarRecurso(prestamo.recursoId)
  const delegado = prestamo.modo === 'delegado'
  // Representa el evento físico del lector: avanza solo después de 1,8 s.
  const pausa = useAutoAdvance('/prestamo/comprobante')
  return (
    <Shell activo="prestamos">
      <PageHeader titulo="Retira el recurso del stand" />
      <div className="container content">
        <div className="col-principal">
          <section className="card">
            <h2>{r.nombre}</h2>
            <p className="note">{r.id}</p>
            <p className="note">
              {delegado ? `Para ${DESTINATARIO.completo} · Entrega ${USUARIO.completo}` : `Para ${USUARIO.completo}`}
            </p>
            <Esperando />
          </section>
          <div className="actions" {...pausa}>
            <Link to="/inicio" className="btn btn--secondary">
              Cancelar
            </Link>
            <Link to="/prestamo/inesperado" className="btn btn--ghost btn--demo">
              Simular lectura distinta
            </Link>
          </div>
        </div>
      </div>
    </Shell>
  )
}

export function ComprobanteRetiro({ prestamo }) {
  const r = buscarRecurso(prestamo.recursoId)
  const delegado = prestamo.modo === 'delegado'
  return (
    <Shell activo="prestamos">
      <PageHeader titulo="Préstamo registrado" subtitulo="El lector RFID confirmó el retiro del recurso." />
      <div className="container content">
        <div className="col-principal">
          <section className="card card--ok" role="status">
            <h2>{r.nombre}</h2>
            <p>Responsable: {delegado ? DESTINATARIO.completo : USUARIO.completo} · Retirado: 2:35 p. m.</p>
            {delegado && <p>Entregado por {USUARIO.completo}</p>}
          </section>
          <div className="actions">
            {delegado ? (
              <Link to="/prestamo" className="btn btn--primary">
                Nuevo préstamo
              </Link>
            ) : (
              <Link to="/mis-recursos" className="btn btn--primary">
                Ver mis recursos
              </Link>
            )}
            <Link to="/inicio" className="btn btn--secondary">
              Ir al inicio
            </Link>
          </div>
        </div>
      </div>
    </Shell>
  )
}

export function RecursoInesperado({ prestamo }) {
  const r = buscarRecurso(prestamo.recursoId)
  return (
    <Shell activo="prestamos">
      <PageHeader titulo="Recurso inesperado" />
      <div className="container content">
        <div className="col-principal">
          <Aviso
            ocurrio={['El préstamo no se registró.', `Esperado: ${r.nombre}`, 'Detectado: Otro recurso']}
            paso="Retira el recurso seleccionado y reintenta la lectura."
          />
          <div className="actions">
            <Link to="/prestamo/retiro" className="btn btn--primary">
              Reintentar lectura
            </Link>
            <Link to="/prestamo/sin-responsable" className="btn btn--ghost btn--demo">
              Ver otra excepción
            </Link>
          </div>
        </div>
      </div>
    </Shell>
  )
}

export function SinResponsable() {
  return (
    <Shell activo="prestamos">
      <PageHeader titulo="Movimiento sin responsable" />
      <div className="container content">
        <div className="col-principal">
          <Aviso
            ocurrio={['Se detectó un retiro sin una persona responsable asignada.', 'El movimiento sigue sin registrar.']}
            paso="Indica para quién es el préstamo y vuelve a retirar el recurso."
          />
          <div className="actions">
            <Link to="/prestamo" className="btn btn--primary">
              Asignar responsable
            </Link>
          </div>
        </div>
      </div>
    </Shell>
  )
}
