// Prueba schema.sql en un Postgres local (PGlite), simulando lo que manda
// el ESP32. No toca el proyecto de Supabase.   Uso: npm install && npm test
import { PGlite } from '@electric-sql/pglite'
import { readFileSync } from 'node:fs'

const sql = readFileSync(process.argv[2] ?? new URL('../schema.sql', import.meta.url), 'utf8')
const db = new PGlite()
let fallos = 0
const ok = (cond, msg) => {
  console.log(`${cond ? 'PASS' : 'FAIL'}  ${msg}`)
  if (!cond) fallos++
}
const filas = async (q) => (await db.query(q)).rows

// Lo que Supabase ya trae
await db.exec(`create role anon nologin; create role authenticated nologin; create publication supabase_realtime;`)

await db.exec(sql)
await db.exec(sql) // segunda vez: debe ser re-ejecutable
ok(true, 'el script corre dos veces sin error')

ok((await filas(`select count(*)::int n from recursos`))[0].n === 12, '12 recursos tras ejecutar dos veces')
ok((await filas(`select count(*)::int n from pg_publication_tables where pubname='supabase_realtime'`))[0].n === 3, '3 tablas en realtime')

// Normalizacion de UID al editar el mapeo
await db.exec(`update recursos set uid_tag = '0xA1, 0xb2, 0xC3, 0xd4', dispositivo_id='stand-01', lector=2 where id='ACT-002'`)
ok((await filas(`select uid_tag from recursos where id='ACT-002'`))[0].uid_tag === 'A1B2C3D4', 'UID se normaliza desde formato 0x..')
let err = null
try { await db.exec(`update recursos set uid_tag = '6F123CE' where id='ACT-003'`) } catch (e) { err = e }
ok(err && /recursos_uid_tag_valido/.test(err.message), 'UID de longitud impar se rechaza')

// ---- A partir de aqui, como el ESP32: rol anon ----
await db.exec(`set role anon`)

const ev = (seq, evento, uid, lector, ms = 0, arr = 1) =>
  `('stand-01', ${arr}, ${seq}, '${evento}', ${uid ? `'${uid}'` : 'null'}, ${lector ?? 'null'}, ${ms})`
const insertar = (vals) =>
  db.exec(`insert into eventos (dispositivo_id, arranque, seq, evento, uid, lector, antiguedad_ms) values ${vals.join(',')}`)
const rec = async (id) => (await filas(`select presente, lector_actual, dispositivo_actual, senalizar_hasta from recursos where id='${id}'`))[0]
const evt = async (seq, arr = 1) => (await filas(`select recurso_id, resultado, ocurrido_en, recibido_en from eventos where arranque=${arr} and seq=${seq}`))[0]

// Arranque: lote INICIO + PRESENTE
await insertar([ev(1, 'INICIO'), ev(2, 'PRESENTE', 'AF91D01C', 1, 4000), ev(3, 'PRESENTE', '06F123CE', 2, 4000)])
ok((await rec('ACT-004')).presente === true && (await rec('ACT-004')).lector_actual === 1, 'PRESENTE marca ACT-004 en lector 1')
ok((await rec('ACT-007')).presente === false, 'ACT-007 no estaba al arrancar -> ausente')
let e = await evt(2)
ok(e.recurso_id === 'ACT-004' && e.resultado === 'OK', 'evento resuelto a ACT-004 / OK')
ok(Math.abs(e.recibido_en - e.ocurrido_en - 4000) < 5, 'ocurrido_en = recibido - antiguedad_ms')

// Retiro
await insertar([ev(4, 'RETIRADO', 'AF91D01C', 1)])
ok((await rec('ACT-004')).presente === false && (await rec('ACT-004')).lector_actual === null, 'RETIRADO marca ausente')

// Reintento duplicado -> violacion de unicidad (PostgREST: 409) y nada cambia
err = null
try { await insertar([ev(4, 'RETIRADO', 'AF91D01C', 1)]) } catch (x) { err = x }
ok(err && err.code === '23505', 'reintento duplicado da 23505')

// Devolucion en lugar incorrecto
await insertar([ev(5, 'DEVUELTO', 'af91d01c', 2)])
e = await evt(5)
ok(e.resultado === 'LUGAR_INCORRECTO' && (await rec('ACT-004')).lector_actual === 2, 'devuelto en lector 2 -> LUGAR_INCORRECTO, presente en 2')

