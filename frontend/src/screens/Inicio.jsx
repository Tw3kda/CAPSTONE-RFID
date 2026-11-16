import { useState } from 'react'
import { Shell, Icon, LoadState, formatDate, locationText } from '../components.jsx'
import { Link, navigate } from '../router.jsx'
import { useApi, useSession } from '../session.jsx'

export function Inicio() {
  const { user } = useSession()
  const loans = useApi('/prestamos?alcance=mios')
  const [query, setQuery] = useState('')
  return <Shell activo="inicio"><section className="hero"><div className="container"><h1>Hola, {user.nombre}</h1><p>¿Qué necesitas hacer con los recursos del laboratorio?</p><form onSubmit={(event) => { event.preventDefault(); navigate(`/inventario?q=${encodeURIComponent(query)}`) }}><label className="label label--sm" htmlFor="inicio-buscar">Buscar en el inventario</label><div className="search-line"><input id="inicio-buscar" className="field" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Nombre o código del recurso" /><button className="btn btn--secondary" aria-label="Buscar"><Icon name="buscar" /></button></div></form></div></section><div className="container content"><h2 className="seccion">Acciones rápidas</h2><div className="acciones-rapidas">{[['/inventario','buscar','Buscar recurso'],['/prestamo','mas','Registrar préstamo'],['/mis-recursos','reloj','Mis recursos'],['/devolucion','devolver','Devolver recurso']].map(([to,icon,label],index) => <Link key={to} to={to} className={index === 0 ? 'accion accion--principal' : 'accion'}><Icon name={icon} />{label}</Link>)}</div><LoadState request={loans}>{(items) => {
    const pending = items.filter((loan) => !['devuelto','cancelado'].includes(loan.estado))
    const latest = items.find((loan) => loan.retiro_at || loan.devolucion_at)
    return <div className="dos-col"><div className="pila">{pending.length ? pending.slice(0,3).map((loan) => <Link key={loan.id} to={`/mis-recursos/prestamo?id=${loan.id}`} className="card card--link"><p className="overline">Pendiente por devolver</p><h2>{loan.activo_nombre}</h2><p className="note">Fecha prevista: {formatDate(loan.devolucion_esperada_at)} · Ver préstamo ›</p></Link>) : <p className="card note">No tienes recursos pendientes por devolver.</p>}<section className="card"><h2>Análisis del laboratorio</h2><p className="note">Aprovecha lo disponible y revisa mantenimiento antes de comprar o reemplazar equipos.</p><p className="derecha"><Link to="/analisis" className="enlace">Ver análisis ↗</Link></p></section></div><aside className="card"><h2>Tu actividad</h2><p className="overline">Pendientes</p><p>{pending.length} {pending.length === 1 ? 'recurso' : 'recursos'} por devolver</p><p className="overline">Último movimiento</p><p className="note">{latest ? `${latest.activo_nombre} · ${formatDate(latest.devolucion_at || latest.retiro_at)}` : 'Sin movimientos físicos registrados.'}</p>{latest && <><p className="overline">Ubicación</p><p className="note">{locationText(latest.ubicacion_asignada)}</p></>}</aside></div>
  }}</LoadState></div></Shell>
}

