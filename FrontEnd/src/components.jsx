import { Link } from './router.jsx'
import { ZONA, ubicacionCorta } from './data.js'

const TRAZOS = {
  buscar: <><circle cx="11" cy="11" r="7" /><path d="m20 20-3.5-3.5" /></>,
  mas: <path d="M12 5v14M5 12h14" />,
  reloj: <><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></>,
  devolver: <><path d="M20 12a8 8 0 1 1-2.6-5.9" /><path d="M20 4v5h-5" /></>,
  inicio: <><path d="M4 11 12 4l8 7v9H4z" /><path d="M10 20v-5h4v5" /></>,
  cuadricula: <><rect x="4" y="4" width="6" height="6" rx="1" /><rect x="14" y="4" width="6" height="6" rx="1" /><rect x="4" y="14" width="6" height="6" rx="1" /><rect x="14" y="14" width="6" height="6" rx="1" /></>,
  barras: <path d="M6 20v-6M12 20V5M18 20v-9" />,
  pin: <><path d="M12 21s-6-5.6-6-10a6 6 0 0 1 12 0c0 4.400-6 10-6 10z" /><circle cx="12" cy="11" r="2" /></>,
  chevron: <path d="m9 6 6 6-6 6" />,
  flecha: <path d="M7 17 17 7M9 7h8v8" />,
}

export function Icon({ name, size = 20 }) {
  return (
    <svg
      className="icon"
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {TRAZOS[name]}
    </svg>
  )
}

// Imagotipo en versión monocromo negativo, para la cabecera navy.
export function Logo() {
  return (
    <span className="logo">
      <svg width="23" height="22" viewBox="0 0 25 24" aria-hidden="true">
        <rect x="0" y="0" width="24" height="6" fill="currentColor" />
        <rect x="9" y="0" width="6" height="24" fill="currentColor" />
        <rect x="18.500" y="14" width="6" height="6" fill="currentColor" />
      </svg>
      Thesora
    </span>
  )
}

const NAV = [
  { clave: 'inicio', to: '/inicio', texto: 'Inicio', icono: 'inicio' },
  { clave: 'inventario', to: '/inventario', texto: 'Inventario', icono: 'cuadricula' },
  { clave: 'prestamos', to: '/prestamo', texto: 'Préstamos', icono: 'mas' },
  { clave: 'mis-recursos', to: '/mis-recursos', texto: 'Mis recursos', icono: 'reloj' },
  { clave: 'analisis', to: '/analisis', texto: 'Análisis', icono: 'barras' },
]

// Marco común: cabecera navy, navegación superior (escritorio) e inferior (móvil).
export function Shell({ activo, sinNav = false, children }) {
  return (
    <div className={sinNav ? 'shell' : 'shell shell--nav'}>
      <header className="topbar">
        <div className="topbar__inner">
          <Link to={sinNav ? '/acceso' : '/inicio'} className="topbar__logo" aria-label="Thesora, ir al inicio">
            <Logo />
          </Link>
          {!sinNav && (
            <>
              <nav className="topnav" aria-label="Principal">
                {NAV.map((n) => (
                  <Link key={n.clave} to={n.to} aria-current={activo === n.clave ? 'page' : undefined}>
                    {n.texto}
                  </Link>
                ))}
              </nav>
              <Link to="/acceso" className="btn btn--salir">
                Salir
              </Link>
            </>
          )}
        </div>
      </header>
      <main>{children}</main>
      {!sinNav && (
        <nav className="bottomnav" aria-label="Principal">
          {NAV.map((n) => (
            <Link key={n.clave} to={n.to} aria-current={activo === n.clave ? 'page' : undefined}>
              <Icon name={n.icono} />
              {n.texto}
            </Link>
          ))}
        </nav>
      )}
    </div>
  )
}

export function PageHeader({ titulo, subtitulo }) {
  return (
    <div className="pagehead">
      <div className="container">
        <h1>{titulo}</h1>
        {subtitulo && <p>{subtitulo}</p>}
      </div>
    </div>
  )
}

export function ResourceRow({ recurso }) {
  const clase = recurso.estado === 'En revisión' ? 'estado estado--revision' : 'estado'
  return (
    <Link to={`/recurso/${recurso.id}`} className="row">
      <span className="row__top">
        <span className="row__nombre">{recurso.nombre}</span>
        <Icon name="chevron" size={16} />
      </span>
      <span className="row__meta">
        {recurso.categoria} · {recurso.id}
      </span>
      <span className="row__bottom">
        <span className="row__ubicacion">
          <Icon name="pin" size={14} />
          {ubicacionCorta(recurso)}
        </span>
        <span className={clase}>{recurso.estado}</span>
      </span>
    </Link>
  )
}

export function ShelfMap({ recurso, leyenda }) {
  return (
    <section aria-label="Mapa de ubicación">
      <p className="label">{ZONA}</p>
      <div className="card shelf">
        <p className="overline">
          Gabinete {recurso.gab} / Estante {recurso.estante}
        </p>
        <ol className="shelf__slots">
          {[1, 2, 3, 4].map((n) => (
            <li key={n} className={n === recurso.pos ? 'is-activa' : undefined} aria-current={n === recurso.pos ? 'location' : undefined}>
              {n}
            </li>
          ))}
        </ol>
        <p className="shelf__leyenda">{leyenda}</p>
      </div>
    </section>
  )
}

export function Summary({ titulo, items }) {
  return (
    <aside className="card summary">
      <h2>{titulo}</h2>
      <dl>
        {items.map(([k, v]) => (
          <div key={k}>
            <dt className="overline">{k}</dt>
            <dd>{v}</dd>
          </div>
        ))}
      </dl>
    </aside>
  )
}

// Tarjeta de espera del lector RFID.
export function Esperando({ children = 'Esperando lectura RFID…' }) {
  return (
    <p className="esperando" role="status">
      <span className="esperando__punto" />
      {children}
    </p>
  )
}

// Aviso de excepción: qué ocurrió + siguiente paso.
export function Aviso({ ocurrio, paso }) {
  return (
    <div className="card aviso" role="alert">
      <h2 className="aviso__titulo">Qué ocurrió</h2>
      {ocurrio.map((l) => (
        <p key={l}>{l}</p>
      ))}
      <h2>Siguiente paso</h2>
      <p>{paso}</p>
    </div>
  )
}