// Mover de lector 2 a lector 1: llega DEVUELTO(1) antes que RETIRADO(2)
await insertar([ev(6, 'DEVUELTO', 'AF91D01C', 1)])
await insertar([ev(7, 'RETIRADO', 'AF91D01C', 2)])
let r4 = await rec('ACT-004')
ok(r4.presente === true && r4.lector_actual === 1, 'mover entre lectores: queda presente en lector 1')
ok((await evt(6)).resultado === 'OK', 'devuelto en su lector -> OK')

// Tag desconocido
await insertar([ev(8, 'DEVUELTO', 'DEADBEEF', 1)])
e = await evt(8)
ok(e.resultado === 'DESCONOCIDO' && e.recurso_id === null, 'tag desconocido -> DESCONOCIDO')

// Evento sin uid -> error 22023 (PostgREST: 400)
err = null
try { await insertar([ev(9, 'DEVUELTO', null, 1)]) } catch (x) { err = x }
ok(err && err.code === '22023', 'evento sin uid da 22023')

// El cliente no puede falsear recurso_id / resultado
await db.exec(`insert into eventos (dispositivo_id, arranque, seq, evento, uid, lector, recurso_id, resultado) values ('stand-01',1,10,'DEVUELTO','DEADBEEF',1,'ACT-004','OK')`)
e = await evt(10)
ok(e.recurso_id === null && e.resultado === 'DESCONOCIDO', 'recurso_id/resultado del cliente se ignoran')

// Cambio de mapeo desde el backend: el tag de ACT-004 pasa a lector 2
await db.exec(`reset role; update recursos set lector = 2 where id='ACT-004'; set role anon`)
await insertar([ev(11, 'RETIRADO', 'AF91D01C', 1), ev(12, 'DEVUELTO', 'AF91D01C', 1)])
ok((await evt(12)).resultado === 'LUGAR_INCORRECTO', 'tras cambiar el mapeo, lector 1 ya es lugar incorrecto')
await db.exec(`reset role; update recursos set lector = 1 where id='ACT-004'; set role anon`)

// Lo que descarga el ESP32 como configuracion
const cfg = await filas(`select uid_tag, lector, id from recursos where dispositivo_id='stand-01' and uid_tag is not null order by id`)
ok(cfg.length === 4, `config del stand: ${cfg.map((c) => `${c.uid_tag}>${c.lector}`).join(' ')}`)

// Indicador luminoso
ok((await filas(`select * from senales`)).length === 0, 'sin senales al inicio')
await db.exec(`select senalizar('ACT-007')`)
let s = await filas(`select dispositivo_id, lector from senales`)
ok(s.length === 1 && s[0].lector === 1 && s[0].dispositivo_id === 'stand-01', 'senalizar(ACT-007) -> lector 1')
await insertar([ev(13, 'DEVUELTO', '15F9DD00', 1)])
ok((await filas(`select * from senales`)).length === 0, 'la senal se apaga al colocar el recurso en su lector')
await db.exec(`select senalizar('ACT-007', 30)`)
await db.exec(`select senalizar('ACT-007', 0)`)
ok((await filas(`select * from senales`)).length === 0, 'senalizar(.., 0) apaga')

// Latido
await db.exec(`select latido('stand-01', 1, 'v2', '192.168.1.50', -61)`)
let d = (await filas(`select * from dispositivos_estado where id='stand-01'`))[0]
ok(d.en_linea === true, 'tras latido: en linea')
await db.exec(`select latido('stand-99', 1, 'v2', '10.0.0.2', -70)`)
ok((await filas(`select count(*)::int n from dispositivos`))[0].n === 2, 'un stand nuevo se registra solo')

// Reinicio del ESP32: nuevo arranque, seq vuelve a 1, lo ausente se limpia
await insertar([ev(1, 'INICIO', null, null, 0, 2), ev(2, 'PRESENTE', '06F123CE', 2, 0, 2)])
ok((await rec('ACT-004')).presente === false && (await rec('ACT-001')).presente === true, 'INICIO limpia y PRESENTE repone')

// Permisos: anon no puede modificar ni borrar
for (const q of [
  `update recursos set lector = 9 where id='ACT-004'`,
  `delete from eventos`,
  `insert into recursos (id, nombre) values ('X','x')`,
  `update dispositivos set nombre='x'`,
]) {
  err = null
  try { await db.exec(q) } catch (x) { err = x }
  ok(err && err.code === '42501', `anon no puede: ${q.slice(0, 32)}...`)
}

console.log(fallos ? `\n${fallos} FALLOS` : '\nTODO OK')
process.exit(fallos ? 1 : 0)
