import { Link } from './router.jsx'
import { navigate } from './navigation.js'
import { availabilityLabel } from './presentation.js'
import { useSession } from './hooks.js'
import logo from './assets/Thesora_Imagotipo_Negativo_Transparente.svg'

const TRAZOS = {
  buscar: <><circle cx="11" cy="11" r="7" /><path d="m20 20-3.5-3.5" /></>,
  mas: <path d="M12 5v14M5 12h14" />,
  reloj: <><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></>,
  devolver: <><path d="M20 12a8 8 0 1 1-2.6-5.9" /><path d="M20 4v5h-5" /></>,
  inicio: <><path d="M4 11 12 4l8 7v9H4z" /><path d="M10 20v-5h4v5" /></>,
  cuadricula: <><rect x="4" y="4" width="6" height="6" rx="1" /><rect x="14" y="4" width="6" height="6" rx="1" /><rect x="4" y="14" width="6" height="6" rx="1" /><rect x="14" y="14" width="6" height="6" rx="1" /></>,
  barras: <path d="M6 20v-6M12 20V5M18 20v-9" />,
  pin: <><path d="M12 21s-6-5.6-6-10a6 6 0 0 1 12 0c0 4.4-6 10-6 10z" /><circle cx="12" cy="11" r="2" /></>,
  chevron: <path d="m9 6 6 6-6 6" />,
}
export function Icon({ name, size = 20 }) {
  return <svg className="icon" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{TRAZOS[name]}</svg>
}
const NAV = [
  ['inicio', '/inicio', 'Inicio', 'inicio'],
  ['inventario', '/inventario', 'Inventario', 'cuadricula'],
  ['prestamos', '/prestamo', 'Préstamos', 'mas'],
  ['mis-recursos', '/mis-recursos', 'Mis recursos', 'reloj'],
  ['analisis', '/analisis', 'Análisis', 'barras'],
]
export function Shell({ activo, sinNav = false, children }) {
  const { user, client, connection, event } = useSession()
  const unregisteredRemoval = event?.tipo === 'inventario_actualizado' && event.detalle?.error === 'retiro_sin_prestamo'
  const administrator = user?.rol === 'administrador'
  const navigation = NAV.filter(([key]) => key !== 'analisis' || administrator)
  const links = navigation.map(([key, to, label, icon]) => <Link key={key} to={to} aria-current={activo === key ? 'page' : undefined}><Icon name={icon} />{label}</Link>)
  const adminLink = administrator && <Link to="/admin/usuarios" aria-current={activo === 'admin' ? 'page' : undefined}>Administración</Link>
  const logout = () => { client.logout(); navigate('/acceso') }
  return <div className={sinNav ? 'shell' : 'shell shell--nav'}>
    <a className="skip-link" href="#contenido" onClick={(event) => { event.preventDefault(); document.getElementById('contenido')?.focus() }}>Saltar al contenido</a>
    <header className="topbar"><div className="topbar__inner">
      <Link to={sinNav ? '/acceso' : '/inicio'} className="topbar__logo" aria-label="Thesora, ir al inicio"><img className="brand-logo" src={logo} alt="Thesora" width="151" height="48" /></Link>
      {!sinNav && <>
        <nav className="topnav" aria-label="Principal">{links}{adminLink}</nav>
        <button className="btn btn--salir topbar__logout" onClick={logout}>Salir</button>
        <details className="topmenu"><summary>Menú</summary><nav aria-label="Menú superior móvil" onClick={(event) => { event.currentTarget.parentElement.open = false }}>{links}{adminLink}<button className="btn" onClick={logout}>Salir</button></nav></details>
      </>}
    </div></header>
    {!sinNav && connection !== 'conectado' && <div className="connection-notice" role="status">Actualización en vivo {connection === 'conectando' ? 'conectando…' : 'desconectada. Reintentando…'} <button className="enlace" onClick={() => window.dispatchEvent(new Event('thesora:refresh'))}>Actualizar datos</button></div>}
    <main id="contenido" tabIndex="-1">{!sinNav && unregisteredRemoval && <div className="container"><div className="notice-warning" role="alert"><strong>Retirado sin préstamo registrado.</strong> El servidor detectó la ausencia de un recurso en su posición asignada. <Link to={`/recurso/${event.activo_id}`} className="enlace">Ver recurso retirado</Link></div></div>}{children}</main>
    {!sinNav && <nav className="bottomnav" aria-label="Principal móvil" style={{ gridTemplateColumns: `repeat(${navigation.length}, minmax(0, 1fr))` }}>{links}</nav>}
  </div>
}
export function PageHeader({ titulo, subtitulo }) {
  return <div className="pagehead"><div className="container"><h1>{titulo}</h1>{subtitulo && <p>{subtitulo}</p>}</div></div>
}
export function Page({ activo, titulo, subtitulo, children }) {
  return <Shell activo={activo}><PageHeader titulo={titulo} subtitulo={subtitulo} /><div className="container content">{children}</div></Shell>
}
export function ResourceRow({ recurso }) {
  return <Link to={`/recurso/${recurso.id}`} className="row"><span className="row__top"><span className="row__nombre">{recurso.nombre}</span><Icon name="chevron" size={16} /></span><span className="row__meta">{recurso.categoria} · {recurso.codigo}</span><span className="row__bottom"><span className="row__ubicacion"><Icon name="pin" size={14} />{recurso.ubicacion.gabinete} · Est. {recurso.ubicacion.estante} · {recurso.ubicacion.codigo}</span><span className={recurso.estado === 'en_revision' ? 'estado estado--revision' : 'estado'}>{availabilityLabel(recurso)}</span></span></Link>
}
export function ShelfMap({ mapa, leyenda }) {
  return <section aria-label="Mapa de ubicación"><p className="label">{mapa.asignada.espacio}</p><div className="card shelf"><p className="overline">Gabinete {mapa.asignada.gabinete} / Estante {mapa.asignada.estante}</p><ol className="shelf__slots" style={{ gridTemplateColumns: `repeat(${Math.min(mapa.posiciones_estante.length, 4)}, minmax(0, 1fr))` }}>{mapa.posiciones_estante.map((position) => <li key={position.posicion_id} className={position.posicion_id === mapa.asignada.posicion_id ? 'is-activa' : undefined} aria-current={position.posicion_id === mapa.asignada.posicion_id ? 'location' : undefined}>{position.codigo}</li>)}</ol><p className="shelf__leyenda">{leyenda || `Posición asignada: ${mapa.asignada.codigo}`}</p></div></section>
}
export function Summary({ titulo, items }) {
  return <aside className="card summary"><h2>{titulo}</h2><dl>{items.map(([key, value]) => <div key={key}><dt className="overline">{key}</dt><dd>{value}</dd></div>)}</dl></aside>
}
export function Esperando({ children = 'Esperando lectura RFID…' }) {
  return <p className="esperando" role="status"><span className="esperando__punto" />{children}</p>
}
export function ErrorNotice({ error, retry }) {
  if (!error) return null
  return <div className="card aviso" role="alert"><h2>No se pudo completar la operación</h2><p>{error.message}</p>{retry && <button className="btn btn--secondary" onClick={retry}>Reintentar</button>}</div>
}
export function LoadState({ request, children }) {
  if (request.loading && !request.data) return <p role="status" className="vacio">Cargando…</p>
  if (request.error) return <ErrorNotice error={request.error} retry={request.reload} />
  return children(request.data)
}
export function Field({ label, children, hint }) {
  return <label className="form-field"><span className="label">{label}</span>{children}{hint && <span className="note">{hint}</span>}</label>
}

