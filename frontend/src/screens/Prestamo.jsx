import { useState } from 'react'
import { Page, LoadState, Field, Summary, ErrorNotice } from '../components.jsx'
import { Link, navigate } from '../router.jsx'
import { useApi, useMutation, useSession } from '../session.jsx'
import { queryString } from '../api.js'

function ResponsiblePicker({ onSelect }) {
  const [value, setValue] = useState('')
  const [query, setQuery] = useState('')
  const users = useApi(`/usuarios${queryString({ q: query })}`)
  return <div className="pila"><Field label="Destinatario (si es otra persona)" hint="Busca por nombre o por su ID universitario registrado."><div className="search-line"><input className="field" value={value} onChange={(event) => setValue(event.target.value)} autoComplete="off" /><button type="button" className="btn btn--secondary" onClick={() => { setQuery(value.trim()); onSelect(null) }}>Buscar persona</button></div></Field><LoadState request={users}>{(items) => <Field label="Persona responsable"><select className="field" defaultValue="" onChange={(event) => onSelect(items.find((item) => item.id === Number(event.target.value)) || null)}><option value="">Selecciona una persona</option>{items.map((person) => <option key={person.id} value={person.id} disabled={!person.activo}>{person.nombre} · {person.rol}{!person.activo ? ' · Inactiva' : ''}</option>)}</select>{!items.length && <span className="note">No se encontraron personas. Comprueba el ID o el nombre.</span>}</Field>}</LoadState></div>
}
export function PrestamoForm({ id0 }) {
  const { user } = useSession()
  const assets = useApi('/activos?estado=disponible')
  const [assetId, setAssetId] = useState(id0 || '')
  const [responsible, setResponsible] = useState(null)
  const [date, setDate] = useState('')
  const [localError, setLocalError] = useState(null)
  const action = useMutation()
  const item = assets.data?.find((asset) => asset.id === Number(assetId))
  async function submit(event) {
    event.preventDefault()
    const delegated = event.nativeEvent.submitter?.value === 'delegado'
    if (delegated && !responsible) { setLocalError(new Error('Movimiento sin responsable. Busca y selecciona la persona destinataria antes de continuar.')); return }
    setLocalError(null)
    const loan = await action.mutate('/prestamos', { activo_id: Number(assetId), responsable_id: delegated ? responsible.id : user.id, devolucion_esperada_at: new Date(date).toISOString() })
    if (loan) navigate(`/prestamo/retiro?id=${loan.id}`)
  }
  return <Page activo="prestamos" titulo="Registrar préstamo" subtitulo="Prepara la operación antes de retirar el recurso."><LoadState request={assets}>{(items) => items.length ? <div className="dos-col"><form className="pila" onSubmit={submit}><Field label="Recurso"><select className="field" value={assetId} required onChange={(event) => setAssetId(event.target.value)}><option value="">Selecciona un recurso</option>{items.map((asset) => <option key={asset.id} value={asset.id}>{asset.nombre} · {asset.codigo} · Disponible</option>)}</select></Field><h2 className="seccion--sm">¿Para quién es el préstamo?</h2><p className="note">Puedes preparar un préstamo a tu nombre{user.rol !== 'usuario' ? ' o elegir otra persona responsable.' : '.'}</p>{user.rol !== 'usuario' && <ResponsiblePicker onSelect={setResponsible} />}<Field label="Fecha prevista de devolución"><input className="field" type="datetime-local" required value={date} onChange={(event) => setDate(event.target.value)} /></Field><p className="note">El retiro se registra únicamente cuando el lector detecta el equipo.</p><ErrorNotice error={localError || action.error} /><div className="actions"><button className="btn btn--primary" value="propio" disabled={action.busy}>{action.busy ? 'Preparando…' : 'Continuar para mí'}</button>{user.rol !== 'usuario' && <button className="btn btn--secondary" value="delegado" disabled={action.busy}>Continuar para otra persona</button>}{item && <Link to={`/recurso/${item.id}/ubicacion`} className="btn btn--secondary">Ver ubicación</Link>}</div></form><Summary titulo="Resumen del préstamo" items={[[ 'Recurso', item?.nombre || 'Selecciona un recurso' ],[ 'Responsable', responsible?.nombre || user.nombre ],[ 'Registro', 'Se confirma al retirar' ]]} /></div> : <p className="card note">No hay recursos disponibles para preparar un préstamo. <Link to="/inventario" className="enlace">Consultar inventario</Link></p>}</LoadState></Page>
}

