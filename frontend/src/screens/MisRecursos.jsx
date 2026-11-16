import { useState } from 'react'
import { Page, LoadState, Summary, ShelfMap, Esperando, ErrorNotice, Field } from '../components.jsx'
import { formatDate, locationText, stateLabel } from '../presentation.js'
import { Link } from '../router.jsx'
import { navigate } from '../navigation.js'
import { useApi, useMutation, useSession } from '../hooks.js'
const finished = (loan) => ['devuelto','cancelado'].includes(loan.estado)

function LoanRow({ loan, to }) {
  return <Link to={to || `/mis-recursos/prestamo?id=${loan.id}`} className="row"><span className="row__nombre">{loan.activo_nombre}</span><span className="row__meta">{loan.responsable_nombre} · {stateLabel(loan.estado)}</span><span className="row__meta">Retiro: {formatDate(loan.retiro_at)} · Devolución prevista: {formatDate(loan.devolucion_esperada_at)}</span></Link>
}
export function MisRecursos({ selecting = false }) {
  const { user } = useSession()
  const [scope, setScope] = useState('mios')
  const loans = useApi(`/prestamos?alcance=${scope}`)
  return <Page activo="mis-recursos" titulo={selecting ? 'Selecciona el recurso que devolverás' : 'Mis recursos'} subtitulo="Consulta los préstamos pendientes y su historial.">{user.rol !== 'usuario' && <Field label="Consultar préstamos"><select className="field" value={scope} onChange={(event) => setScope(event.target.value)}><option value="mios">Mis préstamos</option><option value="todos">Todos los préstamos</option></select></Field>}<LoadState request={loans}>{(items) => <div className="col-principal"><h2 className="seccion--sm">Pendientes por devolver</h2>{items.filter((loan) => !finished(loan)).length ? <div className="rows">{items.filter((loan) => !finished(loan)).map((loan) => <LoanRow key={loan.id} loan={loan} to={selecting ? `/mis-recursos/prestamo?id=${loan.id}` : undefined} />)}</div> : <p className="card note">No hay préstamos pendientes.</p>}{!selecting && <><div className="actions"><Link to="/devolucion" className="btn btn--primary">Devolver recurso</Link></div><h2 className="seccion--sm">Historial</h2>{items.filter(finished).length ? <div className="rows">{items.filter(finished).map((loan) => <LoanRow key={loan.id} loan={loan} />)}</div> : <p className="note">No hay préstamos cerrados.</p>}</>}</div>}</LoadState></Page>
}
function LoanMap({ assetId }) {
  const map = useApi(`/activos/${assetId}/ubicacion`)
  const action = useMutation()
  const [requested, setRequested] = useState(false)
  return <div className="pila"><LoadState request={map}>{(value) => <ShelfMap mapa={value} leyenda={`Coloca el recurso en la posición ${value.asignada.codigo}. El lector debe confirmar su presencia.`} />}</LoadState><button className="btn btn--secondary" disabled={action.busy} onClick={async () => { const value = await action.mutate(`/activos/${assetId}/senal`); if (value !== undefined) setRequested(true) }}>Señalar posición asignada</button>{requested && <p role="status" className="note">Señal solicitada al dispositivo.</p>}<ErrorNotice error={action.error} /></div>
}
export function DetallePrestamo({ id, operation }) {
  const loan = useApi(`/prestamos/${id}`)
  const { event } = useSession()
  const action = useMutation()
  const [dismissed, setDismissed] = useState(null)
  const [problem, setProblem] = useState(false)
  const [override, setOverride] = useState(null)
  const current = loan.data
  const isPending = current && ['pendiente_retiro','validando_devolucion','esperando_posicion'].includes(current.estado)
  const liveError = event !== dismissed && event?.prestamo_id === Number(id) ? event.detalle?.error : null
  const error = isPending && liveError
  const withdrawal = current?.estado === 'pendiente_retiro'
  const returned = current?.estado === 'devuelto'
  const receipt = returned || (current?.estado === 'activo' && operation === 'retiro' && !override)
  const wrongPosition = error === 'posicion_incorrecta' || problem
  const title = error || problem ? wrongPosition ? 'Ubicación no confirmada' : withdrawal ? 'Recurso inesperado' : 'Recurso incorrecto'
    : returned ? 'Devolución confirmada' : receipt ? 'Retiro confirmado'
      : withdrawal ? 'Retira el recurso del stand'
        : current?.estado === 'validando_devolucion' ? 'Presenta el recurso al lector'
          : current?.estado === 'esperando_posicion' ? 'Colócalo en su posición' : 'Detalle del préstamo'
  async function beginReturn() {
    const result = await action.mutate(`/prestamos/${id}/devolucion`)
    if (result) navigate(`/devolucion/lectura?id=${id}`)
  }
  async function cancel() {
    const result = await action.mutate(`/prestamos/${id}/cancelar-operacion`)
    if (result) { setOverride(true); setDismissed(event); setProblem(false); navigate(`/mis-recursos/prestamo?id=${id}`) }
  }
  return <Page activo={withdrawal ? 'prestamos' : 'mis-recursos'} titulo={title} subtitulo={receipt ? 'Movimiento confirmado por el sistema RFID.' : undefined}><LoadState request={loan}>{(item) => <div className="col-principal pila">{(error || problem) && <div className="card aviso" role="alert"><h2>Qué ocurrió</h2><p>{wrongPosition ? 'El equipo no está confirmado en su posición asignada. El préstamo permanece abierto.' : 'El RFID leído no corresponde al recurso esperado. La operación sigue pendiente.'}</p><h2>Siguiente paso</h2><p>{wrongPosition ? `Coloca el recurso en ${locationText(item.ubicacion_asignada)}.` : 'Presenta el equipo correcto y vuelve a intentar la lectura.'}</p><button className="btn btn--secondary" onClick={() => { setDismissed(event); setProblem(false) }}>{wrongPosition ? 'Ver ubicación' : 'Reintentar lectura'}</button></div>}<Summary titulo={item.activo_nombre} items={[[ 'Responsable', item.responsable_nombre ],[ 'Entregado por', item.entregado_por_nombre ],[ 'Estado', stateLabel(item.estado) ],[ 'Retiro', formatDate(item.retiro_at) ],[ 'Devolución prevista', formatDate(item.devolucion_esperada_at) ],...(returned ? [[ 'Devuelto', formatDate(item.devolucion_at) ]] : []),[ 'Ubicación asignada', locationText(item.ubicacion_asignada) ]]} />{isPending && !error && !problem && <>{withdrawal ? <p>Retira únicamente el recurso indicado. El lector confirmará su salida.</p> : item.estado === 'validando_devolucion' ? <p>Presenta el equipo ante el lector para verificar su RFID.</p> : <LoanMap assetId={item.activo_id} />}<Esperando>{withdrawal ? 'Esperando detección física del retiro…' : item.estado === 'validando_devolucion' ? 'Esperando lectura RFID…' : 'Esperando detección física en la posición asignada…'}</Esperando></>}<ErrorNotice error={action.error} /><div className="actions">{item.estado === 'activo' && !receipt && <button className="btn btn--primary" onClick={beginReturn} disabled={action.busy}>Devolver recurso</button>}{isPending && <button className="btn btn--secondary" onClick={cancel} disabled={action.busy}>Cancelar operación</button>}{item.estado === 'esperando_posicion' && !problem && <button className="btn btn--secondary" onClick={() => setProblem(true)}>Reportar problema</button>}{receipt && <Link to="/prestamo" className="btn btn--primary">Nuevo préstamo</Link>}<Link to={`/recurso/${item.activo_id}/ubicacion`} className="btn btn--secondary">Ver ubicación asignada</Link><Link to="/mis-recursos" className="btn btn--secondary">Volver a mis recursos</Link><Link to="/inicio" className="btn btn--ghost">Ir al inicio</Link></div>{action.error?.status === 409 && <button className="btn btn--secondary" onClick={loan.reload}>Consultar estado actual</button>}</div>}</LoadState></Page>
}
