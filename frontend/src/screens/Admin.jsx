import { useState } from 'react'
import { Page, LoadState, Field, ErrorNotice } from '../components.jsx'
import { formatDate, stateLabel, availabilityLabel, locationText } from '../presentation.js'
import { Link } from '../router.jsx'

import { useApi, useMutation, useSession } from '../hooks.js'
import { queryString } from '../api.js'

const sections = {
  usuarios: ['Usuarios', 'Nuevo usuario', true],
  activos: ['Activos', 'Nuevo activo', true],
  categorias: ['Categorías', 'Nueva categoría'],
  espacios: ['Espacios', 'Nuevo espacio'],
  gabinetes: ['Gabinetes', 'Nuevo gabinete'],
  posiciones: ['Posiciones', 'Nueva posición'],
  dispositivos: ['Dispositivos', 'Nuevo dispositivo'],
  lectores: ['Lectores', 'Nuevo lector', true],
}
function TextField({ label, name, value = '', required = true, ...props }) {
  return <Field label={label}><input className="field" name={name} defaultValue={value ?? ''} required={required} {...props} /></Field>
}
function UserFields({ row }) {
  return <><TextField label="Nombre" name="nombre" value={row?.nombre} maxLength={150} /><Field label="Rol"><select className="field" name="rol" defaultValue={row?.rol || 'usuario'}>{['usuario','encargado','administrador'].map((role) => <option key={role} value={role}>{role}</option>)}</select></Field><TextField label={row ? 'Nuevo ID universitario (opcional)' : 'ID universitario registrado'} name="identificador_institucional" required={!row} maxLength={256} autoComplete="off" /><TextField label={row ? 'Nueva clave (opcional)' : 'Clave'} name="clave" type="password" required={!row} minLength={12} maxLength={128} autoComplete="new-password" /><TextField label={row ? 'Nuevo contenido QR (opcional)' : 'Contenido QR de la credencial (opcional)'} name="credencial" required={false} maxLength={256} autoComplete="off" />{row ? <><p className="note">Los identificadores y la clave no se recuperan. Deja los campos vacíos para conservarlos.</p><label className="check-field"><input type="checkbox" name="retirar_qr" />Retirar QR registrado</label><label className="check-field"><input type="checkbox" name="activo" defaultChecked={row.activo} />Cuenta activa</label></> : <><p className="note">Registra ambos identificadores cuando estén disponibles. El ID universitario es obligatorio; el QR es opcional.</p><TextField label="Correo institucional (opcional)" name="correo" type="email" required={false} maxLength={320} /></>}</>
}
function AssetFields({ row }) {
  const categories = useApi('/categorias')
  const positions = useApi('/posiciones')
  const date = row?.ultima_revision_at ? new Date(new Date(row.ultima_revision_at).getTime() - new Date(row.ultima_revision_at).getTimezoneOffset() * 60000).toISOString().slice(0,16) : ''
  return <><TextField label="Nombre" name="nombre" value={row?.nombre} maxLength={150} /><LoadState request={categories}>{(items) => <Field label="Categoría"><select className="field" name="categoria_id" defaultValue={row?.categoria_id || ''} required><option value="">Selecciona una categoría</option>{items.map((item) => <option key={item.id} value={item.id}>{item.nombre}</option>)}</select></Field>}</LoadState><LoadState request={positions}>{(items) => <Field label="Posición asignada"><select className="field" name="posicion_asignada_id" defaultValue={row?.ubicacion?.posicion_id || ''} required><option value="">Selecciona una posición</option>{items.map((item) => <option key={item.posicion_id} value={item.posicion_id}>{locationText(item)}</option>)}</select></Field>}</LoadState><TextField label={row ? 'Nuevo UID RFID (opcional)' : 'UID RFID'} name="rfid_uid" required={!row} minLength={8} maxLength={20} pattern="[0-9A-Fa-f]{8,20}" autoComplete="off" />{row && <p className="note">Deja el UID vacío para conservar la etiqueta actual.</p>}<Field label="Estado"><select className="field" name="estado" defaultValue={row?.estado || 'disponible'}>{['disponible','prestado','en_revision'].map((value) => <option key={value} value={value}>{stateLabel(value)}</option>)}</select></Field><TextField label="Condición física" name="condicion" value={row?.condicion} required={false} maxLength={100} /><TextField label="Última revisión" name="ultima_revision_at" type="datetime-local" value={date} required={false} /><p className="note">El servidor validará los cambios y cualquier préstamo abierto.</p></>
}
function CabinetFields() {
  const spaces = useApi('/espacios')
  return <><TextField label="Nombre" name="nombre" maxLength={120} /><LoadState request={spaces}>{(items) => <Field label="Espacio"><select className="field" name="espacio_id" required defaultValue=""><option value="">Selecciona un espacio</option>{items.map((item) => <option key={item.id} value={item.id}>{item.nombre}</option>)}</select>{!items.length && <span className="note">Crea primero un espacio.</span>}</Field>}</LoadState></>
}
function PositionFields() {
  const cabinets = useApi('/gabinetes')
  return <><LoadState request={cabinets}>{(items) => <Field label="Gabinete"><select className="field" name="gabinete_id" required defaultValue=""><option value="">Selecciona un gabinete</option>{items.map((item) => <option key={item.id} value={item.id}>{item.nombre} · Espacio #{item.espacio_id}</option>)}</select>{!items.length && <span className="note">Crea primero un gabinete.</span>}</Field>}</LoadState><TextField label="Estante" name="estante" maxLength={60} /><TextField label="Código de posición" name="codigo" maxLength={60} /></>
}
function ReaderFields({ row }) {
  const positions = useApi('/posiciones')
  return <>{!row && <><DevicePicker /><TextField label="Canal del lector" name="canal" type="number" min={1} step={1} /></>}<LoadState request={positions}>{(items) => <Field label="Posición del lector"><select className="field" name="posicion_id" required defaultValue={row?.posicion_id || ''}><option value="">Selecciona una posición</option>{items.map((item) => <option key={item.posicion_id} value={item.posicion_id}>{locationText(item)}</option>)}</select></Field>}</LoadState></>
}
function DevicePicker() {
  const devices = useApi('/dispositivos')
  return <LoadState request={devices}>{(items) => <Field label="Dispositivo ESP32"><select className="field" name="dispositivo_id" required defaultValue=""><option value="">Selecciona un dispositivo</option>{items.map((item) => <option key={item.id} value={item.id}>{item.id}</option>)}</select>{!items.length && <span className="note">Registra primero un dispositivo.</span>}</Field>}</LoadState>
}
function Editor({ section, row, onSaved, onCancel }) {
  const action = useMutation()
  async function submit(event) {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    const body = {}
    for (const [key,value] of form.entries()) {
      if (typeof value !== 'string') continue
      if (key === 'clave') { if (value !== '') body[key] = value }
      else if (value.trim()) body[key] = value.trim()
    }
    for (const name of ['categoria_id','posicion_asignada_id','espacio_id','gabinete_id','posicion_id','canal']) if (body[name]) body[name] = Number(body[name])
    if (section === 'usuarios' && row) { body.activo = form.has('activo'); if (form.has('retirar_qr')) body.credencial = null; delete body.retirar_qr }
    if (section === 'activos') {
      body.condicion = form.get('condicion').trim()
      body.ultima_revision_at = body.ultima_revision_at ? new Date(body.ultima_revision_at).toISOString() : null
    }
    const value = await action.mutate(`/${section}${row ? `/${row.id}` : ''}`, body, row ? 'PATCH' : 'POST')
    if (value !== undefined) onSaved(value)
  }
  return <section className="card admin-editor"><h2>{row ? 'Editar registro' : sections[section][1]}</h2><form className="pila" onSubmit={submit}>{section === 'usuarios' ? <UserFields row={row} /> : section === 'activos' ? <AssetFields row={row} /> : ['categorias','espacios'].includes(section) ? <TextField label="Nombre" name="nombre" maxLength={section === 'categorias' ? 100 : 120} /> : section === 'gabinetes' ? <CabinetFields /> : section === 'posiciones' ? <PositionFields /> : section === 'lectores' ? <ReaderFields row={row} /> : <TextField label="Identificador del dispositivo" name="id" maxLength={64} pattern="[A-Za-z0-9_-]+" />}<ErrorNotice error={action.error} /><div className="actions"><button className="btn btn--primary" disabled={action.busy}>{action.busy ? 'Guardando…' : 'Guardar'}</button><button className="btn btn--secondary" type="button" disabled={action.busy} onClick={onCancel}>Cancelar</button></div></form></section>
}
function columns(section) {
  switch (section) {
    case 'usuarios': return [['ID registro', (row) => row.id],['Nombre',(row) => row.nombre],['Rol',(row) => row.rol],['Cuenta',(row) => row.activo ? 'Activa' : 'Inactiva']]
    case 'activos': return [['Código',(row) => row.codigo],['Nombre',(row) => row.nombre],['Categoría',(row) => row.categoria],['Disponibilidad',(row) => availabilityLabel(row)],['Ubicación',(row) => locationText(row.ubicacion)]]
    case 'posiciones': return [['ID registro',(row) => row.posicion_id],['Espacio',(row) => row.espacio],['Gabinete',(row) => row.gabinete],['Estante',(row) => row.estante],['Posición',(row) => row.codigo]]
    case 'gabinetes': return [['ID registro',(row) => row.id],['Nombre',(row) => row.nombre],['ID espacio',(row) => row.espacio_id]]
    case 'lectores': return [['ID registro',(row) => row.id],['Dispositivo',(row) => row.dispositivo_id],['Canal',(row) => row.canal],['ID posición',(row) => row.posicion_id]]
    case 'dispositivos': return [['Dispositivo',(row) => row.id],['Firmware',(row) => row.firmware || 'Sin reporte'],['Último contacto',(row) => formatDate(row.ultimo_heartbeat)],['RSSI',(row) => row.ultimo_rssi == null ? 'Sin reporte' : `${row.ultimo_rssi} dBm`]]
    default: return [['ID registro',(row) => row.id],['Nombre',(row) => row.nombre]]
  }
}
export function Admin({ section }) {
  const valid = !!sections[section]
  const [search, setSearch] = useState('')
  const [query, setQuery] = useState('')
  const [editor, setEditor] = useState(null)
  const [createdKey, setCreatedKey] = useState(null)
  const [saved, setSaved] = useState(false)
  const { client, user } = useSession()
  const request = useApi(`/${valid ? section : 'usuarios'}${queryString({ q: section === 'usuarios' ? query : '' })}`)
  if (!valid) return <Page activo="admin" titulo="Sección no encontrada"><Link to="/admin/usuarios" className="enlace">Volver a administración</Link></Page>
  const fields = columns(section)
  async function onSaved(value) {
    if (section === 'usuarios' && editor?.id === user.id) await client.restore()
    setEditor(null); setSaved(true)
    if (section === 'dispositivos' && value?.api_key) setCreatedKey(value)
  }
  return <Page activo="admin" titulo="Administración" subtitulo="Gestiona las cuentas, el inventario y su configuración física."><nav className="admin-nav" aria-label="Administración">{Object.entries(sections).map(([key,[label]]) => <Link key={key} to={`/admin/${key}`} aria-current={key === section ? 'page' : undefined}>{label}</Link>)}</nav><div className="admin-toolbar"><h2>{sections[section][0]}</h2><button className="btn btn--primary" disabled={!!editor} onClick={() => { setEditor({}); setSaved(false); setCreatedKey(null) }}>{sections[section][1]}</button></div>{createdKey && <section className="card pila key-result" role="status"><h2>Dispositivo registrado: {createdKey.id}</h2><p>Guarda esta clave en la configuración del ESP32. Se entrega una sola vez.</p><Field label="Clave del dispositivo"><textarea className="field" readOnly value={createdKey.api_key} spellCheck="false" /></Field><button className="btn btn--secondary" onClick={() => setCreatedKey(null)}>Ya guardé la clave</button></section>}{saved && !createdKey && <p className="card card--ok" role="status">Cambios guardados.</p>}{editor && <Editor key={editor.id || 'new'} section={section} row={editor.id ? editor : null} onSaved={onSaved} onCancel={() => setEditor(null)} />}{section === 'usuarios' && <form className="admin-search search-line" onSubmit={(event) => { event.preventDefault(); setQuery(search.trim()) }}><Field label="Buscar usuarios"><input className="field" placeholder="Nombre o ID universitario registrado" value={search} onChange={(event) => setSearch(event.target.value)} /></Field><button className="btn btn--secondary">Buscar</button></form>}<LoadState request={request}>{(items) => items.length ? <div className="table-scroll" tabIndex="0" role="region" aria-label={`Tabla de ${sections[section][0]}`}><table className="admin-table"><caption>{sections[section][0]} registrados</caption><thead><tr>{fields.map(([label]) => <th key={label} scope="col">{label}</th>)}{sections[section][2] && <th scope="col">Acciones</th>}</tr></thead><tbody>{items.map((row) => <tr key={row.id || row.posicion_id}>{fields.map(([label,render]) => <td key={label}>{render(row)}</td>)}{sections[section][2] && <td><button className="btn btn--secondary" aria-label={`Editar ${row.nombre || `lector ${row.id}`}`} onClick={() => { setEditor(row); setSaved(false) }}>Editar</button></td>}</tr>)}</tbody></table></div> : <p className="card note">No hay registros{query ? ' que coincidan con la búsqueda' : ''}.</p>}</LoadState></Page>
}
