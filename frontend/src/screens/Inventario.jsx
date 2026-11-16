import { useState } from 'react'
import { Shell, PageHeader, ResourceRow, ShelfMap } from '../components.jsx'
import { Link } from '../router.jsx'
import { RECURSOS, ZONA, buscarRecurso } from '../data.js'

const sinTildes = (s) => s.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase()

export function Inventario({ q0 = '' }) {
  const [q, setQ] = useState(q0)
  const [filtro, setFiltro] = useState('todos')

  const disponibles = RECURSOS.filter((r) => r.estado === 'Disponible').length
  const filtros = [
    ['todos', `Todos · ${RECURSOS.length}`],
    ['disponibles', `${disponibles} disponibles`],
    ['no-disponibles', `${RECURSOS.length - disponibles} no disponibles`],
  ]

  const visibles = RECURSOS.filter((r) => {
    if (filtro === 'disponibles' && r.estado !== 'Disponible') return false
    if (filtro === 'no-disponibles' && r.estado === 'Disponible') return false
    return sinTildes(`${r.nombre} ${r.id} ${r.categoria}`).includes(sinTildes(q.trim()))
  })

  return (
    <Shell activo="inventario">
      <PageHeader titulo="Buscar recursos" subtitulo="Explora recursos reutilizables del laboratorio." />
      <div className="container content">
        <label className="label label--sm" htmlFor="buscar-recurso">
          Buscar recurso
        </label>
        <input
          id="buscar-recurso"
          className="field"
          placeholder="Buscar por nombre, código o categoría"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
        <div className="filtros" role="group" aria-label="Filtrar por disponibilidad">
          {filtros.map(([clave, texto]) => (
            <button key={clave} type="button" aria-pressed={filtro === clave} onClick={() => setFiltro(clave)}>
              {texto}
            </button>
          ))}
        </div>
        {visibles.length ? (
          <div className="rows rows--2">
            {visibles.map((r) => (
              <ResourceRow key={r.id} recurso={r} />
            ))}
          </div>
        ) : (
          <p className="note vacio">Ningún recurso coincide con la búsqueda. Prueba con otro nombre, código o categoría.</p>
        )}
      </div>
    </Shell>
  )
}

export function Ficha({ id }) {
  const r = buscarRecurso(id)
  const disponible = r.estado === 'Disponible'
  const claseEstado = disponible ? 'ok' : r.estado === 'En revisión' ? 'revision' : 'neutro'
  return (
    <Shell activo="inventario">
      <PageHeader titulo={r.nombre} subtitulo={`${r.categoria} · ${r.tipo} · ${r.id}`} />
      <div className="container content">
        <div className="col-principal">
          <dl className="card ficha">
            <div>
              <dt className="note">Disponibilidad</dt>
              <dd className={`ficha__estado ficha__estado--${claseEstado}`}>{r.estado}</dd>
            </div>
            <div>
              <dt>Ubicación asignada</dt>
              <dd>
                {ZONA} → Gabinete {r.gab} → Estante {r.estante} → Posición {r.pos}
              </dd>
            </div>
            <div>
              <dt>Estado físico</dt>
              <dd>{r.estado === 'En revisión' ? 'En revisión · Mantenimiento pendiente' : 'Operativo · Última revisión: 18 sep 2026'}</dd>
            </div>
          </dl>
          <div className="actions">
            {disponible ? (
              <>
                <Link to={`/prestamo?id=${r.id}`} className="btn btn--primary">
                  Registrar préstamo
                </Link>
                <Link to={`/recurso/${r.id}/ubicacion`} className="btn btn--secondary">
                  Ver ubicación
                </Link>
                <Link to="/inventario" className="btn btn--ghost">
                  Volver al inventario
                </Link>
              </>
            ) : (
              <>
                <Link to="/inventario" className="btn btn--primary">
                  Volver al inventario
                </Link>
                <Link to={`/recurso/${r.id}/ubicacion`} className="btn btn--secondary">
                  Ver ubicación
                </Link>
              </>
            )}
          </div>
        </div>
      </div>
    </Shell>
  )
}

export function Ubicacion({ id }) {
  const r = buscarRecurso(id)
  return (
    <Shell activo="inventario">
      <PageHeader titulo="Encuentra el recurso" subtitulo="Sigue la guía hasta el espacio asignado." />
      <div className="container content">
        <div className="col-principal">
          <ShelfMap recurso={r} leyenda={`Posición ${r.pos} · indicador luminoso`} />
          <div className="actions">
            {r.estado === 'Disponible' && (
              <Link to={`/prestamo?id=${r.id}`} className="btn btn--primary">
                Registrar préstamo
              </Link>
            )}
            <Link to={`/recurso/${r.id}`} className="btn btn--secondary">
              Volver a la ficha
            </Link>
          </div>
        </div>
      </div>
    </Shell>
  )
}
