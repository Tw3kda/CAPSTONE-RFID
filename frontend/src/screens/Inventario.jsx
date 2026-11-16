import { useState } from 'react'
import { Page, LoadState, ResourceRow, ShelfMap, Field, ErrorNotice } from '../components.jsx'
import { stateLabel, locationText, formatDate } from '../presentation.js'
import { Link } from '../router.jsx'

import { useApi, useMutation } from '../hooks.js'
import { queryString } from '../api.js'

export function Inventario({ q0 = '' }) {
  const [query, setQuery] = useState(q0)
  const [search, setSearch] = useState(q0)
  const [category, setCategory] = useState('')
  const [state, setState] = useState('')
  const categories = useApi('/categorias')
  const assets = useApi(`/activos${queryString({ q: search, categoria_id: category, estado: state })}`)
  return <Page activo="inventario" titulo="Buscar recursos" subtitulo="Explora los recursos del laboratorio."><form className="inventory-search" onSubmit={(event) => { event.preventDefault(); setSearch(query.trim()) }}><Field label="Buscar recurso"><input className="field" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Buscar por nombre o código" /></Field><Field label="Categoría"><select className="field" value={category} onChange={(event) => setCategory(event.target.value)}><option value="">Todas las categorías</option>{categories.data?.map((item) => <option key={item.id} value={item.id}>{item.nombre}</option>)}</select></Field><button className="btn btn--primary">Buscar</button></form><ErrorNotice error={categories.error} retry={categories.reload} /><div className="filtros" role="group" aria-label="Filtrar por disponibilidad">{[['','Todos'],['disponible','Disponibles'],['prestado','Prestados'],['en_revision','En revisión']].map(([value,label]) => <button key={value} type="button" aria-pressed={state === value} onClick={() => setState(value)}>{label}</button>)}</div><LoadState request={assets}>{(items) => items.length ? <><p className="note" role="status">{items.length} recursos encontrados</p><div className="rows rows--2">{items.map((item) => <ResourceRow key={item.id} recurso={item} />)}</div></> : <p className="vacio note">Ningún recurso coincide con la búsqueda. Prueba con otro nombre, código o categoría.</p>}</LoadState></Page>
}
export function Ficha({ id }) {
  const asset = useApi(`/activos/${id}`)
  const history = useApi(`/activos/${id}/historial`)
  return <Page activo="inventario" titulo={asset.data?.nombre || 'Ficha del recurso'} subtitulo={asset.data ? `${asset.data.categoria} · ${asset.data.codigo}` : undefined}><LoadState request={asset}>{(item) => <div className="col-principal"><dl className="card ficha"><div><dt className="note">Disponibilidad</dt><dd className={`ficha__estado ficha__estado--${item.estado === 'disponible' ? 'ok' : item.estado === 'en_revision' ? 'revision' : 'neutro'}`}>{stateLabel(item.estado)}</dd></div><div><dt>Ubicación asignada</dt><dd>{locationText(item.ubicacion)}</dd></div><div><dt>Estado físico</dt><dd>{item.condicion || 'Sin condición registrada'} · Última revisión: {formatDate(item.ultima_revision_at)}</dd></div></dl><div className="actions">{item.estado === 'disponible' && <Link to={`/prestamo?id=${item.id}`} className="btn btn--primary">Registrar préstamo</Link>}<Link to={`/recurso/${item.id}/ubicacion`} className="btn btn--secondary">Ver ubicación</Link><Link to="/inventario" className="btn btn--secondary">Volver al inventario</Link></div><h2 className="seccion--sm">Historial de movimientos</h2><LoadState request={history}>{(items) => items.length ? <ul className="card pila">{items.map((movement) => <li key={movement.id}><strong>{movement.tipo}</strong><p className="note">{formatDate(movement.ocurrido_at)}{movement.ubicacion && ` · ${locationText(movement.ubicacion)}`}</p></li>)}</ul> : <p className="note">Sin movimientos registrados.</p>}</LoadState></div>}</LoadState></Page>
}
export function Ubicacion({ id }) {
  const asset = useApi(`/activos/${id}`)
  const map = useApi(`/activos/${id}/ubicacion`)
  const action = useMutation()
  const [requested, setRequested] = useState(false)
  return <Page activo="inventario" titulo="Encuentra el recurso" subtitulo="Sigue la guía hasta el espacio asignado."><div className="col-principal pila"><LoadState request={map}>{(value) => <ShelfMap mapa={value} />}</LoadState><ErrorNotice error={action.error} />{requested && <p className="card card--ok" role="status">Señal solicitada al dispositivo. El indicador se activará cuando el ESP32 reciba la solicitud.</p>}<div className="actions"><button className="btn btn--primary" disabled={action.busy || !map.data} onClick={async () => { const value = await action.mutate(`/activos/${id}/senal`); if (value !== undefined) setRequested(true) }}>Señalar posición</button>{asset.data?.estado === 'disponible' && <Link to={`/prestamo?id=${id}`} className="btn btn--secondary">Registrar préstamo</Link>}<Link to={`/recurso/${id}`} className="btn btn--secondary">Volver a la ficha</Link></div></div></Page>
}
