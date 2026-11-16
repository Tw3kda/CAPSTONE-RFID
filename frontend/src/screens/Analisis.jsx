import { useState } from 'react'
import { Shell, PageHeader, ResourceRow } from '../components.jsx'
import { Link } from '../router.jsx'
import { REUTILIZABLES, USO_SEMANAL, buscarRecurso } from '../data.js'

const MAX_USO = Math.max(...USO_SEMANAL.map((s) => s.usos))

export function Analisis() {
  // 'nueva' → aún no se genera · 'abierta' → visible · 'oculta' → generada pero plegada
  const [reco, setReco] = useState('nueva')
  const textoBoton = { nueva: 'Generar recomendación', abierta: 'Ocultar recomendación', oculta: 'Ver recomendación' }[reco]

  return (
    <Shell activo="analisis">
      <PageHeader titulo="Uso responsable de recursos" subtitulo="Reutilización y mantenimiento para reducir el desperdicio." />
      <div className="container content">
        <p className="note">Últimos 30 días · Laboratorio de electrónica</p>

        <div className="indicadores">
          {[
            [9, 'Recursos disponibles'],
            [3, 'Con poco uso'],
            [1, 'En revisión'],
          ].map(([n, texto]) => (
            <div key={texto} className="card indicador">
              <strong>{n}</strong>
              <span className="note">{texto}</span>
            </div>
          ))}
        </div>

        <div className="analisis-grid">
          <section className="card">
            <h2>Uso de recursos por semana</h2>
            <p className="note">El historial ayuda a identificar recursos infrautilizados.</p>
            <ol className="barras" aria-label="Usos por semana">
              {USO_SEMANAL.map((s) => (
                <li key={s.semana}>
                  <strong>{s.usos}</strong>
                  <span className="barras__barra" style={{ height: `${(s.usos / MAX_USO) * 84}px` }} />
                  <span className="note">{s.semana}</span>
                </li>
              ))}
            </ol>
          </section>
          <div className="pila">
            <section className="card">
              <h2>Recursos para aprovechar</h2>
              <ul className="lista-simple">
                {REUTILIZABLES.map((id) => (
                  <li key={id}>{buscarRecurso(id).nombre}</li>
                ))}
              </ul>
            </section>
            <section className="card">
              <h2>Prolongar la vida útil</h2>
              <p className="note note--fuerte">1 equipo en revisión. Evaluar mantenimiento antes de reemplazarlo.</p>
            </section>
          </div>
        </div>

        <section className="card reco">
          <h2>Recomendación de IA</h2>
          <p className="note">Genera una sugerencia de reutilización o mantenimiento con los datos del periodo.</p>
          <button
            type="button"
            className="btn btn--primary"
            aria-expanded={reco === 'abierta'}
            aria-controls="reco-detalle"
            onClick={() => setReco(reco === 'abierta' ? 'oculta' : 'abierta')}
          >
            {textoBoton}
          </button>
          {reco === 'abierta' && (
            <div id="reco-detalle" className="reco__detalle">
              <p>
                Antes de adquirir nuevos equipos, revisa los recursos disponibles con poco uso. Aprovecharlos y mantenerlos puede evitar
                compras y residuos innecesarios.
              </p>
              <h3>Aprovecha los recursos existentes</h3>
              <p>
                La IA identifica tres recursos disponibles con poco uso. Revisa si cubren la necesidad de tu práctica antes de solicitar
                nuevos equipos.
              </p>
              <h3>¿Qué muestra el inventario?</h3>
              <p>9 recursos disponibles y 3 con poco uso en el periodo.</p>
              <p>1 equipo en revisión: evaluar reparación antes de reemplazarlo.</p>
              <p>La trazabilidad ayuda a evitar adquisiciones duplicadas y descartes prematuros.</p>
              <h3>Cómo reducir desperdicio</h3>
              <ol>
                <li>Verifica compatibilidad y estado del recurso.</li>
                <li>Reutiliza lo disponible para tu práctica.</li>
                <li>Prioriza mantenimiento antes de sustituir equipos.</li>
              </ol>
              <Link to="/analisis/reutilizar" className="btn btn--primary">
                Ver recursos disponibles
              </Link>
            </div>
          )}
        </section>
      </div>
    </Shell>
  )
}

export function Reutilizar() {
  return (
    <Shell activo="analisis">
      <PageHeader titulo="Recursos para reutilizar" subtitulo="Abre una ficha para comprobar estado, ubicación y disponibilidad." />
      <div className="container content">
        <div className="col-principal">
          <div className="rows">
            {REUTILIZABLES.map((id) => (
              <ResourceRow key={id} recurso={buscarRecurso(id)} />
            ))}
          </div>
          <div className="actions">
            <Link to="/analisis" className="btn btn--primary">
              Volver al análisis
            </Link>
          </div>
        </div>
      </div>
    </Shell>
  )
}
