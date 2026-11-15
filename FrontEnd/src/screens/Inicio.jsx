import { Shell, Icon } from '../components.jsx'
import { Link, navigate } from '../router.jsx'
import { USUARIO, ZONA } from '../data.js'

const ACCIONES = [
  { to: '/inventario', texto: 'Buscar recurso', icono: 'buscar', principal: true },
  { to: '/prestamo', texto: 'Registrar préstamo', icono: 'mas' },
  { to: '/mis-recursos', texto: 'Mis recursos', icono: 'reloj' },
  { to: '/devolucion', texto: 'Devolver recurso', icono: 'devolver' },
]

export function Inicio() {
  return (
    <Shell activo="inicio">
      <div className="hero">
        <div className="container">
          <h1>Hola, {USUARIO.nombre}</h1>
          <p>¿Qué necesitas hacer con los recursos del laboratorio?</p>
          <form
            onSubmit={(e) => {
              e.preventDefault()
              const q = new FormData(e.currentTarget).get('q').trim()
              navigate(q ? `/inventario?q=${encodeURIComponent(q)}` : '/inventario')
            }}
          >
            <label className="label label--sm" htmlFor="buscar-inicio">
              Buscar en el inventario
            </label>
            <input id="buscar-inicio" name="q" className="field" placeholder="Ej. multímetro, kit, osciloscopio…" />
          </form>
        </div>
      </div>

      <div className="container content">
        <h2 className="seccion">Acciones rápidas</h2>
        <div className="acciones-rapidas">
          {ACCIONES.map((a) => (
            <Link key={a.to} to={a.to} className={a.principal ? 'accion accion--principal' : 'accion'}>
              <Icon name={a.icono} />
              {a.texto}
            </Link>
          ))}
        </div>

        <div className="dos-col">
          <div className="pila">
            <Link to="/mis-recursos/prestamo" className="card card--link">
              <p className="overline">Pendiente por devolver</p>
              <h2>Multímetro digital #04</h2>
              <p className="note">Fecha prevista: 30 sep · Ver préstamo ›</p>
            </Link>
            <section className="card">
              <h2>Análisis del laboratorio</h2>
              <p className="note">Aprovecha lo disponible y revisa mantenimiento antes de comprar o reemplazar equipos.</p>
              <p className="derecha">
                <Link to="/analisis" className="enlace">
                  Ver análisis <Icon name="flecha" size={14} />
                </Link>
              </p>
            </section>
          </div>
          <aside className="card summary">
            <h2>Tu actividad</h2>
            <dl>
              <div>
                <dt className="overline">Pendientes</dt>
                <dd>1 recurso por devolver</dd>
              </div>
              <div>
                <dt className="overline">Último movimiento</dt>
                <dd>Multímetro digital #04</dd>
              </div>
              <div>
                <dt className="overline">Ubicación</dt>
                <dd>{ZONA.replace('Zona', 'Zona de')}</dd>
              </div>
            </dl>
          </aside>
        </div>
      </div>
    </Shell>
  )
}
