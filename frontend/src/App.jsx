import { useEffect } from 'react'
import { Link } from './router.jsx'
import { useRoute, navigate } from './navigation.js'
import { useSession } from './hooks.js'
import { Page, Shell, PageHeader, ErrorNotice } from './components.jsx'
import { Acceso, AccesoQR } from './screens/Acceso.jsx'
import { Inicio } from './screens/Inicio.jsx'
import { Inventario, Ficha, Ubicacion } from './screens/Inventario.jsx'
import { PrestamoForm } from './screens/Prestamo.jsx'
import { MisRecursos, DetallePrestamo } from './screens/MisRecursos.jsx'
import { Analisis, Reutilizar } from './screens/Analisis.jsx'
import { Admin } from './screens/Admin.jsx'
import { Legal } from './screens/Legal.jsx'

export default function App() {
  const { path, query } = useRoute()
  const { user, ready, error, client } = useSession()
  const legalTitle = path === '/privacidad' ? 'Política de privacidad y tratamiento de datos personales' : path === '/terminos' ? 'Términos y condiciones de uso' : null
  useEffect(() => {
    document.title = legalTitle ? `${legalTitle} · Thesora` : 'Thesora · Cada recurso, en su lugar'
    if (user && path.startsWith('/acceso')) navigate('/inicio')
  }, [path, user, legalTitle])
  if (legalTitle) return <Legal privacy={path === '/privacidad'} />
  if (!ready) return <Shell sinNav><PageHeader titulo="Recuperando sesión…" /></Shell>
  if (!user) return path === '/acceso/qr' ? <AccesoQR /> : <Acceso />
  if (error && error.status !== 401) return <Shell sinNav><PageHeader titulo="No se pudo recuperar la sesión" /><div className="container content"><ErrorNotice error={error} retry={() => window.location.reload()} /><button className="btn btn--secondary" onClick={client.logout}>Volver al acceso</button></div></Shell>
  const asset = path.match(/^\/recurso\/(\d+)(\/ubicacion)?$/)
  if (asset) return asset[2] ? <Ubicacion key={path} id={asset[1]} /> : <Ficha key={path} id={asset[1]} />
  if ((path.startsWith('/admin') || path.startsWith('/analisis')) && user.rol !== 'administrador') {
    return <Page titulo="Acceso restringido" subtitulo="Esta sección requiere el rol Administrador."><Link to="/inicio" className="btn btn--primary">Ir al inicio</Link></Page>
  }
  if (path.startsWith('/admin')) {
    return <Admin key={path} section={path.split('/')[2] || 'usuarios'} />
  }
  const id = query.get('id')
  switch (path) {
    case '/acceso': case '/inicio': return <Inicio />
    case '/inventario': return <Inventario key={query.get('q')} q0={query.get('q') || ''} />
    case '/prestamo': return <PrestamoForm key={id} id0={id} />
    case '/mis-recursos': return <MisRecursos />
    case '/devolucion': return <MisRecursos selecting />
    case '/prestamo/retiro': case '/prestamo/comprobante': return id ? <DetallePrestamo key={id} id={id} operation="retiro" /> : <MisRecursos />
    case '/mis-recursos/prestamo': return id ? <DetallePrestamo key={id} id={id} /> : <MisRecursos />
    case '/devolucion/lectura': case '/devolucion/ubicacion': case '/devolucion/comprobante': return id ? <DetallePrestamo key={id} id={id} operation="devolucion" /> : <MisRecursos selecting />
    case '/analisis': return <Analisis />
    case '/analisis/reutilizar': return <Reutilizar />
    default: return <Page titulo="Página no encontrada"><Link to="/inicio" className="btn btn--primary">Ir al inicio</Link></Page>
  }
}
