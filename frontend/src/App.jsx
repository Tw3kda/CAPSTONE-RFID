import { useEffect, useState } from 'react'
import { Link, useRoute } from './router.jsx'
import { RECURSO_REFERENCIA } from './data.js'
import { Acceso, AccesoQR } from './screens/Acceso.jsx'
import { Inicio } from './screens/Inicio.jsx'
import { Inventario, Ficha, Ubicacion } from './screens/Inventario.jsx'
import { PrestamoForm, Retiro, ComprobanteRetiro, RecursoInesperado, SinResponsable } from './screens/Prestamo.jsx'
import {
  MisRecursos,
  DetallePrestamo,
  DevolucionSeleccion,
  DevolucionLectura,
  DevolucionUbicacion,
  ComprobanteDevolucion,
  RecursoIncorrecto,
  UbicacionNoConfirmada,
} from './screens/MisRecursos.jsx'
import { Analisis, Reutilizar } from './screens/Analisis.jsx'
import { Flujos } from './screens/Flujos.jsx'

function pantalla(path, query, prestamo, setPrestamo) {
  const recurso = path.match(/^\/recurso\/([^/]+)(\/ubicacion)?$/)
  if (recurso) return recurso[2] ? <Ubicacion id={recurso[1]} /> : <Ficha id={recurso[1]} />

  switch (path) {
    case '/acceso':
      return <Acceso />
    case '/acceso/qr':
      return <AccesoQR />
    case '/inicio':
      return <Inicio />
    case '/inventario':
      return <Inventario key={query.get('q')} q0={query.get('q') ?? ''} />
    case '/prestamo':
      return <PrestamoForm key={query.get('id')} id0={query.get('id')} setPrestamo={setPrestamo} />
    case '/prestamo/retiro':
      return <Retiro prestamo={prestamo} />
    case '/prestamo/comprobante':
      return <ComprobanteRetiro prestamo={prestamo} />
    case '/prestamo/inesperado':
      return <RecursoInesperado prestamo={prestamo} />
    case '/prestamo/sin-responsable':
      return <SinResponsable />
    case '/mis-recursos':
      return <MisRecursos />
    case '/mis-recursos/prestamo':
      return <DetallePrestamo />
    case '/devolucion':
      return <DevolucionSeleccion />
    case '/devolucion/lectura':
      return <DevolucionLectura />
    case '/devolucion/ubicacion':
      return <DevolucionUbicacion />
    case '/devolucion/comprobante':
      return <ComprobanteDevolucion />
    case '/devolucion/incorrecto':
      return <RecursoIncorrecto />
    case '/devolucion/no-confirmada':
      return <UbicacionNoConfirmada />
    case '/analisis':
      return <Analisis />
    case '/analisis/reutilizar':
      return <Reutilizar />
    case '/flujos':
      return <Flujos />
    default:
      return <Acceso />
  }
}

export default function App() {
  const { path, query } = useRoute()
  // Escenario de préstamo en curso. Por defecto, el ejemplo delegado del diseño.
  const [prestamo, setPrestamo] = useState({ recursoId: RECURSO_REFERENCIA, modo: 'delegado' })

  useEffect(() => {
    window.scrollTo(0, 0)
  }, [path])

  return (
    <>
      {pantalla(path, query, prestamo, setPrestamo)}
      {path !== '/flujos' && (
        <Link to="/flujos" className="fab-flujos" title="Índice de pantallas del prototipo">
          Flujos
        </Link>
      )}
    </>
  )
}
