import { Shell, PageHeader } from '../components.jsx'
import { Link } from '../router.jsx'

// Índice del prototipo: acceso directo a cada pantalla, agrupada por flujo.
// No forma parte del producto; sirve para revisar los recorridos.
const FLUJOS = [
  ['Identificación', [['/acceso', 'Entrar con la credencial'], ['/acceso/qr', 'Escanear el código QR']]],
  ['Entrada y navegación', [['/inicio', 'Inicio']]],
  [
    'Consulta de recursos',
    [
      ['/inventario', 'Buscar y comparar recursos'],
      ['/recurso/ACT-004', 'Ficha · disponible'],
      ['/recurso/ACT-002', 'Ficha · prestado'],
      ['/recurso/ACT-005', 'Ficha · en revisión'],
      ['/recurso/ACT-004/ubicacion', 'Gabinete y posición'],
    ],
  ],
  [
    'Préstamo',
    [
      ['/prestamo', 'Elegir a la persona responsable'],
      ['/prestamo/retiro', 'Retirar y esperar la lectura'],
      ['/prestamo/comprobante', 'Comprobante de retiro'],
    ],
  ],
  ['Préstamos activos', [['/mis-recursos', 'Pendientes e historial'], ['/mis-recursos/prestamo', 'Detalle del préstamo']]],
  [
    'Devolución',
    [
      ['/devolucion', 'Seleccionar el préstamo'],
      ['/devolucion/lectura', 'Presentar el equipo al lector'],
      ['/devolucion/ubicacion', 'Colocar en el lugar asignado'],
      ['/devolucion/comprobante', 'Comprobante de devolución'],
    ],
  ],
  [
    'Excepciones',
    [
      ['/devolucion/incorrecto', 'Recurso incorrecto (devolución)'],
      ['/prestamo/inesperado', 'Recurso inesperado (retiro)'],
      ['/prestamo/sin-responsable', 'Movimiento sin responsable'],
      ['/devolucion/no-confirmada', 'Ubicación no confirmada'],
    ],
  ],
  ['Análisis', [['/analisis', 'Uso del laboratorio y recomendación'], ['/analisis/reutilizar', 'Recursos para reutilizar']]],
]

export function Flujos() {
  return (
    <Shell>
      <PageHeader titulo="Flujos del prototipo" subtitulo="Abre cualquier pantalla directamente. Los datos son de demostración." />
      <div className="container content">
        <div className="flujos">
          {FLUJOS.map(([grupo, pantallas]) => (
            <section key={grupo} className="card">
              <h2 className="h-sm">{grupo}</h2>
              <ul className="lista-simple">
                {pantallas.map(([to, texto]) => (
                  <li key={to}>
                    <Link to={to} className="enlace">
                      {texto}
                    </Link>
                  </li>
                ))}
              </ul>
            </section>
          ))}
        </div>
      </div>
    </Shell>
  )
}
