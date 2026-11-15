// Datos de demostración. Nada de esto viene de un backend todavía.

export const USUARIO = { nombre: 'Rafael', completo: 'Rafael Salcedo', id: '20261234' }
export const DESTINATARIO = { completo: 'Santiago Navarro' }

export const ZONA = 'Zona electrónica'

// ACT-001 a ACT-008 salen de las capturas del diseño.
// ACT-009 a ACT-012 son de relleno para completar los doce recursos del catálogo.
export const RECURSOS = [
  { id: 'ACT-004', nombre: 'Multímetro digital #04', categoria: 'Medición eléctrica', tipo: 'Equipo de medición', gab: 'A', estante: 2, pos: 3, estado: 'Disponible' },
  { id: 'ACT-002', nombre: 'Osciloscopio #02', categoria: 'Medición eléctrica', tipo: 'Equipo de medición', gab: 'A', estante: 1, pos: 2, estado: 'Prestado' },
  { id: 'ACT-007', nombre: 'Kit de electrónica #07', categoria: 'Kits de práctica', tipo: 'Kit', gab: 'B', estante: 1, pos: 1, estado: 'Disponible' },
  { id: 'ACT-003', nombre: 'Fuente de alimentación #03', categoria: 'Alimentación', tipo: 'Fuente', gab: 'A', estante: 3, pos: 2, estado: 'Disponible' },
  { id: 'ACT-001', nombre: 'Generador de señales #01', categoria: 'Medición eléctrica', tipo: 'Equipo de medición', gab: 'A', estante: 1, pos: 4, estado: 'Disponible' },
  { id: 'ACT-006', nombre: 'Pinza amperimétrica #06', categoria: 'Medición eléctrica', tipo: 'Equipo de medición', gab: 'A', estante: 2, pos: 1, estado: 'Disponible' },
  { id: 'ACT-005', nombre: 'Estación de soldadura #05', categoria: 'Herramientas', tipo: 'Herramienta', gab: 'C', estante: 1, pos: 2, estado: 'En revisión' },
  { id: 'ACT-008', nombre: 'Kit Arduino #08', categoria: 'Kits de práctica', tipo: 'Kit', gab: 'B', estante: 2, pos: 3, estado: 'Disponible' },
  { id: 'ACT-009', nombre: 'Protoboard #09', categoria: 'Kits de práctica', tipo: 'Kit', gab: 'B', estante: 2, pos: 4, estado: 'Disponible' },
  { id: 'ACT-010', nombre: 'Analizador lógico #10', categoria: 'Medición eléctrica', tipo: 'Equipo de medición', gab: 'A', estante: 3, pos: 1, estado: 'Prestado' },
  { id: 'ACT-011', nombre: 'Cautín #11', categoria: 'Herramientas', tipo: 'Herramienta', gab: 'C', estante: 1, pos: 3, estado: 'Disponible' },
  { id: 'ACT-012', nombre: 'Fuente dual #12', categoria: 'Alimentación', tipo: 'Fuente', gab: 'A', estante: 3, pos: 4, estado: 'Disponible' },
]

export const RECURSO_REFERENCIA = 'ACT-004'
export const REUTILIZABLES = ['ACT-007', 'ACT-001', 'ACT-003']
export const USO_SEMANAL = [
  { semana: 'S1', usos: 28 },
  { semana: 'S2', usos: 34 },
  { semana: 'S3', usos: 39 },
  { semana: 'S4', usos: 47 },
]

export const buscarRecurso = (id) => RECURSOS.find((r) => r.id === id) ?? RECURSOS[0]
export const ubicacionCorta = (r) => `Gab. ${r.gab} · Estante ${r.estante} · Pos. ${r.pos}`
